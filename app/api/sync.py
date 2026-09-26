"""FastAPI endpoints for WatermelonDB offline-first synchronization protocol."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import SessionDep, get_current_auth
from app.auth.schemas import UserContext
from app.sync.schemas import (
    SyncPullResponse,
    SyncPushPayload,
    SyncPushResponse,
    SyncSchemaResponse,
)
from app.sync.service import SyncService

router = APIRouter(
    prefix="/sync",
    tags=["sync"],
    dependencies=[Depends(get_current_auth)],
)

UserContextDep = Annotated[UserContext, Depends(get_current_auth)]


@router.get("/schema", response_model=SyncSchemaResponse)
async def sync_schema(session: SessionDep) -> SyncSchemaResponse:
    """Return the exact table and column list the server supports for client diffing."""
    service = SyncService(session)
    return service.get_schema()


@router.get("/pull", response_model=SyncPullResponse)
async def sync_pull(
    session: SessionDep,
    user_ctx: UserContextDep,
    last_pulled_at: int | None = Query(None, alias="lastPulledAt"),
    migration_version: int | None = Query(1, alias="migrationVersion"),
    schema_version: int | None = Query(1, alias="schemaVersion"),
    limit: int = Query(500, alias="limit", ge=1, le=2000),
    cursor: str | None = Query(None, alias="cursor"),
) -> SyncPullResponse:
    """Pull delta changes since lastPulledAt with continuation cursor pagination."""
    service = SyncService(session)
    return await service.pull(
        user_ctx=user_ctx,
        last_pulled_at=last_pulled_at,
        limit=limit,
        cursor=cursor,
        schema_version=schema_version or 1,
        migration_version=migration_version or 1,
    )


@router.post("/push", response_model=SyncPushResponse)
async def sync_push(
    payload: SyncPushPayload,
    session: SessionDep,
    user_ctx: UserContextDep,
) -> SyncPushResponse:
    """Push local changes to server with deterministic conflict resolution."""
    service = SyncService(session)
    return await service.push(user_ctx=user_ctx, payload=payload)


# ---------------------------------------------------------------------------
# Backwards Compatibility Aliases (/api/v1/sync GET and POST)
# ---------------------------------------------------------------------------


@router.get("", response_model=SyncPullResponse, include_in_schema=False)
async def sync_pull_legacy(
    session: SessionDep,
    user_ctx: UserContextDep,
    last_pulled_at: int | None = Query(None, alias="lastPulledAt"),
    migration_version: int | None = Query(1, alias="migrationVersion"),
    schema_version: int | None = Query(1, alias="schemaVersion"),
    limit: int = Query(500, alias="limit", ge=1, le=2000),
    cursor: str | None = Query(None, alias="cursor"),
) -> SyncPullResponse:
    return await sync_pull(
        session=session,
        user_ctx=user_ctx,
        last_pulled_at=last_pulled_at,
        migration_version=migration_version,
        schema_version=schema_version,
        limit=limit,
        cursor=cursor,
    )


@router.post("", response_model=SyncPushResponse, include_in_schema=False)
async def sync_push_legacy(
    payload: SyncPushPayload,
    session: SessionDep,
    user_ctx: UserContextDep,
) -> SyncPushResponse:
    return await sync_push(payload=payload, session=session, user_ctx=user_ctx)
