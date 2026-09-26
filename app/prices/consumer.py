import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from app.prices.feed import FeedError, MandiFeed
from app.prices.ingest import IngestCounts, PriceSink, store_quotes
from app.prices.schemas import IngestJobStatusResponse, IngestJobTrigger
from app.telemetry.jetstream import (
    JetStreamMessage,
    JetStreamStreamConfig,
    NatsJetStreamEngine,
)

logger = logging.getLogger("app.prices.consumer")

PRICES_INGEST_STREAM = "PRICES_INGEST_STREAM"
PRICES_TRIGGER_SUBJECT = "prices.ingest.trigger"
PRICES_COMPLETED_SUBJECT = "prices.ingest.completed"
PRICES_FAILED_SUBJECT = "prices.ingest.failed"


class ContinuousIngestionConsumer:
    """Continuous NATS JetStream consumer and scheduler for automated AGMARKNET / NDSAP ingestion."""

    def __init__(
        self,
        engine: NatsJetStreamEngine,
        feed: MandiFeed | None = None,
        sink_factory: Any = None,
    ) -> None:
        self.engine = engine
        self.feed = feed
        self.sink_factory = sink_factory
        self._jobs: dict[str, IngestJobStatusResponse] = {}
        self._lock = asyncio.Lock()
        self._consumer_durable = "agmarknet_scheduled_consumer"
        self._consumer = None

    async def initialize(self) -> JetStreamStreamConfig:
        """Provision the prices ingest stream with JetStream deduplication and message limits."""
        async with self._lock:
            if PRICES_INGEST_STREAM not in self.engine._streams:
                config = JetStreamStreamConfig(
                    stream_name=PRICES_INGEST_STREAM,
                    fpo_id="SYSTEM",
                    subjects=["prices.ingest.>"],
                    max_messages=50_000,
                    duplicate_window_seconds=300,
                )
                self.engine._streams[PRICES_INGEST_STREAM] = config
                self.engine._messages[PRICES_INGEST_STREAM] = []
                self.engine._consumers[PRICES_INGEST_STREAM] = []
                logger.info("Initialized NATS JetStream stream %s", PRICES_INGEST_STREAM)
            return self.engine._streams[PRICES_INGEST_STREAM]

    async def schedule_ingest(
        self,
        *,
        state: str | None = None,
        commodity: str | None = None,
        max_records: int = 100,
        trigger_type: str = "SCHEDULED",
        rate_limit_delay_seconds: float = 0.05,
    ) -> IngestJobTrigger:
        """Schedule an ingestion job by publishing a trigger event to NATS."""
        await self.initialize()
        job_id = f"ingest_{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC)

        job_trigger = IngestJobTrigger(
            job_id=job_id,
            state=state,
            commodity=commodity,
            max_records=max_records,
            trigger_type=trigger_type,
            rate_limit_delay_seconds=rate_limit_delay_seconds,
            timestamp=now,
        )

        initial_status = IngestJobStatusResponse(
            job_id=job_id,
            status="PENDING",
            state=state,
            commodity=commodity,
            started_at=None,
            completed_at=None,
            fetched=0,
            stored=0,
            skipped=0,
        )
        self._jobs[job_id] = initial_status

        await self.engine.publish(
            subject=PRICES_TRIGGER_SUBJECT,
            payload=job_trigger.model_dump(mode="json"),
            msg_id=job_id,
        )
        logger.info("Published ingest trigger for job %s to %s", job_id, PRICES_TRIGGER_SUBJECT)
        return job_trigger

    async def process_job(
        self,
        job_id: str,
        *,
        state: str | None = None,
        commodity: str | None = None,
        max_records: int = 100,
        rate_limit_delay_seconds: float = 0.05,
        max_retries: int = 3,
        backoff_base_seconds: float = 0.05,
        feed: MandiFeed | None = None,
        sink: PriceSink | None = None,
    ) -> IngestJobStatusResponse:
        """Process an ingestion trigger with exponential backoff on transient errors and rate limiting."""
        active_feed = feed or self.feed
        if not active_feed:
            raise RuntimeError("MandiFeed is not configured for consumer")

        await self.initialize()
        start_time = datetime.now(UTC)
        current_job = self._jobs.get(
            job_id,
            IngestJobStatusResponse(
                job_id=job_id,
                status="RUNNING",
                state=state,
                commodity=commodity,
                started_at=start_time,
            ),
        )
        current_job.status = "RUNNING"
        current_job.started_at = start_time
        self._jobs[job_id] = current_job

        retries = 0
        last_error: Exception | None = None

        while retries <= max_retries:
            try:
                # Apply rate limit delay before hitting NDSAP/AGMARKNET API
                if rate_limit_delay_seconds > 0:
                    await asyncio.sleep(rate_limit_delay_seconds)

                records = await active_feed.fetch(
                    state=state,
                    commodity=commodity,
                    max_records=max_records,
                )

                # Store quotes
                if sink:
                    counts = await store_quotes(records, sink)
                elif self.sink_factory:
                    active_sink = await self.sink_factory()
                    counts = await store_quotes(records, active_sink)
                else:
                    # Ingest without persistence sink if test mode
                    counts = IngestCounts(fetched=len(records), stored=len(records), skipped=0)

                end_time = datetime.now(UTC)
                duration = round((end_time - start_time).total_seconds(), 3)

                current_job.status = "SUCCESS"
                current_job.fetched = counts.fetched
                current_job.stored = counts.stored
                current_job.skipped = counts.skipped
                current_job.completed_at = end_time
                current_job.duration_seconds = duration
                current_job.retries = retries
                self._jobs[job_id] = current_job

                # Publish completion event to NATS
                await self.engine.publish(
                    subject=PRICES_COMPLETED_SUBJECT,
                    payload=current_job.model_dump(mode="json"),
                    msg_id=f"comp_{job_id}",
                )
                logger.info("Job %s completed successfully: %s stored", job_id, counts.stored)
                return current_job

            except FeedError as exc:
                retries += 1
                last_error = exc
                logger.warning(
                    "Job %s attempt %d failed with FeedError: %s. Backing off...",
                    job_id,
                    retries,
                    exc,
                )
                if retries <= max_retries:
                    backoff = backoff_base_seconds * (2 ** (retries - 1))
                    await asyncio.sleep(backoff)

        # Retries exhausted -> mark as FAILED
        end_time = datetime.now(UTC)
        duration = round((end_time - start_time).total_seconds(), 3)
        current_job.status = "FAILED"
        current_job.error_message = str(last_error) if last_error else "Max retries exceeded"
        current_job.completed_at = end_time
        current_job.duration_seconds = duration
        current_job.retries = retries - 1
        self._jobs[job_id] = current_job

        await self.engine.publish(
            subject=PRICES_FAILED_SUBJECT,
            payload=current_job.model_dump(mode="json"),
            msg_id=f"fail_{job_id}",
        )
        logger.error("Job %s failed permanently after %d retries: %s", job_id, retries - 1, last_error)
        return current_job

    async def poll_and_process_next_batch(
        self,
        batch_size: int = 5,
        feed: MandiFeed | None = None,
        sink: PriceSink | None = None,
    ) -> list[IngestJobStatusResponse]:
        """Poll queued trigger messages from NATS and execute ingestion."""
        await self.initialize()
        if self._consumer is None:
            self._consumer = self.engine.create_consumer(
                stream_name=PRICES_INGEST_STREAM,
                durable_name=self._consumer_durable,
                subject_filter=PRICES_TRIGGER_SUBJECT,
            )

        messages: list[JetStreamMessage] = self._consumer.fetch(batch_size=batch_size)

        results: list[IngestJobStatusResponse] = []

        for msg in messages:
            try:
                payload = msg.payload
                job_id = payload.get("job_id", msg.msg_id)
                res = await self.process_job(
                    job_id=job_id,
                    state=payload.get("state"),
                    commodity=payload.get("commodity"),
                    max_records=payload.get("max_records", 100),
                    rate_limit_delay_seconds=payload.get("rate_limit_delay_seconds", 0.0),
                    feed=feed,
                    sink=sink,
                )
                msg.ack()
                results.append(res)
            except Exception as e:
                logger.exception("Error processing message %s: %s", msg.msg_id, e)
                msg.nak()

        return results

    def get_job(self, job_id: str) -> IngestJobStatusResponse | None:
        return self._jobs.get(job_id)

    def list_jobs(self, limit: int = 50) -> list[IngestJobStatusResponse]:
        jobs = list(self._jobs.values())
        jobs.sort(key=lambda j: j.started_at or datetime.min.replace(tzinfo=UTC), reverse=True)
        return jobs[:limit]
