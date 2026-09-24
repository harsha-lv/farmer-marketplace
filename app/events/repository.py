from datetime import UTC, datetime
from typing import Any
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.events.models import OutboxEvent


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_event(
        self,
        *,
        event_type: str,
        stream_id: str,
        partition_key: str,
        payload: dict[str, Any],
        consent_artifact_id: str | None = None,
        occurred_at: datetime | None = None,
    ) -> OutboxEvent:
        now = occurred_at or datetime.now(UTC)
        event_id = f"evt_{uuid.uuid4().hex}"
        event = OutboxEvent(
            event_id=event_id,
            stream_id=stream_id,
            event_type=event_type,
            partition_key=partition_key,
            payload=payload,
            consent_artifact_id=consent_artifact_id,
            occurred_at=now,
            published_at=None,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def fetch_pending(self, limit: int = 100) -> list[OutboxEvent]:
        statement = (
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.id.asc())
            .limit(limit)
        )
        result = await self.session.scalars(statement)
        return list(result.all())

    async def mark_published(self, event_ids: list[str]) -> int:
        if not event_ids:
            return 0
        now = datetime.now(UTC)
        statement = (
            update(OutboxEvent)
            .where(OutboxEvent.event_id.in_(event_ids))
            .values(published_at=now)
        )
        result = await self.session.execute(statement)
        await self.session.flush()
        return result.rowcount

    async def get_stream(self, stream_id: str) -> list[OutboxEvent]:
        statement = (
            select(OutboxEvent)
            .where(OutboxEvent.stream_id == stream_id)
            .order_by(OutboxEvent.id.asc())
        )
        result = await self.session.scalars(statement)
        return list(result.all())

    async def get_by_consent(self, consent_artifact_id: str) -> list[OutboxEvent]:
        statement = (
            select(OutboxEvent)
            .where(OutboxEvent.consent_artifact_id == consent_artifact_id)
            .order_by(OutboxEvent.id.asc())
        )
        result = await self.session.scalars(statement)
        return list(result.all())

    async def query_events(
        self,
        *,
        event_type: str | None = None,
        stream_id: str | None = None,
        consent_artifact_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[OutboxEvent], int]:
        filters = []
        if event_type:
            filters.append(OutboxEvent.event_type == event_type)
        if stream_id:
            filters.append(OutboxEvent.stream_id == stream_id)
        if consent_artifact_id:
            filters.append(OutboxEvent.consent_artifact_id == consent_artifact_id)

        count_statement = select(func.count(OutboxEvent.id))
        if filters:
            count_statement = count_statement.where(*filters)
        total = await self.session.scalar(count_statement) or 0

        query_statement = select(OutboxEvent)
        if filters:
            query_statement = query_statement.where(*filters)
        query_statement = query_statement.order_by(OutboxEvent.id.desc()).offset(offset).limit(limit)

        result = await self.session.scalars(query_statement)
        return list(result.all()), total
