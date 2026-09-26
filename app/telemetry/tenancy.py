"""Multi-tenant NATS JetStream stream and consumer management.

Implements programmatic per-tenant isolation:
- Stream template: AGRI_{tenant_id} with subject agri.{tenant_id}.>
- DLQ Stream template: AGRI_{tenant_id}_DLQ with subject agri.{tenant_id}.dlq.>
- Retention limits / work limits from platform settings
- Duplicate window = 120s for deterministic deduplication
- Idempotent stream provisioning (safe to execute on every boot)
- Pull-based consumer creation with flow control, tunable ack_wait,
  inactive threshold, and max_ack_pending backpressure.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.config import Settings, get_settings
from app.telemetry.jetstream import (
    JetStreamConsumer,
    JetStreamStreamConfig,
    NatsJetStreamEngine,
    get_jetstream_engine,
)

logger = logging.getLogger("app.telemetry.tenancy")


def normalize_tenant_identifier(tenant_id: str) -> tuple[str, str]:
    """Normalize tenant identifier into canonical stream name and subject prefix.

    Returns:
        (stream_name, subject_prefix) e.g. ("AGRI_PUNJAB_FPO_01", "agri.punjab_fpo_01")
    """
    clean = str(tenant_id).strip().replace("-", "_").replace(".", "_")
    stream_name = f"AGRI_{clean.upper()}"
    subject_prefix = f"agri.{clean.lower()}"
    return stream_name, subject_prefix


@dataclass
class TenantStreamProvisionResult:
    tenant_id: str
    primary_stream: str
    primary_subject: str
    dlq_stream: str
    dlq_subject: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated: bool = False


class TenantStreamManager:
    """Manages multi-tenant JetStream stream and pull-consumer lifecycles."""

    def __init__(
        self,
        engine: NatsJetStreamEngine | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.engine = engine or get_jetstream_engine()
        self.default_duplicate_window = 120  # 120 seconds deduplication window

    async def provision_tenant_streams(
        self,
        tenant_id: str,
        *,
        max_messages: int | None = None,
        max_bytes: int | None = None,
        max_age_seconds: int | None = None,
        duplicate_window_seconds: int | None = None,
        retention: str = "limits",
    ) -> TenantStreamProvisionResult:
        """Programmatically and idempotently provision primary and DLQ streams for a tenant.

        - Primary: AGRI_{tenant_id} -> subjects: agri.{tenant_id}.>
        - DLQ: AGRI_{tenant_id}_DLQ -> subjects: agri.{tenant_id}.dlq.>
        Safe to call on every service startup.
        """
        stream_name, subject_prefix = normalize_tenant_identifier(tenant_id)
        dlq_stream_name = f"{stream_name}_DLQ"
        dlq_subject = f"{subject_prefix}.dlq.>"
        primary_subject = f"{subject_prefix}.>"

        limit_messages = max_messages or self.settings.nats_jetstream_max_messages
        limit_bytes = max_bytes or self.settings.nats_jetstream_max_bytes
        limit_age = max_age_seconds or self.settings.nats_jetstream_max_age_seconds
        dedup_window = duplicate_window_seconds or self.default_duplicate_window

        # 1. Provision DLQ Stream first
        dlq_config = JetStreamStreamConfig(
            stream_name=dlq_stream_name,
            fpo_id=tenant_id,
            subjects=[dlq_subject],
            max_messages=max(10_000, limit_messages // 5),
            max_bytes=max(10_485_760, limit_bytes // 5),
            max_age_seconds=max(2_592_000, limit_age),  # DLQ retained longer (30 days minimum)
            duplicate_window_seconds=dedup_window,
        )
        dlq_config.retention = retention  # type: ignore[attr-defined]

        # 2. Provision Primary Stream
        primary_config = JetStreamStreamConfig(
            stream_name=stream_name,
            fpo_id=tenant_id,
            subjects=[primary_subject],
            max_messages=limit_messages,
            max_bytes=limit_bytes,
            max_age_seconds=limit_age,
            duplicate_window_seconds=dedup_window,
        )
        primary_config.retention = retention  # type: ignore[attr-defined]

        # Register in in-process engine
        updated = False
        async with self.engine._lock:
            if stream_name in self.engine._streams:
                updated = True
            self.engine._streams[stream_name] = primary_config
            if stream_name not in self.engine._messages:
                self.engine._messages[stream_name] = []
            if stream_name not in self.engine._consumers:
                self.engine._consumers[stream_name] = []

            self.engine._streams[dlq_stream_name] = dlq_config
            if dlq_stream_name not in self.engine._messages:
                self.engine._messages[dlq_stream_name] = []
            if dlq_stream_name not in self.engine._consumers:
                self.engine._consumers[dlq_stream_name] = []

        # If real NATS client is active and connected, apply stream configs to cluster
        if getattr(self.engine, "_nc", None) and hasattr(self.engine._nc, "jetstream"):
            try:
                js = self.engine._nc.jetstream()
                # Idempotent add or update stream
                try:
                    await js.add_stream(name=dlq_stream_name, subjects=[dlq_subject])
                except Exception:
                    await js.update_stream(name=dlq_stream_name, subjects=[dlq_subject])

                try:
                    await js.add_stream(
                        name=stream_name,
                        subjects=[primary_subject],
                        duplicate_window=dedup_window,
                        max_msgs=limit_messages,
                        max_bytes=limit_bytes,
                        max_age=limit_age,
                    )
                except Exception:
                    await js.update_stream(
                        name=stream_name,
                        subjects=[primary_subject],
                        duplicate_window=dedup_window,
                        max_msgs=limit_messages,
                        max_bytes=limit_bytes,
                        max_age=limit_age,
                    )
            except Exception as e:
                logger.warning("Could not sync tenant streams with external NATS server: %s", e)

        logger.info(
            "Provisioned tenant streams for %s: primary=%s (%s), dlq=%s (%s)",
            tenant_id,
            stream_name,
            primary_subject,
            dlq_stream_name,
            dlq_subject,
        )

        return TenantStreamProvisionResult(
            tenant_id=tenant_id,
            primary_stream=stream_name,
            primary_subject=primary_subject,
            dlq_stream=dlq_stream_name,
            dlq_subject=dlq_subject,
            updated=updated,
        )

    def create_pull_consumer(
        self,
        tenant_id: str,
        durable_name: str,
        *,
        subject_filter: str | None = None,
        ack_wait_seconds: float = 30.0,
        max_deliver: int = 5,
        max_ack_pending: int = 100,
        flow_control: bool = True,
        inactive_threshold_seconds: float = 86400.0,
    ) -> JetStreamConsumer:
        """Create or configure a pull-based durable consumer for a tenant stream.

        Features:
        - Pull-based delivery
        - Flow control
        - Workload-tuned ack_wait
        - Max deliver poison-pill cutoff before routing to DLQ
        - Max ack pending for backpressure
        - Inactive threshold to purge dead ephemeral consumers
        """
        stream_name, subject_prefix = normalize_tenant_identifier(tenant_id)
        effective_filter = subject_filter or f"{subject_prefix}.>"

        # Ensure stream is registered
        if stream_name not in self.engine._streams:
            primary_config = JetStreamStreamConfig(
                stream_name=stream_name,
                fpo_id=tenant_id,
                subjects=[f"{subject_prefix}.>"],
                max_messages=self.settings.nats_jetstream_max_messages,
                max_bytes=self.settings.nats_jetstream_max_bytes,
                max_age_seconds=self.settings.nats_jetstream_max_age_seconds,
                duplicate_window_seconds=self.default_duplicate_window,
            )
            self.engine._streams[stream_name] = primary_config
            self.engine._messages[stream_name] = []
            self.engine._consumers[stream_name] = []

        consumer = JetStreamConsumer(
            durable_name=durable_name,
            stream_name=stream_name,
            subject_filter=effective_filter,
            engine=self.engine,
            ack_wait_seconds=ack_wait_seconds,
            max_deliver=max_deliver,
            max_ack_pending=max_ack_pending,
            flow_control=flow_control,
            inactive_threshold_seconds=inactive_threshold_seconds,
        )

        if stream_name not in self.engine._consumers:
            self.engine._consumers[stream_name] = []

        # Idempotently update existing durable consumer registration
        existing = [c for c in self.engine._consumers[stream_name] if c.durable_name == durable_name]
        if existing:
            self.engine._consumers[stream_name].remove(existing[0])

        self.engine._consumers[stream_name].append(consumer)
        logger.info(
            "Created pull consumer '%s' on stream '%s' (filter=%s, ack_wait=%.1fs, max_deliver=%d, max_ack_pending=%d)",
            durable_name,
            stream_name,
            effective_filter,
            ack_wait_seconds,
            max_deliver,
            max_ack_pending,
        )
        return consumer
