from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_outbox_events_event_id"),
        Index("ix_app_outbox_events_event_id", "event_id"),
        Index("ix_app_outbox_events_stream_id", "stream_id"),
        Index("ix_app_outbox_events_event_type", "event_type"),
        Index("ix_app_outbox_events_partition_key", "partition_key"),
        Index("ix_app_outbox_events_consent_artifact_id", "consent_artifact_id"),
        Index("ix_app_outbox_events_occurred_at", "occurred_at"),
        Index("ix_app_outbox_events_published_at", "published_at"),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), Identity(), autoincrement=True, primary_key=True
    )
    event_id: Mapped[str] = mapped_column(String(64))
    stream_id: Mapped[str] = mapped_column(String(128))
    event_type: Mapped[str] = mapped_column(String(64))
    partition_key: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    consent_artifact_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    kafka_topic: Mapped[str | None] = mapped_column(String(128), nullable=True)
    kafka_partition: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kafka_offset: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), nullable=True
    )
    retry_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProcessedEvent(Base):
    """Consumer idempotency registry table ensuring exactly-once processing per consumer group."""
    __tablename__ = "processed_events"
    __table_args__ = (
        UniqueConstraint("consumer_group", "event_id", name="uq_processed_events_group_event"),
        Index("ix_processed_events_event_id", "event_id"),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), Identity(), autoincrement=True, primary_key=True
    )
    consumer_group: Mapped[str] = mapped_column(String(64), nullable=False)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
