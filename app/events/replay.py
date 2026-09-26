"""CLI and service logic for event replay and CQRS read model reconstruction from log.

CLI Usage:
    python -m app.events.replay --topic agri.lot.events --from 2026-01-01T00:00:00Z --projection lots
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.config import Settings, get_settings
from app.db.session import Database
from app.events.models import OutboxEvent
from app.events.publisher import EventPublisher
from app.events.reconstruction import (
    compute_state_hash,
    reconstruct_point_in_time_state,
)
from app.events.repository import EventRepository
from app.events.schemas import (
    EventResponse,
    ReplayRequest,
    ReplayResponse,
)

logger = logging.getLogger("app.events.replay")


async def execute_event_replay(
    request: ReplayRequest,
    repo: EventRepository,
    publisher: EventPublisher | None = None,
) -> ReplayResponse:
    """Execute sequential event replay over Kafka/NATS with dry-run support and state reconstruction."""
    if request.stream_id:
        events = await repo.get_stream(request.stream_id)
    else:
        raw_events, _ = await repo.query_events(limit=request.limit)
        events = raw_events

    # Filter by event_types
    if request.event_types:
        types_set = set(request.event_types)
        events = [e for e in events if e.event_type in types_set]

    # Filter by time bounds
    if request.from_time:
        events = [e for e in events if e.occurred_at >= request.from_time]
    if request.to_time:
        events = [e for e in events if e.occurred_at <= request.to_time]

    # Sort strictly chronologically
    events.sort(key=lambda e: (e.occurred_at, e.id))
    events = events[: request.limit]

    replayed_count = 0
    if not request.dry_run and publisher is not None:
        for event in events:
            # Republish with replay telemetry headers
            await publisher.publish(
                event_type=event.event_type,
                stream_id=event.stream_id,
                partition_key=event.partition_key,
                payload=event.payload,
            )
            replayed_count += 1
        logger.info("Replayed %d events to messaging bus", replayed_count)
    else:
        replayed_count = len(events)

    recon_state = None
    if request.stream_id and events:
        recon_point = reconstruct_point_in_time_state(request.stream_id, events)
        recon_state = recon_point.state

    return ReplayResponse(
        total_matched=len(events),
        replayed_count=replayed_count,
        dry_run=request.dry_run,
        events=[EventResponse.from_model(e) for e in events],
        reconstructed_state=recon_state,
    )


async def fetch_events_from_kafka(
    topic: str,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    limit: int = 1000,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Consume events directly from Kafka immutable topic log."""
    settings = settings or get_settings()
    if not settings.kafka_bootstrap_servers:
        return []

    from aiokafka import AIOKafkaConsumer, TopicPartition

    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=f"replay-cli-{int(datetime.now(UTC).timestamp())}",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    events: list[dict[str, Any]] = []
    try:
        await consumer.start()
        # Seek from beginning
        partitions = consumer.partitions_for_topic(topic) or set()
        if not partitions:
            return []

        tps = [TopicPartition(topic, p) for p in partitions]
        consumer.assign(tps)

        if from_time:
            # Lookup offsets by timestamp (milliseconds)
            ts_ms = int(from_time.timestamp() * 1000)
            offsets = await consumer.offsets_for_times({tp: ts_ms for tp in tps})
            for tp, offset_and_ts in offsets.items():
                if offset_and_ts is not None:
                    consumer.seek(tp, offset_and_ts.offset)
                else:
                    consumer.seek_to_beginning(tp)
        else:
            consumer.seek_to_beginning(*tps)

        # Read available records up to limit
        batch = await consumer.getmany(*tps, timeout_ms=3000, max_records=limit)
        for tp, messages in batch.items():
            for msg in messages:
                try:
                    payload = json.loads(msg.value.decode("utf-8"))
                    occ_str = payload.get("occurred_at")
                    occ_at = datetime.fromisoformat(occ_str) if occ_str else None
                    if to_time and occ_at and occ_at > to_time:
                        continue
                    events.append(payload)
                except Exception:
                    pass
    except Exception as exc:
        logger.warning("Could not read from Kafka topic %s (%s). Replaying from local DB outbox.", topic, exc)
    finally:
        await consumer.stop()

    return events


async def fetch_events_from_db(
    topic: str,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    limit: int = 1000,
    database: Database | None = None,
) -> list[dict[str, Any]]:
    """Fetch events from transactional outbox table matching topic and time bounds."""
    owns_db = database is None
    db = database or Database(get_settings().database_url)
    events: list[dict[str, Any]] = []

    try:
        async with db.session_factory() as session:
            stmt = select(OutboxEvent)
            # Match topic if recorded in kafka_topic, or match domain prefix
            domain_prefix = topic.replace("agri.", "").replace(".events", "")
            stmt = stmt.where(
                (OutboxEvent.kafka_topic == topic)
                | (OutboxEvent.event_type.ilike(f"{domain_prefix}%"))
                | (OutboxEvent.stream_id.ilike(f"{domain_prefix}%"))
            )
            if from_time:
                stmt = stmt.where(OutboxEvent.occurred_at >= from_time)
            if to_time:
                stmt = stmt.where(OutboxEvent.occurred_at <= to_time)
            stmt = stmt.order_by(OutboxEvent.occurred_at.asc(), OutboxEvent.id.asc()).limit(limit)

            result = await session.scalars(stmt)
            for row in result.all():
                events.append({
                    "event_id": row.event_id,
                    "stream_id": row.stream_id,
                    "event_type": row.event_type,
                    "occurred_at": row.occurred_at,
                    "partition_key": row.partition_key,
                    "payload": row.payload or {},
                    "consent_artifact_id": row.consent_artifact_id,
                })
    except Exception as exc:
        logger.warning("Could not query events from database outbox (%s). Continuing with available log events.", exc)
    finally:
        if owns_db:
            try:
                await db.dispose()
            except Exception:
                pass

    return events


async def replay_and_reconstruct(
    topic: str,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    projection: str = "lots",
    limit: int = 1000,
    db: Database | None = None,
) -> tuple[dict[str, Any], str, int]:
    """Rebuild read model projection from the log and compute deterministic SHA-256 state hash.

    Wires directly to `reconstruct_point_in_time_state` from `app.events.reconstruction`.
    """
    settings = get_settings()
    events = await fetch_events_from_kafka(topic, from_time=from_time, to_time=to_time, limit=limit, settings=settings)
    if not events:
        events = await fetch_events_from_db(topic, from_time=from_time, to_time=to_time, limit=limit, database=db)

    # Group events by stream / entity
    streams: dict[str, list[dict[str, Any]]] = {}
    for ev in events:
        stream_id = ev.get("stream_id") or f"{projection}:{ev.get('partition_key', 'default')}"
        streams.setdefault(stream_id, []).append(ev)

    reconstructed_read_models: dict[str, Any] = {}
    total_events = 0

    for stream_id, stream_evs in sorted(streams.items()):
        recon_result = reconstruct_point_in_time_state(
            stream_id=stream_id,
            events=stream_evs,
            as_of=to_time,
        )
        reconstructed_read_models[stream_id] = recon_result.state
        total_events += recon_result.total_events_applied

    combined_state = {
        "projection": projection,
        "topic": topic,
        "from_time": from_time.isoformat() if from_time else None,
        "to_time": to_time.isoformat() if to_time else None,
        "total_events": total_events,
        "entities": reconstructed_read_models,
    }
    state_hash = compute_state_hash(combined_state)
    return combined_state, state_hash, total_events


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay immutable Kafka / outbox events log and rebuild CQRS read model projection."
    )
    parser.add_argument("--topic", required=True, help="Kafka topic name (e.g. agri.lot.events)")
    parser.add_argument("--from", dest="from_time", help="Start timestamp in ISO 8601 (e.g. 2026-01-01T00:00:00Z)")
    parser.add_argument("--to", dest="to_time", help="End timestamp in ISO 8601")
    parser.add_argument("--projection", default="lots", help="Projection read model to rebuild (e.g. lots, trades)")
    parser.add_argument("--limit", type=int, default=1000, help="Max events to replay (default 1000)")
    return parser.parse_args(args)


async def main() -> None:
    args = parse_args(sys.argv[1:])

    from_dt: datetime | None = None
    if args.from_time:
        clean_from = args.from_time.replace("Z", "+00:00")
        from_dt = datetime.fromisoformat(clean_from)

    to_dt: datetime | None = None
    if args.to_time:
        clean_to = args.to_time.replace("Z", "+00:00")
        to_dt = datetime.fromisoformat(clean_to)

    print("=" * 70)
    print("AGRI-PLATFORM IMMUTABLE LOG REPLAY & CQRS RECONSTRUCTION")
    print(f"Topic:       {args.topic}")
    print(f"Projection:  {args.projection}")
    print(f"From:        {args.from_time or 'Beginning of Log'}")
    print(f"To:          {args.to_time or 'Latest'}")
    print("=" * 70)

    state, state_hash, count = await replay_and_reconstruct(
        topic=args.topic,
        from_time=from_dt,
        to_time=to_dt,
        projection=args.projection,
        limit=args.limit,
    )

    print("\n--- RECONSTRUCTED READ MODEL STATE ---")
    print(json.dumps(state, indent=2, default=str))
    print("\n" + "=" * 70)
    print(f"Events Replayed:  {count}")
    print(f"SHA-256 State Hash: {state_hash}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
