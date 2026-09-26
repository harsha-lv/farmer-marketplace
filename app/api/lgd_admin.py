"""Admin API endpoints for LGD unresolved queue inspection and manual resolution."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from app.api.deps import SessionDep, require_roles
from app.prices.lgd_models import LgdMarket, LgdMarketAlias, LgdUnresolved
from app.prices.lgd_resolver import resolve_market

router = APIRouter(prefix="/admin/lgd", tags=["admin-lgd"])


# ── Schemas ──


class UnresolvedItem(BaseModel):
    id: int
    raw_name: str
    entity_type: str
    state_hint: str | None = None
    district_hint: str | None = None
    best_guess_lgd_code: str | None = None
    confidence: float | None = None
    occurrence_count: int = 1
    created_at: str | None = None


class UnresolvedListResponse(BaseModel):
    items: list[UnresolvedItem]
    total: int


class ResolveRequest(BaseModel):
    unresolved_id: int = Field(..., description="ID from the unresolved queue")
    lgd_market_id: int = Field(..., description="Target LGD market ID to map to")
    create_alias: bool = Field(
        True, description="Whether to create an alias entry for future auto-resolution"
    )


class ResolveResponse(BaseModel):
    resolved: bool
    raw_name: str
    lgd_market_id: int
    alias_created: bool


class LgdResolveTestRequest(BaseModel):
    raw_market_name: str
    state_lgd_code: str | None = None


class LgdResolveTestResponse(BaseModel):
    raw_market_name: str
    lgd_code: str | None
    entity_id: int | None
    method: str
    confidence: float


# ── Endpoints ──


@router.get("/unresolved", response_model=UnresolvedListResponse)
async def list_unresolved(
    session: SessionDep,
    _admin: Annotated[dict, Depends(require_roles("admin"))],
    entity_type: Annotated[str | None, Query(max_length=32)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> UnresolvedListResponse:
    """List unresolved AGMARKNET names awaiting admin resolution."""
    stmt = select(LgdUnresolved).where(LgdUnresolved.resolved == False)
    if entity_type:
        stmt = stmt.where(LgdUnresolved.entity_type == entity_type)

    count_result = await session.execute(
        select(LgdUnresolved.id).where(LgdUnresolved.resolved == False)
    )
    all_ids = list(count_result.scalars().all())
    total = len(all_ids)

    stmt = stmt.order_by(LgdUnresolved.occurrence_count.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    items = [
        UnresolvedItem(
            id=r.id,
            raw_name=r.raw_name,
            entity_type=r.entity_type,
            state_hint=r.state_hint,
            district_hint=r.district_hint,
            best_guess_lgd_code=r.best_guess_lgd_code,
            confidence=r.confidence,
            occurrence_count=r.occurrence_count,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in rows
    ]
    return UnresolvedListResponse(items=items, total=total)


@router.post("/resolve", response_model=ResolveResponse)
async def resolve_unresolved(
    body: ResolveRequest,
    session: SessionDep,
    _admin: Annotated[dict, Depends(require_roles("admin"))],
) -> ResolveResponse:
    """Manually resolve an unresolved AGMARKNET name to an LGD market and optionally create an alias."""
    from app.errors import AppError

    # Fetch the unresolved entry
    stmt = select(LgdUnresolved).where(LgdUnresolved.id == body.unresolved_id)
    result = await session.execute(stmt)
    entry = result.scalars().first()
    if not entry:
        raise AppError(404, "Unresolved entry not found")

    # Verify target market exists
    mkt_stmt = select(LgdMarket).where(LgdMarket.id == body.lgd_market_id)
    mkt_result = await session.execute(mkt_stmt)
    market = mkt_result.scalars().first()
    if not market:
        raise AppError(404, "LGD market not found")

    # Mark as resolved
    up = (
        update(LgdUnresolved)
        .where(LgdUnresolved.id == entry.id)
        .values(
            resolved=True,
            resolved_lgd_code=market.district_lgd_code,
            resolved_by="admin",
            resolved_at=datetime.now(UTC),
            resolution_method="manual",
        )
    )
    await session.execute(up)

    # Optionally create alias
    alias_created = False
    if body.create_alias:
        alias = LgdMarketAlias(
            raw_name=entry.raw_name,
            market_id=market.id,
            created_by="admin",
        )
        session.add(alias)
        alias_created = True

    await session.commit()

    return ResolveResponse(
        resolved=True,
        raw_name=entry.raw_name,
        lgd_market_id=market.id,
        alias_created=alias_created,
    )


@router.post("/test-resolve", response_model=LgdResolveTestResponse)
async def test_resolve(
    body: LgdResolveTestRequest,
    session: SessionDep,
    _admin: Annotated[dict, Depends(require_roles("admin"))],
) -> LgdResolveTestResponse:
    """Test the resolution cascade for a raw AGMARKNET market name without persisting."""
    res = await resolve_market(
        session,
        raw_market_name=body.raw_market_name,
        state_lgd_code=body.state_lgd_code,
    )
    return LgdResolveTestResponse(
        raw_market_name=body.raw_market_name,
        lgd_code=res.lgd_code,
        entity_id=res.entity_id,
        method=res.method,
        confidence=res.confidence,
    )
