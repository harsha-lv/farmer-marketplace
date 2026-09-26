"""LGD name-to-code resolution engine.

Resolution cascade:
  1. Exact match against canonical LGD market/district name
  2. Normalized match (case, accent, punctuation insensitive)
  3. Alias table lookup (admin-editable ``lgd_market_aliases``)
  4. Fuzzy match using difflib.SequenceMatcher with confidence threshold

Every resolution records the method and confidence score for auditability.
Unresolvable names are sent to the ``lgd_unresolved`` review queue.
"""

from __future__ import annotations

import difflib
import logging
import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy import func, select, update

from app.prices.lgd_models import (
    LgdDistrict,
    LgdMarket,
    LgdMarketAlias,
    LgdState,
    LgdUnresolved,
)

logger = logging.getLogger("app.prices.lgd_resolver")

# Confidence threshold for fuzzy matching.  Below this, name goes to the review queue.
FUZZY_THRESHOLD = 0.75


@dataclass(frozen=True)
class ResolutionResult:
    """Outcome of a single name-to-LGD-code resolution attempt."""

    lgd_code: str | None
    entity_id: int | None
    method: str  # "exact" | "normalized" | "alias" | "fuzzy" | "unresolved"
    confidence: float  # 1.0 for exact, 0.0..1.0 for fuzzy, 0.0 for unresolved


def _normalize(name: str) -> str:
    """Normalize a place name: strip accents, lowercase, collapse whitespace/punctuation."""
    # NFD decompose → remove combining marks → NFC recompose
    text = unicodedata.normalize("NFD", name)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = unicodedata.normalize("NFC", text)
    text = text.casefold().replace("&", " and ")
    # Replace any non-alnum with space, collapse runs
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


async def resolve_market(
    session,
    *,
    raw_market_name: str,
    state_lgd_code: str | None = None,
) -> ResolutionResult:
    """Resolve a raw AGMARKNET market string to an LGD market entity.

    Parameters
    ----------
    session:
        Async database session (or AsyncSessionAdapter from tests).
    raw_market_name:
        The AGMARKNET market name exactly as received from the feed.
    state_lgd_code:
        Optional state LGD code to narrow the search scope.
    """
    if not raw_market_name or not raw_market_name.strip():
        return ResolutionResult(lgd_code=None, entity_id=None, method="unresolved", confidence=0.0)

    raw_stripped = raw_market_name.strip()
    normalized_input = _normalize(raw_stripped)

    # ── 1. Exact match ──
    stmt = select(LgdMarket).where(LgdMarket.market_name == raw_stripped)
    if state_lgd_code:
        stmt = stmt.where(LgdMarket.state_lgd_code == state_lgd_code)
    result = await session.execute(stmt)
    row = result.scalars().first() if hasattr(result, "scalars") else None
    if row:
        logger.debug("LGD exact match: '%s' → market_id=%s", raw_stripped, row.id)
        return ResolutionResult(
            lgd_code=row.district_lgd_code, entity_id=row.id, method="exact", confidence=1.0
        )

    # ── 2. Normalized match ──
    all_stmt = select(LgdMarket)
    if state_lgd_code:
        all_stmt = all_stmt.where(LgdMarket.state_lgd_code == state_lgd_code)
    all_result = await session.execute(all_stmt)
    all_markets = list(all_result.scalars().all()) if hasattr(all_result, "scalars") else []

    for mkt in all_markets:
        if _normalize(mkt.market_name) == normalized_input:
            logger.debug("LGD normalized match: '%s' → market_id=%s", raw_stripped, mkt.id)
            return ResolutionResult(
                lgd_code=mkt.district_lgd_code, entity_id=mkt.id, method="normalized", confidence=0.95
            )

    # ── 3. Alias table lookup ──
    alias_stmt = select(LgdMarketAlias).where(
        func.lower(LgdMarketAlias.raw_name) == raw_stripped.lower()
    )
    alias_result = await session.execute(alias_stmt)
    alias_row = alias_result.scalars().first() if hasattr(alias_result, "scalars") else None
    if alias_row:
        # Fetch the market to get its lgd code
        mkt_stmt = select(LgdMarket).where(LgdMarket.id == alias_row.market_id)
        mkt_result = await session.execute(mkt_stmt)
        mkt_row = mkt_result.scalars().first() if hasattr(mkt_result, "scalars") else None
        if mkt_row:
            logger.debug("LGD alias match: '%s' → market_id=%s", raw_stripped, mkt_row.id)
            return ResolutionResult(
                lgd_code=mkt_row.district_lgd_code,
                entity_id=mkt_row.id,
                method="alias",
                confidence=0.90,
            )

    # ── 4. Fuzzy match ──
    best_match: LgdMarket | None = None
    best_score = 0.0
    for mkt in all_markets:
        score = difflib.SequenceMatcher(None, normalized_input, _normalize(mkt.market_name)).ratio()
        if score > best_score:
            best_score = score
            best_match = mkt

    if best_match and best_score >= FUZZY_THRESHOLD:
        logger.debug(
            "LGD fuzzy match: '%s' → '%s' (score=%.3f, market_id=%s)",
            raw_stripped,
            best_match.market_name,
            best_score,
            best_match.id,
        )
        return ResolutionResult(
            lgd_code=best_match.district_lgd_code,
            entity_id=best_match.id,
            method="fuzzy",
            confidence=round(best_score, 4),
        )

    # ── 5. Unresolved → review queue ──
    await _enqueue_unresolved(
        session,
        raw_name=raw_stripped,
        entity_type="market",
        state_hint=state_lgd_code,
        best_guess_lgd=best_match.district_lgd_code if best_match else None,
        best_guess_confidence=round(best_score, 4) if best_match else None,
    )
    return ResolutionResult(lgd_code=None, entity_id=None, method="unresolved", confidence=0.0)


async def resolve_district(
    session,
    *,
    raw_district_name: str,
    state_lgd_code: str | None = None,
) -> ResolutionResult:
    """Resolve a raw district name to an LGD district entity."""
    if not raw_district_name or not raw_district_name.strip():
        return ResolutionResult(lgd_code=None, entity_id=None, method="unresolved", confidence=0.0)

    raw_stripped = raw_district_name.strip()
    normalized_input = _normalize(raw_stripped)

    # ── 1. Exact match ──
    stmt = select(LgdDistrict).where(LgdDistrict.district_name == raw_stripped)
    if state_lgd_code:
        stmt = stmt.where(LgdDistrict.state_lgd_code == state_lgd_code)
    result = await session.execute(stmt)
    row = result.scalars().first() if hasattr(result, "scalars") else None
    if row:
        return ResolutionResult(lgd_code=row.lgd_code, entity_id=row.id, method="exact", confidence=1.0)

    # ── 2. Normalized match ──
    all_stmt = select(LgdDistrict)
    if state_lgd_code:
        all_stmt = all_stmt.where(LgdDistrict.state_lgd_code == state_lgd_code)
    all_result = await session.execute(all_stmt)
    all_districts = list(all_result.scalars().all()) if hasattr(all_result, "scalars") else []

    for dist in all_districts:
        if _normalize(dist.district_name) == normalized_input:
            return ResolutionResult(
                lgd_code=dist.lgd_code, entity_id=dist.id, method="normalized", confidence=0.95
            )

    # ── 3. Fuzzy match ──
    best_match: LgdDistrict | None = None
    best_score = 0.0
    for dist in all_districts:
        score = difflib.SequenceMatcher(None, normalized_input, _normalize(dist.district_name)).ratio()
        if score > best_score:
            best_score = score
            best_match = dist

    if best_match and best_score >= FUZZY_THRESHOLD:
        return ResolutionResult(
            lgd_code=best_match.lgd_code,
            entity_id=best_match.id,
            method="fuzzy",
            confidence=round(best_score, 4),
        )

    await _enqueue_unresolved(
        session,
        raw_name=raw_stripped,
        entity_type="district",
        state_hint=state_lgd_code,
    )
    return ResolutionResult(lgd_code=None, entity_id=None, method="unresolved", confidence=0.0)


async def resolve_state(session, *, raw_state_name: str) -> ResolutionResult:
    """Resolve a raw state name to an LGD state entity."""
    if not raw_state_name or not raw_state_name.strip():
        return ResolutionResult(lgd_code=None, entity_id=None, method="unresolved", confidence=0.0)

    raw_stripped = raw_state_name.strip()
    normalized_input = _normalize(raw_stripped)

    # ── 1. Exact ──
    stmt = select(LgdState).where(LgdState.state_name == raw_stripped)
    result = await session.execute(stmt)
    row = result.scalars().first() if hasattr(result, "scalars") else None
    if row:
        return ResolutionResult(lgd_code=row.lgd_code, entity_id=row.id, method="exact", confidence=1.0)

    # ── 2. Normalized ──
    all_result = await session.execute(select(LgdState))
    all_states = list(all_result.scalars().all()) if hasattr(all_result, "scalars") else []

    for st in all_states:
        if _normalize(st.state_name) == normalized_input:
            return ResolutionResult(
                lgd_code=st.lgd_code, entity_id=st.id, method="normalized", confidence=0.95
            )

    # Also check state_code (e.g. "MH", "KA")
    upper = raw_stripped.upper()
    for st in all_states:
        if st.state_code == upper:
            return ResolutionResult(
                lgd_code=st.lgd_code, entity_id=st.id, method="exact", confidence=1.0
            )

    # ── 3. Fuzzy ──
    best_match: LgdState | None = None
    best_score = 0.0
    for st in all_states:
        score = difflib.SequenceMatcher(None, normalized_input, _normalize(st.state_name)).ratio()
        if score > best_score:
            best_score = score
            best_match = st

    if best_match and best_score >= FUZZY_THRESHOLD:
        return ResolutionResult(
            lgd_code=best_match.lgd_code,
            entity_id=best_match.id,
            method="fuzzy",
            confidence=round(best_score, 4),
        )

    await _enqueue_unresolved(
        session, raw_name=raw_stripped, entity_type="state"
    )
    return ResolutionResult(lgd_code=None, entity_id=None, method="unresolved", confidence=0.0)


async def _enqueue_unresolved(
    session,
    *,
    raw_name: str,
    entity_type: str,
    state_hint: str | None = None,
    district_hint: str | None = None,
    best_guess_lgd: str | None = None,
    best_guess_confidence: float | None = None,
) -> None:
    """Insert or increment the occurrence counter for an unresolved name."""
    # Check if already exists
    stmt = select(LgdUnresolved).where(
        LgdUnresolved.raw_name == raw_name,
        LgdUnresolved.entity_type == entity_type,
    )
    result = await session.execute(stmt)
    existing = result.scalars().first() if hasattr(result, "scalars") else None

    if existing:
        # Increment counter
        up = (
            update(LgdUnresolved)
            .where(LgdUnresolved.id == existing.id)
            .values(occurrence_count=LgdUnresolved.occurrence_count + 1)
        )
        await session.execute(up)
    else:
        entry = LgdUnresolved(
            raw_name=raw_name,
            entity_type=entity_type,
            state_hint=state_hint,
            district_hint=district_hint,
            best_guess_lgd_code=best_guess_lgd,
            confidence=best_guess_confidence,
            resolved=False,
            occurrence_count=1,
        )
        session.add(entry)

    try:
        await session.commit()
    except Exception:
        await session.rollback()
        logger.warning("Failed to enqueue unresolved LGD name: '%s' (%s)", raw_name, entity_type)
