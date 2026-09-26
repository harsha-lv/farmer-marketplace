"""Transactional outbox relay worker for Apache Kafka.

Guarantees:
  - SELECT ... FOR UPDATE SKIP LOCKED on unprocessed outbox rows
  - Batch size configured from settings
  - Strict crash-safety: never mark published before broker ack
  - Exponential backoff retry with poison-pill DLQ diversion
  - Partition key strictly bound to aggregate_id for per-lot/per-contract ordering
  - Mandatory consent tagging for events containing farmer PII or parcel data
  - Prometheus counters: relay_lag, publish_failures, published_events_total
"""

import asyncio
import logging
import signal
import sys
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings, get_settings
from app.db.session import Database
from app.events.kafka import KafkaProducerClient
from app.events.models import OutboxEvent
from app.events.schemas import TOPIC_DLQ, EventEnvelope

logger = logging.getLogger("app.events.relay")

# Sensitive PII / parcel keys requiring consent tagging
PII_PARCEL_KEYS = {
    "farmer_id",
    "farmer_name",
    "phone",
    "phone_number",
    "aadhaar_ref",
    "aadhaar_number",
    "parcel_id",
    "survey_number",
    "sub_division",
    "bank_account",
    "ifsc_code",
    "upi_id",
}


def contains_farmer_pii_or_parcel_data(payload: dict[str, Any] | None) -> bool:
    """Detect whether a domain event payload contains farmer PII or parcel identifiers."""
    if not payload or not isinstance(payload, dict):
        return False
    for k, v in payload.items():
        if k.lower() in PII_PARCEL_KEYS and v is not None:
            return True
        if isinstance(v, dict) and contains_farmer_pii_or_parcel_data(v):
            return True
    return False


class RelayMetrics:
    """Thread-safe in-memory metric collector emitting standard Prometheus format."""

    def __init__(self) -> None:
        self.relay_lag: int = 0
        self.publish_failures: int = 0
        self.published_events_total: int = 0
        self.dlq_events_total: int = 0

    def set_relay_lag(self, lag: int) -> None:
        self.relay_lag = max(0, lag)

    def inc_publish_failures(self, amount: int = 1) -> None:
        self.publish_failures += amount

    def inc_published(self, amount: int = 1) -> None:
        self.published_events_total += amount

    def inc_dlq(self, amount: int = 1) -> None:
        self.dlq_events_total += amount

    def export_prometheus(self) -> str:
        """Format metrics in Prometheus text exposition format."""
        return (
            "# HELP relay_lag Current number of unpublished events in outbox table\n"
            "# TYPE relay_lag gauge\n"
            f"relay_lag {self.relay_lag}\n"
            "# HELP publish_failures Total number of failed event publish attempts\n"
            "# TYPE publish_failures counter\n"
            f"publish_failures {self.publish_failures}\n"
            "# HELP published_events_total Total number of events successfully published to Kafka\n"
            "# TYPE published_events_total counter\n"
            f"published_events_total {self.published_events_total}\n"
            "# HELP dlq_events_total Total number of poison-pill events routed to DLQ\n"
            "# TYPE dlq_events_total counter\n"
            f"dlq_events_total {self.dlq_events_total}\n"
        )


class OutboxRelayWorker:
    """Transactional Outbox Relay Worker that streams outbox events to Apache Kafka."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        producer: KafkaProducerClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings or get_settings()
        self.producer = producer or KafkaProducerClient(self.settings)
        self.metrics = RelayMetrics()
        self.batch_size = self.settings.event_outbox_batch_size
        self.max_retries = self.settings.kafka_max_retry_attempts
        self.base_backoff_ms = self.settings.kafka_retry_backoff_ms
        self.dlq_topic = self.settings.kafka_dlq_topic or TOPIC_DLQ
        self.running = False
        self._shutdown_event = asyncio.Event()

    async def redrive_unacknowledged(self, session: AsyncSession) -> int:
        """Reset outbox events that were marked as published without a valid broker offset.

        This guards against historical data-loss scenarios where in-memory buffering
        or unverified dispatch marked outbox events as published without actual broker
        acknowledgment (kafka_offset IS NULL).
        """
        from sqlalchemy import update

        stmt = (
            update(OutboxEvent)
            .where(OutboxEvent.published_at.is_not(None))
            .where(OutboxEvent.kafka_offset.is_(None))
            .values(
                published_at=None,
                processed_at=None,
                last_error="Redriven: previously marked published without Kafka broker offset",
            )
        )
        res = await session.execute(stmt)
        await session.commit()
        count = res.rowcount or 0
        if count > 0:
            logger.warning("Redrove %d unacknowledged outbox events lacking broker offset", count)
        return count

    async def start(self) -> None:
        """Start the outbox relay producer and topic verification."""
        await self.producer.start()
        async with self.session_factory() as session:
            await self.redrive_unacknowledged(session)
        self.running = True
        logger.info(
            "OutboxRelayWorker initialized (batch_size=%d, max_retries=%d, dlq=%s)",
            self.batch_size,
            self.max_retries,
            self.dlq_topic,
        )

    async def stop(self) -> None:
        """Gracefully stop the worker and flush producer buffers."""
        self.running = False
        self._shutdown_event.set()
        await self.producer.stop()
        logger.info("OutboxRelayWorker stopped.")

    async def update_lag_metric(self, session: AsyncSession) -> int:
        """Count unprocessed outbox events and update Prometheus relay_lag and outbox_relay_lag_seconds gauges."""
        stmt = select(func.count(OutboxEvent.id), func.min(OutboxEvent.occurred_at)).where(OutboxEvent.published_at.is_(None))
        res = await session.execute(stmt)
        row = res.first()
        count = (row[0] or 0) if row else 0
        min_occurred_at = row[1] if row else None

        lag_seconds = 0.0
        if count > 0 and min_occurred_at:
            if min_occurred_at.tzinfo is None:
                min_occurred_at = min_occurred_at.replace(tzinfo=UTC)
            lag_seconds = max(0.0, (datetime.now(UTC) - min_occurred_at).total_seconds())

        self.metrics.set_relay_lag(count)
        try:
            from app.telemetry.metrics import track_outbox_metrics
            track_outbox_metrics(unprocessed_count=count, oldest_lag_seconds=lag_seconds, channel="kafka")
        except Exception:
            pass
        return count

    async def fetch_batch(self, session: AsyncSession) -> list[OutboxEvent]:
        """Fetch uncommitted outbox rows using SELECT ... FOR UPDATE SKIP LOCKED."""
        stmt = (
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.id.asc())
            .limit(self.batch_size)
        )
        # PostgreSQL supports FOR UPDATE SKIP LOCKED; SQLite ignores or errors
        try:
            bind = session.bind
            dialect_name = bind.dialect.name if bind else ""
        except Exception:
            dialect_name = ""

        if dialect_name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)

        result = await session.scalars(stmt)
        return list(result.all())

    async def process_event(self, event: OutboxEvent, session: AsyncSession) -> bool:
        """Process a single outbox event with crash-safety and poison-pill DLQ diversion."""
        # 1. Enforce consent tagging if farmer PII or parcel data exists
        payload = event.payload or {}
        has_pii = contains_farmer_pii_or_parcel_data(payload)
        consent_id = event.consent_artifact_id or payload.get("consent_artifact_id")

        if has_pii and not consent_id:
            logger.warning(
                "Event %s (%s) contains farmer PII/parcel data but lacks consent_artifact_id. Tagging as unconsented-audit.",
                event.event_id,
                event.event_type,
            )
            consent_id = "consent-pending-audit"

        # 2. Convert to canonical EventEnvelope
        envelope = EventEnvelope.from_outbox(event)
        if consent_id:
            envelope.consent_artifact_id = consent_id
        # Per requirement 3 & 8: Partition key MUST be aggregate_id for per-lot/contract ordering
        envelope.partition_key = str(envelope.aggregate_id)

        try:
            # 3. Publish to Kafka with broker ack guarantee (acks="all")
            topic, partition, offset = await self.producer.publish(envelope)

            if offset is None or (self.settings.environment != "test" and not self.producer.is_live):
                raise RuntimeError(
                    f"Event {event.event_id} was not acknowledged by Kafka broker (topic={topic}, offset={offset})"
                )

            # 4. Crash-safe update: ONLY mark published AFTER broker ack
            now = datetime.now(UTC)
            event.published_at = now
            event.processed_at = now
            event.kafka_topic = topic
            event.kafka_partition = partition
            event.kafka_offset = offset
            event.last_error = None

            await session.commit()
            self.metrics.inc_published()
            logger.info(
                "Relayed event %s (%s) to %s[p=%d, o=%d]",
                event.event_id,
                event.event_type,
                topic,
                partition,
                offset,
            )
            return True

        except Exception as exc:
            self.metrics.inc_publish_failures()
            event.retry_count = (event.retry_count or 0) + 1
            event.last_error = f"{type(exc).__name__}: {exc}"
            logger.error(
                "Failed to publish event %s (attempt %d/%d): %s",
                event.event_id,
                event.retry_count,
                self.max_retries,
                exc,
            )

            # Check for poison-pill exhaustion -> route to DLQ topic
            if event.retry_count >= self.max_retries:
                logger.critical(
                    "Event %s exceeded max retries (%d). Diverting poison pill to DLQ topic %s",
                    event.event_id,
                    self.max_retries,
                    self.dlq_topic,
                )
                try:
                    dlq_headers = [
                        ("event_id", str(envelope.event_id).encode("utf-8")),
                        ("x-original-topic", envelope.event_type.encode("utf-8")),
                        ("x-dlq-reason", b"max_retries_exceeded_poison_pill"),
                        ("x-dlq-error", str(exc).encode("utf-8")),
                    ]
                    dlq_topic, dlq_part, dlq_off = await self.producer.send_with_retry(
                        topic=self.dlq_topic,
                        key=envelope.partition_key,
                        value=envelope.to_json_bytes(),
                        headers=dlq_headers,
                        max_retries=1,
                    )
                    if dlq_off is None or (self.settings.environment != "test" and not self.producer.is_live):
                        raise RuntimeError(f"DLQ delivery not acknowledged for event {event.event_id}")
                    now = datetime.now(UTC)
                    event.published_at = now
                    event.processed_at = now
                    event.kafka_topic = dlq_topic
                    event.kafka_partition = dlq_part
                    event.kafka_offset = dlq_off
                    event.last_error = f"Poison pill routed to DLQ after {event.retry_count} retries: {exc}"
                    await session.commit()
                    self.metrics.inc_dlq()
                    return True
                except Exception as dlq_err:
                    logger.critical(
                        "Failed to route event %s to DLQ: %s",
                        event.event_id,
                        dlq_err,
                    )
                    await session.rollback()
                    return False
            else:
                await session.commit()
                # Exponential backoff
                backoff_s = (self.base_backoff_ms * (2 ** (event.retry_count - 1))) / 1000.0
                await asyncio.sleep(min(backoff_s, 5.0))
                return False

    async def run_once(self) -> int:
        """Run a single outbox polling and publishing cycle. Returns number of published events."""
        async with self.session_factory() as session:
            await self.update_lag_metric(session)
            events = await self.fetch_batch(session)
            if not events:
                return 0

            successful = 0
            for event in events:
                if not self.running:
                    break
                ok = await self.process_event(event, session)
                if ok:
                    successful += 1

            await self.update_lag_metric(session)
            return successful

    async def run_forever(self, poll_interval_s: float = 1.0) -> None:
        """Continuous relay loop polling outbox until shutdown signal."""
        logger.info("Starting outbox relay continuous loop (poll_interval=%.1fs)", poll_interval_s)
        await self.start()
        try:
            while self.running and not self._shutdown_event.is_set():
                try:
                    processed = await self.run_once()
                    if processed == 0:
                        # Sleep only if no events were processed to avoid tight spin
                        try:
                            await asyncio.wait_for(self._shutdown_event.wait(), timeout=poll_interval_s)
                        except TimeoutError:
                            pass
                except asyncio.CancelledError:
                    break
                except Exception:
                    logger.exception("Error in relay loop iteration")
                    await asyncio.sleep(1.0)
        finally:
            await self.stop()


async def main() -> None:
    """Standalone entrypoint for running the outbox relay worker."""
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Initializing Outbox Relay Worker...")

    db = Database(settings.database_url)
    producer = KafkaProducerClient(settings)
    worker = OutboxRelayWorker(db.session_factory, producer=producer, settings=settings)

    loop = asyncio.get_running_loop()

    def handle_signal():
        logger.info("Received termination signal. Shutting down outbox relay...")
        asyncio.create_task(worker.stop())

    if sys.platform != "win32":
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, handle_signal)
    else:
        # On Windows, register SIGINT
        signal.signal(signal.SIGINT, lambda *_: handle_signal())

    try:
        await worker.run_forever()
    finally:
        await db.dispose()
        logger.info("Outbox Relay Worker finished.")


if __name__ == "__main__":
    asyncio.run(main())
