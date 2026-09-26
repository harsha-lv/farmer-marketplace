from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import SessionDep, SettingsDep, require_roles
from app.events.publisher import EventPublisher
from app.events.reconciliation import reconcile_audit_ledger
from app.events.reconstruction import reconstruct_point_in_time_state
from app.events.replay import execute_event_replay
from app.events.repository import EventRepository
from app.events.schemas import (
    AuditReconciliationReport,
    ConsentAuditResponse,
    EventListResponse,
    EventResponse,
    PointInTimeStateResponse,
    PublishOutboxResponse,
    ReplayRequest,
    ReplayResponse,
    StreamReplayResponse,
)

router = APIRouter(
    prefix="/events",
    tags=["events"],
    dependencies=[Depends(require_roles("admin"))],
)



def get_event_repo(session: SessionDep) -> EventRepository:
    return EventRepository(session)


EventRepoDep = Annotated[EventRepository, Depends(get_event_repo)]


@router.get("", response_model=EventListResponse)
async def list_events(
    repo: EventRepoDep,
    event_type: Annotated[str | None, Query(max_length=64)] = None,
    stream_id: Annotated[str | None, Query(max_length=128)] = None,
    consent_artifact_id: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EventListResponse:
    events, total = await repo.query_events(
        event_type=event_type,
        stream_id=stream_id,
        consent_artifact_id=consent_artifact_id,
        limit=limit,
        offset=offset,
    )
    return EventListResponse(
        total=total,
        limit=limit,
        offset=offset,
        events=[EventResponse.from_model(e) for e in events],
    )


@router.get("/stream/{stream_id}", response_model=StreamReplayResponse)
async def replay_event_stream(
    stream_id: str,
    repo: EventRepoDep,
) -> StreamReplayResponse:
    events = await repo.get_stream(stream_id)
    return StreamReplayResponse(
        stream_id=stream_id,
        total_events=len(events),
        events=[EventResponse.from_model(e) for e in events],
    )


@router.get("/audit/dpdp/{consent_artifact_id}", response_model=ConsentAuditResponse)
async def audit_dpdp_consent_operations(
    consent_artifact_id: str,
    repo: EventRepoDep,
) -> ConsentAuditResponse:
    events = await repo.get_by_consent(consent_artifact_id)
    return ConsentAuditResponse(
        consent_artifact_id=consent_artifact_id,
        total_operations=len(events),
        events=[EventResponse.from_model(e) for e in events],
    )


@router.post("/publish", response_model=PublishOutboxResponse)
async def flush_outbox_events(
    repo: EventRepoDep,
    session: SessionDep,
    settings: SettingsDep,
) -> PublishOutboxResponse:
    publisher = EventPublisher(
        kafka_servers=settings.kafka_bootstrap_servers,
        nats_url=settings.nats_url,
    )
    dispatched_ids = await publisher.flush_outbox(
        repo,
        limit=settings.event_outbox_batch_size,
    )
    await session.commit()
    return PublishOutboxResponse(
        dispatched_count=len(dispatched_ids),
        event_ids=dispatched_ids,
    )


@router.get("/reconstruct/{stream_id}", response_model=PointInTimeStateResponse)
async def reconstruct_state(
    stream_id: str,
    repo: EventRepoDep,
    as_of: datetime | None = None,
) -> PointInTimeStateResponse:
    """CQRS Point-in-Time Reconstruction: Rebuild exact entity state by folding chronological events up to as_of timestamp."""
    events = await repo.get_stream(stream_id)
    return reconstruct_point_in_time_state(stream_id, events, as_of=as_of)


@router.post("/replay", response_model=ReplayResponse)
async def replay_events(
    request: ReplayRequest,
    repo: EventRepoDep,
    settings: SettingsDep,
) -> ReplayResponse:
    """Kafka Event Replay: Sequentially replay events for a stream or time-window with dry-run verification."""
    publisher = None
    if not request.dry_run:
        publisher = EventPublisher(
            kafka_servers=settings.kafka_bootstrap_servers,
            nats_url=settings.nats_url,
        )
    return await execute_event_replay(request, repo, publisher=publisher)


@router.post("/reconcile/{stream_id}", response_model=AuditReconciliationReport)
async def reconcile_stream(
    stream_id: str,
    repo: EventRepoDep,
    current_projection: dict[str, Any] | None = None,
) -> AuditReconciliationReport:
    """Audit Reconciliation: Compare event-sourced reconstructed state against current read projection to detect discrepancies."""
    events = await repo.get_stream(stream_id)
    recon = reconstruct_point_in_time_state(stream_id, events)
    return reconcile_audit_ledger(
        stream_id=stream_id,
        reconstructed_state=recon.state,
        projection_state=current_projection,
        event_count=len(events),
    )

