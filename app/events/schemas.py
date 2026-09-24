from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.events.models import OutboxEvent


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

