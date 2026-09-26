"""Cache invalidation hooks for domain lifecycle events.

Triggers:
  - consent revoked -> flush farmer profile, parcel, lot, price-personalised keys
  - lot status change / contract state change -> flush lot availability + ONDC catalog keys
  - new price observation -> flush mandi price snapshot + VWAP keys for that market
  - assay report created -> flush lot grade keys
"""

import logging

from app.cache.service import CacheService, get_cache_service

logger = logging.getLogger("app.cache.hooks")


async def on_consent_revoked(
    farmer_id: str,
    consent_artifact_id: str | None = None,
    tenant: str = "*",
    service: CacheService | None = None,
) -> int:
    """Flush farmer profile, parcel, lot, and price-personalised cache keys upon consent revocation."""
    cache = service or get_cache_service()
    patterns = [
        f"agri:{tenant}:farmer:{farmer_id}*",
        f"agri:{tenant}:farmer:profile:{farmer_id}*",
        f"agri:{tenant}:parcel:*{farmer_id}*",
        f"agri:{tenant}:parcel:*",
        f"agri:{tenant}:lot:*{farmer_id}*",
        f"agri:{tenant}:price:personalised:{farmer_id}*",
        f"agri:{tenant}:consent:*{farmer_id}*",
    ]
    if consent_artifact_id:
        patterns.append(f"agri:{tenant}:consent:*{consent_artifact_id}*")

    total_cleared = 0
    for p in patterns:
        total_cleared += await cache.invalidate(p)

    total_cleared += await cache.invalidate_tags(f"farmer:{farmer_id}", f"consent:{consent_artifact_id or ''}")
    try:
        from app.telemetry.metrics import track_consent_revocation
        track_consent_revocation(action="cache_purge")
    except Exception:
        pass
    logger.info("Executed on_consent_revoked hook for farmer %s (cleared %d keys)", farmer_id, total_cleared)
    return total_cleared


async def on_lot_status_changed(
    lot_id: str,
    lot_code: str | None = None,
    tenant: str = "*",
    service: CacheService | None = None,
) -> int:
    """Flush lot availability and ONDC catalog keys when lot state updates."""
    cache = service or get_cache_service()
    patterns = [
        f"agri:{tenant}:lot:availability*",
        f"agri:{tenant}:ondc:catalog*",
        f"agri:{tenant}:lot:{lot_id}*",
    ]
    if lot_code:
        patterns.append(f"agri:{tenant}:lot:{lot_code}*")

    total_cleared = 0
    for p in patterns:
        total_cleared += await cache.invalidate(p)

    total_cleared += await cache.invalidate_tags(f"lot:{lot_id}", f"lot:{lot_code or ''}")
    logger.info("Executed on_lot_status_changed hook for lot %s (cleared %d keys)", lot_id, total_cleared)
    return total_cleared


async def on_contract_state_changed(
    contract_id: str,
    lot_id: str | None = None,
    tenant: str = "*",
    service: CacheService | None = None,
) -> int:
    """Flush lot availability and contract catalog keys upon trade contract changes."""
    cache = service or get_cache_service()
    patterns = [
        f"agri:{tenant}:lot:availability*",
        f"agri:{tenant}:ondc:catalog*",
        f"agri:{tenant}:trade:contract:{contract_id}*",
        f"agri:{tenant}:trade:{contract_id}*",
    ]
    if lot_id:
        patterns.append(f"agri:{tenant}:lot:{lot_id}*")

    total_cleared = 0
    for p in patterns:
        total_cleared += await cache.invalidate(p)

    logger.info("Executed on_contract_state_changed hook for contract %s (cleared %d keys)", contract_id, total_cleared)
    return total_cleared


async def on_price_observation_ingested(
    market_id: str,
    commodity: str | None = None,
    tenant: str = "*",
    service: CacheService | None = None,
) -> int:
    """Flush mandi price snapshot and VWAP keys for that market on new price observation."""
    cache = service or get_cache_service()
    patterns = [
        f"agri:{tenant}:price:snapshot:{market_id}*",
        f"agri:{tenant}:price:vwap:{market_id}*",
        f"agri:{tenant}:price:mandi:{market_id}*",
    ]
    if commodity:
        patterns.append(f"agri:{tenant}:price:*{commodity.lower()}*")

    total_cleared = 0
    for p in patterns:
        total_cleared += await cache.invalidate(p)

    total_cleared += await cache.invalidate_tags(f"market:{market_id}", f"commodity:{commodity or ''}")
    logger.info("Executed on_price_observation_ingested hook for market %s (cleared %d keys)", market_id, total_cleared)
    return total_cleared


async def on_assay_report_created(
    lot_id: str,
    tenant: str = "*",
    service: CacheService | None = None,
) -> int:
    """Flush lot grade keys when assay report is issued."""
    cache = service or get_cache_service()
    patterns = [
        f"agri:{tenant}:lot:grade:{lot_id}*",
        f"agri:{tenant}:lot:{lot_id}*",
        f"agri:{tenant}:assay:{lot_id}*",
    ]
    total_cleared = 0
    for p in patterns:
        total_cleared += await cache.invalidate(p)

    total_cleared += await cache.invalidate_tags(f"lot:{lot_id}", f"assay:{lot_id}")
    logger.info("Executed on_assay_report_created hook for lot %s (cleared %d keys)", lot_id, total_cleared)
    return total_cleared
