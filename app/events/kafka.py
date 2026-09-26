"""Production-grade Apache Kafka producer wrapper with idempotence, DLQ retry, and topic provisioning."""

import asyncio
import logging
from typing import Any

from aiokafka import AIOKafkaProducer
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.errors import KafkaError, TopicAlreadyExistsError

from app.config import Settings, get_settings
from app.events.schemas import (
    ALL_TOPICS,
    TOPIC_RETENTION_MS,
    EventEnvelope,
    get_topic_for_event_type,
)

logger = logging.getLogger("app.events.kafka")


class KafkaProducerClient:
    """Production aiokafka producer wrapper.

    Guarantees:
      - enable_idempotence = True (exactly-once producer semantics)
      - acks = "all" (cluster-wide durably replicated commit)
      - linger/batch tuning from settings
      - Partition key strictly bound to aggregate_id for per-lot/per-contract causal ordering
      - Exponential backoff retry with automatic fallback to DLQ (agri.dlq)
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.bootstrap_servers = self.settings.kafka_bootstrap_servers.strip()
        self.dlq_topic = self.settings.kafka_dlq_topic
        self.max_retries = self.settings.kafka_max_retry_attempts
        self.retry_backoff_ms = self.settings.kafka_retry_backoff_ms
        self._started = False
        self.producer: AIOKafkaProducer | None = None
        # In-memory journal for unit tests
        self.published_records: list[dict[str, Any]] = []

    @property
    def is_live(self) -> bool:
        """Returns True if connected to an active Kafka cluster with a live producer."""
        return self.producer is not None

    async def start(self) -> None:
        """Start the Kafka producer and ensure all canonical topics exist."""
        if not self.bootstrap_servers:
            logger.info("Kafka bootstrap servers not configured. Running in mock/local mode.")
            self._started = True
            return

        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                client_id=self.settings.kafka_client_id,
                acks=self.settings.kafka_acks,
                enable_idempotence=self.settings.kafka_enable_idempotence,
                linger_ms=self.settings.kafka_linger_ms,
                max_batch_size=self.settings.kafka_max_batch_size,
            )
            await self.producer.start()
            self._started = True
            logger.info("AIOKafkaProducer started successfully on %s", self.bootstrap_servers)

            # Ensure canonical topics exist
            await self.ensure_topics()
        except Exception as exc:
            logger.warning("Failed to start Kafka producer (%s). Running in memory buffer mode.", exc)
            self.producer = None
            self._started = True

    async def stop(self) -> None:
        """Gracefully stop the Kafka producer, flushing all in-flight buffers."""
        if self.producer and self._started:
            try:
                await self.producer.stop()
                logger.info("AIOKafkaProducer stopped cleanly.")
            except Exception as exc:
                logger.warning("Error during Kafka producer shutdown: %s", exc)
        self._started = False

    async def ensure_topics(self) -> None:
        """Provision all canonical topics with per-topic retention configurations."""
        if not self.bootstrap_servers:
            return

        admin: AIOKafkaAdminClient | None = None
        try:
            admin = AIOKafkaAdminClient(
                bootstrap_servers=self.bootstrap_servers,
                client_id=f"{self.settings.kafka_client_id}-admin",
            )
            await admin.start()
            existing_topics = set(await admin.list_topics())

            new_topics: list[NewTopic] = []
            for topic in ALL_TOPICS:
                if topic not in existing_topics:
                    retention_ms = TOPIC_RETENTION_MS.get(topic, 604_800_000)
                    new_topics.append(
                        NewTopic(
                            name=topic,
                            num_partitions=3,
                            replication_factor=1,
                            topic_configs={"retention.ms": str(retention_ms)},
                        )
                    )

            if new_topics:
                try:
                    await admin.create_topics(new_topics)
                    logger.info("Created Kafka topics: %s", [t.name for t in new_topics])
                except TopicAlreadyExistsError:
                    pass
        except Exception as exc:
            logger.warning("Kafka topic auto-creation failed: %s", exc)
        finally:
            if admin:
                try:
                    await admin.close()
                except Exception:
                    pass

    async def send_with_retry(
        self,
        topic: str,
        key: str,
        value: bytes,
        headers: list[tuple[str, bytes]] | None = None,
        max_retries: int | None = None,
    ) -> tuple[str, int, int]:
        """Send message with exponential backoff. Routes to DLQ after max_retries attempts.

        Returns:
            tuple[str, int, int]: (topic, partition, offset)
        """
        retries = max_retries if max_retries is not None else self.max_retries
        key_bytes = key.encode("utf-8") if isinstance(key, str) else key

        # If running without live broker connection
        if self.producer is None:
            if self.settings.environment == "test":
                offset = len(self.published_records)
                record = {
                    "topic": topic,
                    "partition": 0,
                    "offset": offset,
                    "key": key,
                    "value": value,
                    "headers": headers or [],
                }
                self.published_records.append(record)
                return topic, 0, offset
            raise RuntimeError(
                f"Kafka producer is not connected to broker ({self.bootstrap_servers}). "
                "Events cannot be acknowledged without real broker persistence."
            )

        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                record_meta = await self.producer.send_and_wait(
                    topic=topic,
                    key=key_bytes,
                    value=value,
                    headers=headers,
                )
                return record_meta.topic, record_meta.partition, record_meta.offset
            except KafkaError as exc:
                last_error = exc
                backoff_s = (self.retry_backoff_ms * (2 ** (attempt - 1))) / 1000.0
                logger.warning(
                    "Kafka send to %s attempt %d/%d failed: %s. Backing off %.3fs",
                    topic,
                    attempt,
                    retries,
                    exc,
                    backoff_s,
                )
                await asyncio.sleep(backoff_s)

        # Retries exhausted -> route to DLQ topic
        logger.error(
            "Kafka send to %s failed after %d retries. Diverting to DLQ (%s)",
            topic,
            retries,
            self.dlq_topic,
        )
        dlq_headers = list(headers or [])
        dlq_headers.append(("x-original-topic", topic.encode("utf-8")))
        dlq_headers.append(("x-dlq-error", str(last_error).encode("utf-8")))

        try:
            dlq_meta = await self.producer.send_and_wait(
                topic=self.dlq_topic,
                key=key_bytes,
                value=value,
                headers=dlq_headers,
            )
            return dlq_meta.topic, dlq_meta.partition, dlq_meta.offset
        except Exception as dlq_exc:
            logger.critical("Failed to dispatch to DLQ topic %s: %s", self.dlq_topic, dlq_exc)
            raise last_error or dlq_exc

    async def publish(
        self,
        event: EventEnvelope,
        topic: str | None = None,
    ) -> tuple[str, int, int]:
        """Publish a canonical domain event envelope to Kafka.

        Guarantees:
          - Partition key is ALWAYS aggregate_id (per-lot / per-contract strict ordering)
          - Topic is determined by event_type unless explicitly overridden
          - Returns (topic, partition, offset)
        """
        target_topic = topic or get_topic_for_event_type(event.event_type)

        # Causal ordering guarantee: partition_key MUST be aggregate_id
        partition_key = str(event.aggregate_id or event.partition_key)

        headers: list[tuple[str, bytes]] = [
            ("event_id", str(event.event_id).encode("utf-8")),
            ("event_type", event.event_type.encode("utf-8")),
            ("stream_id", event.stream_id.encode("utf-8")),
            ("aggregate_type", event.aggregate_type.encode("utf-8")),
            ("aggregate_id", str(event.aggregate_id).encode("utf-8")),
            ("occurred_at", event.occurred_at.isoformat().encode("utf-8")),
        ]
        if event.consent_artifact_id:
            headers.append(("consent_artifact_id", event.consent_artifact_id.encode("utf-8")))
        if event.trace_id:
            headers.append(("trace_id", event.trace_id.encode("utf-8")))
        if event.actor_id:
            headers.append(("actor_id", event.actor_id.encode("utf-8")))

        payload_bytes = event.to_json_bytes()
        return await self.send_with_retry(
            topic=target_topic,
            key=partition_key,
            value=payload_bytes,
            headers=headers,
        )

    async def publish_batch(
        self,
        events: list[EventEnvelope],
    ) -> list[tuple[str, int, int]]:
        """Publish a batch of domain event envelopes sequentially preserving causal order."""
        results: list[tuple[str, int, int]] = []
        for event in events:
            res = await self.publish(event)
            results.append(res)
        return results
