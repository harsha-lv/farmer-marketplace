"""Base idempotent Kafka consumer with manual offset commit, dedup, and DLQ routing.

Guarantees:
  - Idempotent deduplication by event_id in PostgreSQL `app.processed_events` (or Redis)
  - Consumer group isolation per service
  - Strict manual commit ONLY after successful event handling and db transaction commit
  - Automatic poison-pill diversion to DLQ (`agri.dlq`) after max retry attempts
  - Consent revocation / data erasure hooks for downstream projection purging
  - Graceful shutdown handling on SIGTERM and SIGINT
"""

import asyncio
import logging
import signal
import sys
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from aiokafka import AIOKafkaConsumer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings, get_settings
from app.events.kafka import KafkaProducerClient
from app.events.models import ProcessedEvent
from app.events.schemas import (
    TOPIC_DLQ,
    EventEnvelope,
    RegisteredEventType,
)

logger = logging.getLogger("app.events.consumers")

EventHandler = Callable[[EventEnvelope, AsyncSession], Awaitable[None]]


class BaseIdempotentEventConsumer:
    """Base idempotent consumer guaranteeing exactly-once message handling semantics."""

    def __init__(
        self,
        topics: list[str] | str,
        group_id: str,
        session_factory: async_sessionmaker[AsyncSession],
        handler: EventHandler | None = None,
        settings: Settings | None = None,
        producer: KafkaProducerClient | None = None,
    ) -> None:
        self.topics = [topics] if isinstance(topics, str) else list(topics)
        self.group_id = group_id
        self.session_factory = session_factory
        self.handler = handler
        self.settings = settings or get_settings()
        self.producer = producer or KafkaProducerClient(self.settings)
        self.dlq_topic = self.settings.kafka_dlq_topic or TOPIC_DLQ
        self.max_retries = self.settings.kafka_max_retry_attempts
        self.base_backoff_ms = self.settings.kafka_retry_backoff_ms
        self.consumer: AIOKafkaConsumer | None = None
        self.running = False
        self._shutdown_event = asyncio.Event()
        self._retry_tracker: dict[str, int] = {}
        # Optional Redis client if redis_url is configured
        self._redis_client: Any = None

    async def _init_redis_if_configured(self) -> None:
        if self.settings.redis_url and not self._redis_client:
            try:
                import redis.asyncio as aioredis
                self._redis_client = aioredis.from_url(self.settings.redis_url, decode_responses=True)
                logger.info("Connected to Redis for consumer deduplication cache.")
            except Exception as exc:
                logger.warning("Redis configured at %s but connection failed (%s); using PostgreSQL.", self.settings.redis_url, exc)
                self._redis_client = None

    async def is_processed(self, session: AsyncSession, event_id: str) -> bool:
        """Check if an event has already been processed by this consumer group."""
        cache_key = f"processed:{self.group_id}:{event_id}"
        if self._redis_client:
            try:
                val = await self._redis_client.get(cache_key)
                if val:
                    return True
            except Exception:
                pass

        stmt = select(ProcessedEvent.id).where(
            ProcessedEvent.consumer_group == self.group_id,
            ProcessedEvent.event_id == event_id,
        )
        row = await session.scalar(stmt)
        return row is not None

    async def mark_processed(self, session: AsyncSession, event_id: str) -> None:
        """Record processed event in deduplication table and cache."""
        record = ProcessedEvent(
            consumer_group=self.group_id,
            event_id=event_id,
            processed_at=datetime.now(UTC),
        )
        session.add(record)
        await session.flush()

        if self._redis_client:
            try:
                cache_key = f"processed:{self.group_id}:{event_id}"
                await self._redis_client.setex(cache_key, 604_800, "1")  # 7 days TTL
            except Exception:
                pass

    async def start(self) -> None:
        """Initialize consumer, connect to Kafka broker, and start producer for DLQ."""
        await self._init_redis_if_configured()
        await self.producer.start()

        if self.settings.kafka_bootstrap_servers:
            try:
                self.consumer = AIOKafkaConsumer(
                    *self.topics,
                    bootstrap_servers=self.settings.kafka_bootstrap_servers,
                    group_id=self.group_id,
                    enable_auto_commit=False,  # Strict manual commit after processing
                    auto_offset_reset="earliest",
                    client_id=f"{self.group_id}-{self.settings.kafka_client_id}",
                )
                await self.consumer.start()
                logger.info("AIOKafkaConsumer connected for group '%s' on topics: %s", self.group_id, self.topics)
            except Exception as exc:
                logger.warning("Failed to start AIOKafkaConsumer (%s). Consumer will run in mock mode.", exc)
                self.consumer = None
        else:
            logger.info("Kafka bootstrap servers not configured. Consumer running in mock mode.")

        self.running = True

    async def stop(self) -> None:
        """Gracefully stop consumer and flush producer."""
        self.running = False
        self._shutdown_event.set()
        if self.consumer:
            try:
                await self.consumer.stop()
                logger.info("AIOKafkaConsumer cleanly stopped.")
            except Exception as exc:
                logger.warning("Error stopping Kafka consumer: %s", exc)
        if self.producer:
            await self.producer.stop()
        if self._redis_client:
            try:
                await self._redis_client.aclose()
            except Exception:
                pass

    async def handle_consent_revocation(self, envelope: EventEnvelope, session: AsyncSession) -> None:
        """Hook called when ConsentRevoked or DataErasureCompleted event is received.

        Downstream projection models purge farmer PII, parcel caches, and local projections.
        """
        logger.warning(
            "Consent revocation/erasure event received (%s, stream=%s, consent_artifact=%s). Triggering projection purge.",
            envelope.event_type,
            envelope.stream_id,
            envelope.consent_artifact_id,
        )
        try:
            from app.cache.hooks import on_consent_revoked
            farmer_id = (envelope.payload or {}).get("farmer_id") or envelope.aggregate_id
            await on_consent_revoked(farmer_id=str(farmer_id), consent_artifact_id=envelope.consent_artifact_id)
        except Exception as cache_err:
            logger.warning("Cache invalidation hook error during consent revocation: %s", cache_err)

    async def _trigger_domain_cache_invalidation(self, envelope: EventEnvelope) -> None:
        """Dispatch domain cache invalidation hooks based on event type."""
        try:
            from app.cache.hooks import (
                on_assay_report_created,
                on_contract_state_changed,
                on_lot_status_changed,
                on_price_observation_ingested,
            )
            payload = envelope.payload or {}
            event_type = envelope.event_type

            if event_type in ("LotListed", "LotWithdrawn", "GateEntryCreated", "LotCreated"):
                lot_code = payload.get("lot_code")
                await on_lot_status_changed(lot_id=envelope.aggregate_id, lot_code=lot_code)
            elif event_type in ("TradeContractIssued", "TLCGenerated", "PaymentSettled"):
                lot_id = payload.get("lot_id") or payload.get("lot_code")
                await on_contract_state_changed(contract_id=envelope.aggregate_id, lot_id=lot_id)
            elif event_type in ("PriceObservationIngested", "ForecastPublished"):
                market_id = payload.get("market_id") or payload.get("mandi_code") or envelope.aggregate_id
                commodity = payload.get("commodity")
                await on_price_observation_ingested(market_id=str(market_id), commodity=commodity)
            elif event_type in ("AssayCompleted", "LotGraded"):
                lot_id = payload.get("lot_id") or envelope.aggregate_id
                await on_assay_report_created(lot_id=str(lot_id))
        except Exception as hook_err:
            logger.warning("Cache invalidation hook error for %s: %s", envelope.event_type, hook_err)

    async def handle_event(self, envelope: EventEnvelope, session: AsyncSession) -> None:
        """Core event business logic hook. Override in subclass or supply via handler callback."""
        await self._trigger_domain_cache_invalidation(envelope)
        if self.handler:
            await self.handler(envelope, session)
        else:
            logger.info(
                "Consumer '%s' handled event %s [%s]",
                self.group_id,
                envelope.event_id,
                envelope.event_type,
            )

    async def process_envelope(self, envelope: EventEnvelope) -> bool:
        """Process an event envelope idempotently with retry and DLQ diversion."""
        event_id_str = str(envelope.event_id)

        # 1. Deduplication check
        async with self.session_factory() as session:
            if await self.is_processed(session, event_id_str):
                logger.info(
                    "Duplicate event %s already processed by consumer group '%s'. Skipping.",
                    event_id_str,
                    self.group_id,
                )
                # Commit offset to advance past duplicate
                if self.consumer:
                    await self.consumer.commit()
                return True

        # 2. Check for consent revocation or data erasure event (Requirement 8)
        if envelope.event_type in (
            RegisteredEventType.ConsentRevoked.value,
            RegisteredEventType.DataErasureCompleted.value,
            "ConsentRevoked",
            "DataErasureCompleted",
        ):
            async with self.session_factory() as session:
                try:
                    await self.handle_consent_revocation(envelope, session)
                    await session.commit()
                except Exception as rev_err:
                    logger.error("Error during consent revocation hook: %s", rev_err)

        # 3. Invoke business handler
        attempt = self._retry_tracker.get(event_id_str, 0) + 1
        self._retry_tracker[event_id_str] = attempt

        async with self.session_factory() as session:
            try:
                await self.handle_event(envelope, session)
                # Record in processed_events table
                await self.mark_processed(session, event_id_str)
                await session.commit()

                # Manual commit after successful handling
                if self.consumer:
                    await self.consumer.commit()

                self._retry_tracker.pop(event_id_str, None)
                return True

            except Exception as exc:
                await session.rollback()
                logger.error(
                    "Handler error for event %s (attempt %d/%d): %s",
                    event_id_str,
                    attempt,
                    self.max_retries,
                    exc,
                )

                if attempt >= self.max_retries:
                    logger.critical(
                        "Consumer group '%s' exceeded max retries for event %s. Diverting to DLQ (%s)",
                        self.group_id,
                        event_id_str,
                        self.dlq_topic,
                    )
                    try:
                        dlq_headers = [
                            ("event_id", event_id_str.encode("utf-8")),
                            ("x-consumer-group", self.group_id.encode("utf-8")),
                            ("x-original-topic", envelope.event_type.encode("utf-8")),
                            ("x-dlq-error", str(exc).encode("utf-8")),
                        ]
                        await self.producer.send_with_retry(
                            topic=self.dlq_topic,
                            key=envelope.partition_key,
                            value=envelope.to_json_bytes(),
                            headers=dlq_headers,
                            max_retries=1,
                        )
                        # Commit offset so consumer does not block on poison pill
                        if self.consumer:
                            await self.consumer.commit()
                        self._retry_tracker.pop(event_id_str, None)
                        return True
                    except Exception as dlq_err:
                        logger.critical("Failed to route to DLQ topic: %s", dlq_err)
                        raise exc
                else:
                    backoff_s = (self.base_backoff_ms * (2 ** (attempt - 1))) / 1000.0
                    await asyncio.sleep(min(backoff_s, 5.0))
                    raise exc

    async def run_forever(self) -> None:
        """Poll Kafka consumer loop until shutdown."""
        await self.start()
        if not self.consumer:
            logger.info("No active Kafka consumer connection. Consumer run_forever idle.")
            await self._shutdown_event.wait()
            return

        try:
            while self.running and not self._shutdown_event.is_set():
                try:
                    # Poll for messages with 1s timeout
                    msg_dict = await self.consumer.getmany(timeout_ms=1000, max_records=10)
                    for tp, messages in msg_dict.items():
                        if messages and self.consumer:
                            try:
                                from app.telemetry.metrics import track_kafka_lag
                                highwater = self.consumer.highwater(tp)
                                if highwater is not None:
                                    last_offset = messages[-1].offset
                                    lag = max(0, highwater - last_offset - 1)
                                    track_kafka_lag(topic=tp.topic, partition=tp.partition, consumer_group=self.group_id, lag=lag)
                            except Exception:
                                pass
                        for msg in messages:
                            if not self.running:
                                break
                            try:
                                envelope = EventEnvelope.from_json_bytes(msg.value)
                                await self.process_envelope(envelope)
                            except Exception as parse_err:
                                logger.error("Failed to process message offset %d: %s", msg.offset, parse_err)
                except asyncio.CancelledError:
                    break
                except Exception:
                    logger.exception("Consumer loop exception")
                    await asyncio.sleep(1.0)
        finally:
            await self.stop()

    def register_signal_handlers(self) -> None:
        """Attach graceful shutdown signals to running loop."""
        loop = asyncio.get_running_loop()

        def _stop():
            logger.info("Received termination signal. Shutting down consumer...")
            asyncio.create_task(self.stop())

        if sys.platform != "win32":
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, _stop)
        else:
            signal.signal(signal.SIGINT, lambda *_: _stop())
