from datetime import datetime
import logging
from typing import Sequence

from app.events.models import OutboxEvent
from app.events.publisher import EventPublisher
from app.events.reconstruction import reconstruct_point_in_time_state
from app.events.repository import EventRepository
from app.events.schemas import EventResponse, ReplayRequest, ReplayResponse

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
