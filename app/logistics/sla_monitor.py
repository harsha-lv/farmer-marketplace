"""SLA monitoring service for logistics shipments.

Guarantees:
  - Continuously evaluates active shipments against contracted pickup windows and delivery ETAs.
  - Automatically flags missed pickup windows and breached ETAs.
  - Automatically raises an IGM grievance ticket (`category="DELIVERY_DELAY"`, `escalation_level=1`).
  - Automatically pauses settlement release on the associated `TradeContract` (`settlement_hold=True`).
  - Publishes `ShipmentStatusChanged` event to Kafka topic `agri.shipment.events`.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.events.kafka import KafkaProducerClient
from app.events.schemas import (
    TOPIC_SHIPMENT_EVENTS,
    EventEnvelope,
    RegisteredEventType,
)
from app.logistics.models import Shipment
from app.ondc.igm import IgmService

logger = logging.getLogger("app.logistics.sla_monitor")


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """Ensure datetime has UTC timezone for cross-dialect (SQLite/PostgreSQL) safe comparison."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class SlaMonitorService:
    """Evaluates shipment SLA deadlines, creates IGM disputes, and holds settlement release."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.igm_service = IgmService(session)
        self.kafka_producer = KafkaProducerClient(get_settings())

    async def check_shipment_slas(self) -> dict[str, Any]:
        """Scan all in-flight shipments and flag SLA breaches."""
        stmt = select(Shipment).where(
            Shipment.state.not_in(["DELIVERED", "CANCELLED", "COMPLETED"])
        )
        shipments = (await self.session.scalars(stmt)).all()

        now = datetime.now(UTC)
        breached: list[dict[str, Any]] = []

        for s in shipments:
            breach_type: str | None = None
            description: str | None = None

            pickup_end = _ensure_utc(s.pickup_window_end)
            eta_delivery = _ensure_utc(s.eta_delivery_at)

            # 1. Missed Pickup Window
            if pickup_end and pickup_end < now and s.actual_pickup_at is None:
                if s.sla_status != "PICKUP_BREACHED":
                    breach_type = "PICKUP_BREACHED"
                    s.sla_status = "PICKUP_BREACHED"
                    description = (
                        f"Pickup window SLA breached for shipment {s.shipment_id}. "
                        f"Scheduled deadline was {pickup_end.isoformat()}, carrier has not picked up."
                    )

            # 2. Breached Delivery ETA
            elif eta_delivery and eta_delivery < now and s.actual_delivery_at is None:
                if s.sla_status != "DELIVERY_BREACHED":
                    breach_type = "DELIVERY_BREACHED"
                    s.sla_status = "DELIVERY_BREACHED"
                    description = (
                        f"Delivery ETA SLA breached for shipment {s.shipment_id}. "
                        f"Committed delivery was {eta_delivery.isoformat()}."
                    )

            if breach_type and description:
                # Raise IGM grievance (which automatically sets settlement_hold = True on TradeContract)
                ticket = await self.igm_service.create_ticket(
                    transaction_id=s.transaction_id,
                    category="DELIVERY_DELAY",
                    sub_category=breach_type,
                    description=description,
                    complainant_info={
                        "role": "PLATFORM_SLA_MONITOR",
                        "shipment_id": s.shipment_id,
                        "transaction_id": s.transaction_id,
                    },
                    respondent_info={
                        "role": "LOGISTICS_PROVIDER",
                        "lsp_id": s.lsp_id,
                        "lsp_name": s.lsp_name,
                    },
                )
                s.igm_ticket_id = ticket.ticket_id
                s.updated_at = now

                # Publish Kafka event
                try:
                    event = EventEnvelope(
                        event_id=uuid.uuid4(),
                        stream_id=f"shipment-{s.shipment_id}",
                        event_type=RegisteredEventType.ShipmentStatusChanged.value,
                        event_version=1,
                        occurred_at=now,
                        aggregate_type="Shipment",
                        aggregate_id=s.shipment_id,
                        partition_key=s.shipment_id,
                        payload={
                            "shipment_id": s.shipment_id,
                            "transaction_id": s.transaction_id,
                            "lsp_id": s.lsp_id,
                            "state": s.state,
                            "sla_status": s.sla_status,
                            "breach_type": breach_type,
                            "igm_ticket_id": ticket.ticket_id,
                            "settlement_paused": True,
                        },
                    )
                    await self.kafka_producer.publish(event, topic=TOPIC_SHIPMENT_EVENTS)
                except Exception as exc:
                    logger.warning("Failed to publish ShipmentStatusChanged SLA breach event: %s", exc)

                breached.append({
                    "shipment_id": s.shipment_id,
                    "transaction_id": s.transaction_id,
                    "breach_type": breach_type,
                    "igm_ticket_id": ticket.ticket_id,
                    "settlement_paused": True,
                })

        await self.session.commit()
        return {
            "evaluated_count": len(shipments),
            "breached_count": len(breached),
            "breaches": breached,
        }
