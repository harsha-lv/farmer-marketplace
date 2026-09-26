import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

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
    retention: str = "limits"
    max_deliver: int = 5


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
    delivery_count: int = 0
    max_deliver: int = 5
    engine: Any = None

    def ack(self) -> None:
        self.acked = True

    def nak(self) -> None:
        self.nacked = True
        self.delivery_count += 1
        if self.delivery_count >= self.max_deliver:
            self.terminated = True
            # Route poison pill to DLQ stream if DLQ stream is provisioned
            if self.engine is not None:
                dlq_stream = f"{self.stream}_DLQ"
                if dlq_stream in self.engine._streams:
                    clean_subject = self.subject
                    if ".dlq." not in clean_subject:
                        parts = clean_subject.split(".")
                        if len(parts) >= 2:
                            dlq_subj = f"{parts[0]}.{parts[1]}.dlq.{'.'.join(parts[2:]) if len(parts) > 2 else 'messages'}"
                        else:
                            dlq_subj = f"{clean_subject}.dlq"
                    else:
                        dlq_subj = clean_subject

                    asyncio.create_task(
                        self.engine.publish(
                            subject=dlq_subj,
                            payload=self.payload,
                            headers={
                                **self.headers,
                                "x-dlq-reason": "max_deliver_exceeded",
                                "x-original-stream": self.stream,
                                "x-delivery-count": str(self.delivery_count),
                            },
                            msg_id=f"dlq_{self.msg_id}",
                        )
                    )

    def term(self) -> None:
        self.terminated = True


class JetStreamConsumer:
    def __init__(
        self,
        durable_name: str,
        stream_name: str,
        subject_filter: str,
        engine: "NatsJetStreamEngine",
        ack_wait_seconds: float = 30.0,
        max_deliver: int = 5,
        max_ack_pending: int = 100,
        flow_control: bool = True,
        inactive_threshold_seconds: float = 86400.0,
    ) -> None:
        self.durable_name = durable_name
        self.stream_name = stream_name
        self.subject_filter = subject_filter
        self.engine = engine
        self.ack_wait_seconds = ack_wait_seconds
        self.max_deliver = max_deliver
        self.max_ack_pending = max_ack_pending
        self.flow_control = flow_control
        self.inactive_threshold_seconds = inactive_threshold_seconds
        self.cursor_seq = 0

    def fetch(self, batch_size: int = 10) -> list[JetStreamMessage]:
        effective_batch = min(batch_size, self.max_ack_pending)
        messages = self.engine.get_messages_for_consumer(
            stream_name=self.stream_name,
            subject_filter=self.subject_filter,
            start_seq=self.cursor_seq + 1,
            limit=effective_batch,
        )
        for msg in messages:
            msg.engine = self.engine
            msg.max_deliver = self.max_deliver
        if messages:
            self.cursor_seq = messages[-1].seq
        try:
            from app.telemetry.metrics import track_nats_ack_pending
            pending = sum(1 for m in self.engine._messages.get(self.stream_name, []) if not m.acked and not m.terminated)
            track_nats_ack_pending(stream=self.stream_name, consumer=self.durable_name, pending=pending)
        except Exception:
            pass
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
        parts = subject.split(".")
        # 1. Multi-tenant subject pattern: agri.<tenant_id>.<subtopic>
        if len(parts) >= 2 and parts[0] == "agri":
            tenant_id = parts[1]
            base_name = f"AGRI_{tenant_id.upper().replace('-', '_').replace('.', '_')}"
            # Check if this is targeting the DLQ stream
            if len(parts) >= 3 and parts[2] == "dlq":
                dlq_name = f"{base_name}_DLQ"
                if dlq_name in self._streams:
                    return self._streams[dlq_name]
            if base_name in self._streams:
                return self._streams[base_name]

        # 2. Legacy Subject pattern fpo.<fpo_id>.<subtopic>
        if len(parts) >= 2 and parts[0] == "fpo":
            fpo_id = parts[1]
            stream_name = self._normalize_stream_name(fpo_id)
            if stream_name in self._streams:
                return self._streams[stream_name]

        # 3. Fallback check registered subjects with wildcard matching
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
