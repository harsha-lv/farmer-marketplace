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
