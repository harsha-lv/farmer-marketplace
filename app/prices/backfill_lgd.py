"""Backfill LGD codes on existing price_observations rows.

Usage::

    python -m app.prices.backfill_lgd

Iterates all markets that lack ``lgd_market_id`` on their price_observations,
runs the resolver cascade, and updates the row. Reports unresolved counts at
the end.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select, update

logger = logging.getLogger("app.prices.backfill_lgd")


async def _run() -> None:
    from app.config import get_settings
    from app.db.session import Database
    from app.prices.lgd_resolver import resolve_market
    from app.prices.models import Market, PriceObservation

    settings = get_settings()
    db = Database(settings.database_url)

    resolved_count = 0
    unresolved_count = 0

    try:
        async with db.session_factory() as session:
            # Get all distinct markets referenced in price_observations
            stmt = select(Market)
            result = await session.execute(stmt)
            markets = list(result.scalars().all())

            logger.info("Backfilling LGD codes for %d markets…", len(markets))

            for market in markets:
                res = await resolve_market(
                    session,
                    raw_market_name=market.market_name,
                    state_lgd_code=market.state_lgd_code,
                )

                if res.entity_id is not None:
                    # Update the market record with the lgd district code
                    if not market.district_lgd_code:
                        up = (
                            update(Market)
                            .where(Market.id == market.id)
                            .values(district_lgd_code=res.lgd_code)
                        )
                        await session.execute(up)

                    # Update price_observations referencing this market
                    obs_up = (
                        update(PriceObservation)
                        .where(PriceObservation.market_id == market.id)
                        .where(PriceObservation.lgd_market_id.is_(None))
                        .values(
                            lgd_market_id=res.entity_id,
                            lgd_resolution_method=res.method,
                            lgd_resolution_confidence=res.confidence,
                        )
                    )
                    await session.execute(obs_up)
                    resolved_count += 1
                    logger.info(
                        "  ✓ %s → LGD market %s (%s, confidence=%.2f)",
                        market.market_name,
                        res.entity_id,
                        res.method,
                        res.confidence,
                    )
                else:
                    unresolved_count += 1
                    logger.warning(
                        "  ✗ %s → UNRESOLVED (state=%s, district=%s)",
                        market.market_name,
                        market.state_name,
                        market.district_name,
                    )

            await session.commit()
    finally:
        await db.dispose()

    logger.info(
        "Backfill complete: %d resolved, %d unresolved (check GET /api/v1/admin/lgd/unresolved)",
        resolved_count,
        unresolved_count,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(_run())


if __name__ == "__main__":
    main()
