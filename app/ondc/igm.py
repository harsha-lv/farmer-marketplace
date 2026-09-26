"""Integrated Grievance Management (IGM) service and SLA escalation ladder.

Guarantees:
  - Grievance categories: QUALITY, DELIVERY_DELAY, SHORT_QUANTITY, SETTLEMENT_PAYOUT, PACKAGING, COMMUNICATION
  - Escalation ladder: L1 Support -> L2 Network ONDC Escalation -> L3 Regulator
  - SLA timer checking job for automated ticket escalation
  - Pauses trade contract settlement while active grievance is unresolved
  - Exposes REST API service for Kotlin Android frontend
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ondc.models import IgmTicket
from app.trades.models import TradeContract

logger = logging.getLogger("app.ondc.igm")

VALID_CATEGORIES = {
    "QUALITY",
    "DELIVERY_DELAY",
    "SHORT_QUANTITY",
    "SETTLEMENT_PAYOUT",
    "PACKAGING",
    "COMMUNICATION",
}

ESCALATION_LEVELS = {
    1: "Level 1 - FPO Nodal Officer",
    2: "Level 2 - ONDC Network Escalation",
    3: "Level 3 - State Regulatory Authority / Arbitrator",
}

SLA_HOURS_PER_LEVEL = {
    1: 48,
    2: 24,
    3: 72,
}


class IgmService:
    """Manages IGM grievance tickets, SLA timer breaches, and settlement pauses."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_ticket(
        self,
        transaction_id: str,
        category: str,
        sub_category: str,
        description: str,
        complainant_info: dict[str, Any],
        respondent_info: dict[str, Any],
        ticket_id: str | None = None,
    ) -> IgmTicket:
        """Create new grievance ticket and pause trade contract settlement."""
        cat = category.upper() if category.upper() in VALID_CATEGORIES else "QUALITY"
        tkt_id = ticket_id or f"TKT-IGM-{uuid.uuid4().hex[:12].upper()}"

        now = datetime.now(UTC)
        sla_hours = SLA_HOURS_PER_LEVEL[1]
        sla_expires = now + timedelta(hours=sla_hours)

        ticket = IgmTicket(
            ticket_id=tkt_id,
            transaction_id=transaction_id,
            category=cat,
            sub_category=sub_category,
            description=description,
            status="OPEN",
            escalation_level=1,
            expected_response_time=f"PT{sla_hours}H",
            complainant_info=complainant_info,
            respondent_info=respondent_info,
            settlement_paused=True,
            sla_expires_at=sla_expires,
            created_at=now,
            updated_at=now,
        )
        self.session.add(ticket)

        # Pause settlement on the trade contract
        stmt = (
            update(TradeContract)
            .where(TradeContract.transaction_id == transaction_id)
            .values(settlement_hold=True, updated_at=now)
        )
        await self.session.execute(stmt)
        await self.session.commit()

        logger.warning(
            "Created IGM ticket %s for tx %s. Paused settlement pending resolution.",
            tkt_id,
            transaction_id,
        )
        return ticket

    async def escalate_ticket(self, ticket_id: str, reason: str | None = None) -> IgmTicket | None:
        """Escalate ticket up the ladder: L1 -> L2 -> L3."""
        stmt = select(IgmTicket).where(IgmTicket.ticket_id == ticket_id)
        ticket = (await self.session.scalars(stmt)).first()
        if not ticket or ticket.status in ("RESOLVED", "CLOSED"):
            return None

        current_level = ticket.escalation_level
        if current_level < 3:
            ticket.escalation_level += 1
            ticket.status = f"ESCALATED_L{ticket.escalation_level}"
            sla_hours = SLA_HOURS_PER_LEVEL.get(ticket.escalation_level, 24)
            ticket.expected_response_time = f"PT{sla_hours}H"
            ticket.sla_expires_at = datetime.now(UTC) + timedelta(hours=sla_hours)
            ticket.updated_at = datetime.now(UTC)
            if reason:
                ticket.description += f"\n[Escalated to L{ticket.escalation_level}]: {reason}"
            await self.session.commit()
            logger.info("Escalated ticket %s to %s", ticket_id, ESCALATION_LEVELS.get(ticket.escalation_level))
        return ticket

    async def check_sla_timers(self) -> list[IgmTicket]:
        """Background job helper: find expired SLA tickets and escalate them automatically."""
        now = datetime.now(UTC)
        stmt = (
            select(IgmTicket)
            .where(
                IgmTicket.status.in_(["OPEN", "PROCESSING", "ESCALATED_L2"]),
                IgmTicket.sla_expires_at <= now,
                IgmTicket.escalation_level < 3,
            )
        )
        breached_tickets = (await self.session.scalars(stmt)).all()
        escalated: list[IgmTicket] = []
        for t in breached_tickets:
            res = await self.escalate_ticket(t.ticket_id, reason="SLA breach automated escalation")
            if res:
                escalated.append(res)
        return escalated

    async def resolve_ticket(
        self,
        ticket_id: str,
        resolution_notes: str,
        refund_amount_inr: int = 0,
    ) -> IgmTicket | None:
        """Resolve grievance ticket and unpause trade contract settlement."""
        stmt = select(IgmTicket).where(IgmTicket.ticket_id == ticket_id)
        ticket = (await self.session.scalars(stmt)).first()
        if not ticket:
            return None

        now = datetime.now(UTC)
        ticket.status = "RESOLVED"
        ticket.resolution_notes = resolution_notes
        ticket.refund_amount_inr = refund_amount_inr
        ticket.settlement_paused = False
        ticket.updated_at = now

        # Unpause settlement on trade contract
        contract_stmt = (
            update(TradeContract)
            .where(TradeContract.transaction_id == ticket.transaction_id)
            .values(settlement_hold=False, updated_at=now)
        )
        await self.session.execute(contract_stmt)
        await self.session.commit()

        logger.info("Resolved IGM ticket %s. Unpaused settlement on tx %s", ticket_id, ticket.transaction_id)
        return ticket

    async def get_ticket(self, ticket_id: str) -> IgmTicket | None:
        stmt = select(IgmTicket).where(IgmTicket.ticket_id == ticket_id)
        return (await self.session.scalars(stmt)).first()

    async def list_tickets(self, transaction_id: str | None = None) -> list[IgmTicket]:
        stmt = select(IgmTicket)
        if transaction_id:
            stmt = stmt.where(IgmTicket.transaction_id == transaction_id)
        stmt = stmt.order_by(IgmTicket.created_at.desc())
        return list((await self.session.scalars(stmt)).all())
