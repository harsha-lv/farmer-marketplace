"""Canonical event envelope, registered event types, topic configurations, and API schemas."""

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.events.models import OutboxEvent

# ---------------------------------------------------------------------------
# Registered Domain Event Types
# ---------------------------------------------------------------------------


class RegisteredEventType(str, Enum):
    LotCreated = "LotCreated"
    LotGraded = "LotGraded"
    AssayCompleted = "AssayCompleted"
    LotListed = "LotListed"
    LotWithdrawn = "LotWithdrawn"
    GateEntryCreated = "GateEntryCreated"
    EnwREIssued = "EnwREIssued"
    TradeContractIssued = "TradeContractIssued"
    TLCGenerated = "TLCGenerated"
    PaymentEscrowed = "PaymentEscrowed"
    PaymentSettled = "PaymentSettled"
    TdsDeducted = "TdsDeducted"
    ErupiVoucherIssued = "ErupiVoucherIssued"
    PledgeLoanDisbursed = "PledgeLoanDisbursed"
    ConsentGranted = "ConsentGranted"
    ConsentRevoked = "ConsentRevoked"
    DataErasureCompleted = "DataErasureCompleted"
    PriceObservationIngested = "PriceObservationIngested"
    ForecastPublished = "ForecastPublished"
    ShipmentStatusChanged = "ShipmentStatusChanged"
    GrievanceRaised = "GrievanceRaised"


# ---------------------------------------------------------------------------
# Topic Definitions and Retention Configurations
# ---------------------------------------------------------------------------

TOPIC_LOT_EVENTS = "agri.lot.events"
TOPIC_ASSAY_EVENTS = "agri.assay.events"
TOPIC_TRADE_EVENTS = "agri.trade.events"
TOPIC_SETTLEMENT_EVENTS = "agri.settlement.events"
TOPIC_CONSENT_EVENTS = "agri.consent.events"
TOPIC_PRICE_EVENTS = "agri.price.events"
TOPIC_SHIPMENT_EVENTS = "agri.shipment.events"
TOPIC_GRIEVANCE_EVENTS = "agri.grievance.events"
TOPIC_DLQ = "agri.dlq"

# Deprecated topic alias shims (Scheduled removal: 2026-12-31). Use canonical TOPIC_* constants above.
TOPIC_LOGISTICS_UPDATES = TOPIC_SHIPMENT_EVENTS
TOPIC_LOT_ASSAY_EVENTS = TOPIC_ASSAY_EVENTS
TOPIC_PRICE_DISCOVERY = TOPIC_PRICE_EVENTS


ALL_TOPICS = [
    TOPIC_LOT_EVENTS,
    TOPIC_ASSAY_EVENTS,
    TOPIC_TRADE_EVENTS,
    TOPIC_SETTLEMENT_EVENTS,
    TOPIC_CONSENT_EVENTS,
    TOPIC_PRICE_EVENTS,
    TOPIC_SHIPMENT_EVENTS,
    TOPIC_GRIEVANCE_EVENTS,
    TOPIC_DLQ,
]

# Event Type to Topic Routing Table
EVENT_TOPIC_MAP: dict[str, str] = {
    "LotCreated": TOPIC_LOT_EVENTS,
    "LotListed": TOPIC_LOT_EVENTS,
    "LotWithdrawn": TOPIC_LOT_EVENTS,
    "GateEntryCreated": TOPIC_LOT_EVENTS,
    "EnwREIssued": TOPIC_LOT_EVENTS,
    "LotGraded": TOPIC_ASSAY_EVENTS,
    "AssayCompleted": TOPIC_ASSAY_EVENTS,
    "TradeContractIssued": TOPIC_TRADE_EVENTS,
    "TLCGenerated": TOPIC_TRADE_EVENTS,
    "PaymentEscrowed": TOPIC_SETTLEMENT_EVENTS,
    "PaymentSettled": TOPIC_SETTLEMENT_EVENTS,
    "TdsDeducted": TOPIC_SETTLEMENT_EVENTS,
    "ErupiVoucherIssued": TOPIC_SETTLEMENT_EVENTS,
    "PledgeLoanDisbursed": TOPIC_SETTLEMENT_EVENTS,
    "ConsentGranted": TOPIC_CONSENT_EVENTS,
    "ConsentRevoked": TOPIC_CONSENT_EVENTS,
    "DataErasureCompleted": TOPIC_CONSENT_EVENTS,
    "PriceObservationIngested": TOPIC_PRICE_EVENTS,
    "ForecastPublished": TOPIC_PRICE_EVENTS,
    "ShipmentStatusChanged": TOPIC_SHIPMENT_EVENTS,
    "GrievanceRaised": TOPIC_GRIEVANCE_EVENTS,
}

# Retention mapping: 7 days default, 1 year for compliance (settlement & consent)
TOPIC_RETENTION_MS: dict[str, int] = {
    TOPIC_LOT_EVENTS: 604_800_000,          # 7 days
    TOPIC_ASSAY_EVENTS: 604_800_000,        # 7 days
    TOPIC_TRADE_EVENTS: 604_800_000,        # 7 days
    TOPIC_SETTLEMENT_EVENTS: 31_536_000_000, # 1 year compliance
    TOPIC_CONSENT_EVENTS: 31_536_000_000,    # 1 year compliance
    TOPIC_PRICE_EVENTS: 604_800_000,        # 7 days
    TOPIC_SHIPMENT_EVENTS: 604_800_000,     # 7 days
    TOPIC_GRIEVANCE_EVENTS: 604_800_000,    # 7 days
    TOPIC_DLQ: 604_800_000,                 # 7 days
}


def get_topic_for_event_type(event_type: str) -> str:
    """Resolve Kafka topic for an event type with fallback to generic domain or DLQ."""
    if event_type in EVENT_TOPIC_MAP:
        return EVENT_TOPIC_MAP[event_type]
    prefix = event_type.split(".")[0].lower() if "." in event_type else ""
    if not prefix:
        for candidate in ["trade", "lot", "settlement", "consent", "assay", "shipment", "price", "grievance"]:
            if event_type.lower().startswith(candidate):
                prefix = candidate
                break
    if prefix == "trade":
        return TOPIC_TRADE_EVENTS
    if prefix == "lot":
        return TOPIC_LOT_EVENTS
    if prefix == "settlement":
        return TOPIC_SETTLEMENT_EVENTS
    if prefix == "consent":
        return TOPIC_CONSENT_EVENTS
    if prefix == "assay":
        return TOPIC_ASSAY_EVENTS
    if prefix == "price":
        return TOPIC_PRICE_EVENTS
    if prefix == "shipment":
        return TOPIC_SHIPMENT_EVENTS
    if prefix == "grievance":
        return TOPIC_GRIEVANCE_EVENTS
    return TOPIC_DLQ


# ---------------------------------------------------------------------------
# Canonical Event Envelope (Pydantic v2)
# ---------------------------------------------------------------------------


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    event_id: UUID = Field(default_factory=uuid.uuid4)
    stream_id: str
    event_type: str
    event_version: int = 1
    occurred_at: datetime
    aggregate_type: str
    aggregate_id: str
    partition_key: str = Field(description="Must be aggregate_id to guarantee per-lot/per-contract ordering")
    payload: dict[str, Any]
    consent_artifact_id: str | None = None
    actor_id: str | None = None
    trace_id: str | None = None
    causation_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def set_envelope_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Guarantee partition_key is set to aggregate_id
            if "aggregate_id" in data and ("partition_key" not in data or not data["partition_key"]):
                data["partition_key"] = str(data["aggregate_id"])
            elif "partition_key" in data and ("aggregate_id" not in data or not data["aggregate_id"]):
                data["aggregate_id"] = str(data["partition_key"])

            if "occurred_at" not in data or not data["occurred_at"]:
                data["occurred_at"] = datetime.now(UTC)

            # Auto-convert string event_id to UUID
            if "event_id" in data and isinstance(data["event_id"], str):
                try:
                    data["event_id"] = UUID(data["event_id"])
                except ValueError:
                    data["event_id"] = uuid.uuid5(uuid.NAMESPACE_DNS, data["event_id"])
        return data

    def to_json_bytes(self) -> bytes:
        return self.model_dump_json().encode("utf-8")

    @classmethod
    def from_json_bytes(cls, raw: bytes) -> "EventEnvelope":
        return cls.model_validate_json(raw.decode("utf-8"))

    @classmethod
    def from_outbox(
        cls,
        outbox: OutboxEvent,
        actor_id: str | None = None,
        trace_id: str | None = None,
        causation_id: str | None = None,
    ) -> "EventEnvelope":
        """Convert a database OutboxEvent row into a canonical EventEnvelope."""
        # Derive aggregate_type and aggregate_id
        stream_id = outbox.stream_id or ""
        if ":" in stream_id:
            agg_type, agg_id = stream_id.split(":", 1)
        else:
            agg_type = "unknown"
            agg_id = outbox.partition_key or stream_id

        # Consent tagging: check payload if consent_artifact_id is present
        consent_id = outbox.consent_artifact_id
        if not consent_id and isinstance(outbox.payload, dict):
            consent_id = outbox.payload.get("consent_artifact_id")

        return cls(
            event_id=outbox.event_id,
            stream_id=outbox.stream_id,
            event_type=outbox.event_type,
            event_version=1,
            occurred_at=outbox.occurred_at,
            aggregate_type=agg_type,
            aggregate_id=agg_id,
            partition_key=agg_id,
            payload=outbox.payload,
            consent_artifact_id=consent_id,
            actor_id=actor_id or (outbox.payload.get("actor_id") if isinstance(outbox.payload, dict) else None),
            trace_id=trace_id or (outbox.payload.get("trace_id") if isinstance(outbox.payload, dict) else None),
            causation_id=causation_id,
        )


# ---------------------------------------------------------------------------
# API Schemas (Preserved for existing endpoints)
# ---------------------------------------------------------------------------


class EventResponse(BaseModel):
    event_id: str
    stream_id: str
    event_type: str
    partition_key: str
    payload: dict[str, Any]
    consent_artifact_id: str | None
    occurred_at: datetime
    published_at: datetime | None

    @classmethod
    def from_model(cls, event: OutboxEvent) -> "EventResponse":
        return cls(
            event_id=event.event_id,
            stream_id=event.stream_id,
            event_type=event.event_type,
            partition_key=event.partition_key,
            payload=event.payload,
            consent_artifact_id=event.consent_artifact_id,
            occurred_at=event.occurred_at,
            published_at=event.published_at,
        )


class EventListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    events: list[EventResponse]


class StreamReplayResponse(BaseModel):
    stream_id: str
    total_events: int
    events: list[EventResponse]


class PublishOutboxResponse(BaseModel):
    dispatched_count: int
    event_ids: list[str]


class ConsentAuditResponse(BaseModel):
    consent_artifact_id: str
    total_operations: int
    events: list[EventResponse]


class PointInTimeStateResponse(BaseModel):
    stream_id: str
    as_of: datetime | None
    total_events_applied: int
    state: dict[str, Any]
    state_hash: str


class ReplayRequest(BaseModel):
    stream_id: str | None = None
    event_types: list[str] | None = None
    from_time: datetime | None = None
    to_time: datetime | None = None
    dry_run: bool = True
    limit: int = Field(default=100, ge=1, le=1000)


class ReplayResponse(BaseModel):
    total_matched: int
    replayed_count: int
    dry_run: bool
    events: list[EventResponse]
    reconstructed_state: dict[str, Any] | None = None


class DivergenceItem(BaseModel):
    field: str
    reconstructed_value: Any
    projected_value: Any
    discrepancy_type: str  # VALUE_MISMATCH, MISSING_IN_PROJECTION, EXTRA_IN_PROJECTION


class AuditReconciliationReport(BaseModel):
    stream_id: str
    entity_type: str
    is_consistent: bool
    event_count: int
    divergences: list[DivergenceItem]
    reconstructed_state: dict[str, Any]
    current_projection_state: dict[str, Any] | None
    reconciliation_action: str  # NO_ACTION_REQUIRED, REPLAY_REQUIRED, MANUAL_INVESTIGATION
