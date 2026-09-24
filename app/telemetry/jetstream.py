import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import json
import logging
from typing import Any
import uuid

from app.telemetry.schemas import FpoStreamInfo

logger = logging.getLogger("app.telemetry.jetstream")


@dataclass
class JetStreamStreamConfig:
    stream_name: str
    fpo_id: str
    subjects: list[str]
    max_messages: int = 100_000
    max_bytes: int = 104_857_600
    max_age_seconds: int = 604_800
    duplicate_window_seconds: int = 120
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class JetStreamMessage:
    stream: str
    seq: int
    subject: str
    headers: dict[str, str]
    payload: dict[str, Any]
    msg_id: str
    timestamp: datetime
    acked: bool = False
    nacked: bool = False
    terminated: bool = False

    def ack(self) -> None:
        self.acked = True

    def nak(self) -> None:
        self.nacked = True

    def term(self) -> None:
        self.terminated = True


class JetStreamConsumer:
    def __init__(
        self,
        durable_name: str,
        stream_name: str,
        subject_filter: str,
        engine: "NatsJetStreamEngine",
    ) -> None:
        self.durable_name = durable_name
        self.stream_name = stream_name
        self.subject_filter = subject_filter
        self.engine = engine
        self.cursor_seq = 0

    def fetch(self, batch_size: int = 10) -> list[JetStreamMessage]:
        messages = self.engine.get_messages_for_consumer(
            stream_name=self.stream_name,
            subject_filter=self.subject_filter,
            start_seq=self.cursor_seq + 1,
            limit=batch_size,
        )
        if messages:
            self.cursor_seq = messages[-1].seq
        return messages


class NatsJetStreamEngine:
    """
    High-Throughput NATS JetStream Engine providing multi-tenant isolated
    ordered streams per active FPO / edge device without cluster rebalancing overhead.
    """

    def __init__(
        self,
        default_max_messages: int = 100_000,
        default_max_bytes: int = 104_857_600,
        default_max_age_seconds: int = 604_800,
        default_dedup_window_seconds: int = 120,
    ) -> None:
        self.default_max_messages = default_max_messages
        self.default_max_bytes = default_max_bytes
        self.default_max_age_seconds = default_max_age_seconds
        self.default_dedup_window_seconds = default_dedup_window_seconds

        self._streams: dict[str, JetStreamStreamConfig] = {}
        self._messages: dict[str, list[JetStreamMessage]] = {}
        self._dedup_cache: dict[tuple[str, str], tuple[JetStreamMessage, datetime]] = {}
        self._consumers: dict[str, list[JetStreamConsumer]] = {}
        self._lock = asyncio.Lock()

    def _normalize_stream_name(self, fpo_id: str) -> str:
        clean = fpo_id.upper().replace("-", "_").replace(".", "_")
        return f"FPO_{clean}"

    async def provision_fpo_stream(
        self,
        fpo_id: str,
        *,
        max_messages: int | None = None,
        max_bytes: int | None = None,
        max_age_seconds: int | None = None,
        duplicate_window_seconds: int | None = None,
    ) -> JetStreamStreamConfig:
        async with self._lock:
            stream_name = self._normalize_stream_name(fpo_id)
            config = JetStreamStreamConfig(
                stream_name=stream_name,
                fpo_id=fpo_id,
                subjects=[f"fpo.{fpo_id}.>"],
                max_messages=max_messages or self.default_max_messages,
                max_bytes=max_bytes or self.default_max_bytes,
                max_age_seconds=max_age_seconds or self.default_max_age_seconds,
                duplicate_window_seconds=duplicate_window_seconds or self.default_dedup_window_seconds,
            )
            self._streams[stream_name] = config
            if stream_name not in self._messages:
                self._messages[stream_name] = []
            if stream_name not in self._consumers:
                self._consumers[stream_name] = []
            logger.info("Provisioned isolated JetStream stream %s for FPO %s", stream_name, fpo_id)
            return config

    def _match_stream_for_subject(self, subject: str) -> JetStreamStreamConfig | None:
        # Subject pattern fpo.<fpo_id>.<subtopic>
        parts = subject.split(".")
        if len(parts) >= 2 and parts[0] == "fpo":
            fpo_id = parts[1]
            stream_name = self._normalize_stream_name(fpo_id)
            if stream_name in self._streams:
                return self._streams[stream_name]
        # Fallback check registered subjects
        for config in self._streams.values():
            for s in config.subjects:
                prefix = s.rstrip(".>")
                if subject == prefix or subject.startswith(f"{prefix}."):
                    return config
        return None

    async def publish(
        self,
        subject: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
        msg_id: str | None = None,
    ) -> JetStreamMessage:
        async with self._lock:
            config = self._match_stream_for_subject(subject)
            if config is None:
                # Auto-provision on first publish
                parts = subject.split(".")
                fpo_id = parts[1] if len(parts) >= 2 and parts[0] == "fpo" else "DEFAULT"
                stream_name = self._normalize_stream_name(fpo_id)
                config = JetStreamStreamConfig(
                    stream_name=stream_name,
                    fpo_id=fpo_id,
                    subjects=[f"fpo.{fpo_id}.>"],
                    max_messages=self.default_max_messages,
                    max_bytes=self.default_max_bytes,
                    max_age_seconds=self.default_max_age_seconds,
                    duplicate_window_seconds=self.default_dedup_window_seconds,
                )
                self._streams[stream_name] = config
                self._messages[stream_name] = []
                self._consumers[stream_name] = []

            stream_name = config.stream_name
            now = datetime.now(UTC)
            effective_msg_id = msg_id or f"msg_{uuid.uuid4().hex}"

            # Deduplication check
            dedup_key = (stream_name, effective_msg_id)
            if dedup_key in self._dedup_cache:
                cached_msg, cached_time = self._dedup_cache[dedup_key]
                if (now - cached_time).total_seconds() <= config.duplicate_window_seconds:
                    logger.debug("Deduplicated message %s on stream %s", effective_msg_id, stream_name)
                    return cached_msg

            stream_msgs = self._messages[stream_name]
            seq = len(stream_msgs) + 1

            message = JetStreamMessage(
                stream=stream_name,
                seq=seq,
                subject=subject,
                headers=headers or {},
                payload=payload,
                msg_id=effective_msg_id,
                timestamp=now,
            )

            # Enforce max_messages limits
            if len(stream_msgs) >= config.max_messages:
                stream_msgs.pop(0)

            stream_msgs.append(message)
            self._dedup_cache[dedup_key] = (message, now)

            logger.debug(
                "Published message seq=%d to stream=%s subject=%s (msg_id=%s)",
                seq,
                stream_name,
                subject,
                effective_msg_id,
            )
            return message

    def get_stream_info(self, fpo_id: str) -> FpoStreamInfo | None:
        stream_name = self._normalize_stream_name(fpo_id)
        config = self._streams.get(stream_name)
        if config is None:
            return None

        msgs = self._messages.get(stream_name, [])
        first_seq = msgs[0].seq if msgs else 0
        last_seq = msgs[-1].seq if msgs else 0
        total_bytes = sum(len(json.dumps(m.payload).encode()) for m in msgs)
        consumers = self._consumers.get(stream_name, [])

        return FpoStreamInfo(
            stream_name=stream_name,
            fpo_id=fpo_id,
            subjects=config.subjects,
            message_count=len(msgs),
            byte_count=total_bytes,
            first_seq=first_seq,
            last_seq=last_seq,
            consumer_count=len(consumers),
            created_at=config.created_at,
        )

    def create_consumer(
        self,
        stream_name: str,
        durable_name: str,
        subject_filter: str = ">",
    ) -> JetStreamConsumer:
        if stream_name not in self._streams:
            raise ValueError(f"Stream {stream_name} does not exist")
        consumer = JetStreamConsumer(
            durable_name=durable_name,
            stream_name=stream_name,
            subject_filter=subject_filter,
            engine=self,
        )
        if stream_name not in self._consumers:
            self._consumers[stream_name] = []
        self._consumers[stream_name].append(consumer)
        return consumer

    def get_messages_for_consumer(
        self,
        stream_name: str,
        subject_filter: str,
        start_seq: int,
        limit: int,
    ) -> list[JetStreamMessage]:
        msgs = self._messages.get(stream_name, [])
        result: list[JetStreamMessage] = []
        for m in msgs:
            if m.seq >= start_seq:
                if subject_filter in (">", "*") or m.subject.startswith(subject_filter.rstrip(".>")):
                    result.append(m)
                    if len(result) >= limit:
                        break
        return result


# Global singleton instance for platform runtime
_global_jetstream_engine: NatsJetStreamEngine | None = None


def get_jetstream_engine() -> NatsJetStreamEngine:
    global _global_jetstream_engine
    if _global_jetstream_engine is None:
        _global_jetstream_engine = NatsJetStreamEngine()
    return _global_jetstream_engine
