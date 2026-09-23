from datetime import UTC, datetime

from app.consent.repository import ConsentRepository
from app.consent.signing import authorize_profile_fetch


def parse_order(message: object) -> tuple[dict, str | None] | str:
    if not isinstance(message, dict):
        return "one item is required"
    order = message.get("order")
    if not isinstance(order, dict):
        return "one item is required"
    items = order.get("items")
    if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
        return "one item is required"
    if not str(items[0].get("id", "")).strip():
        return "one item is required"
    provider = order.get("provider")
    provider_id = None
    if isinstance(provider, dict) and str(provider.get("id", "")).strip():
        provider_id = str(provider["id"]).strip()
    return items[0], provider_id


async def unavailable_reason(lot, provider_id: str | None, farmers, consents) -> str | None:
    if lot is None or lot.assay is None or not lot.enam_lot_id:
        return "item is not available"
    if provider_id is not None and provider_id != lot.farmer_id:
        return "provider does not match the item"
    farmer = await farmers.get(lot.farmer_id)
    artifact = await consents.get(lot.consent_artifact_id)
    if farmer is None or farmer.consent_artifact_id != lot.consent_artifact_id:
        return "item is not available"
    record = None if artifact is None else ConsentRepository.record(artifact)
    if authorize_profile_fetch(record, lot.farmer_id, datetime.now(UTC)) is not None:
        return "item is not available"
    return None
