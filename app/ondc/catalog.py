from datetime import UTC, datetime

REQUIRED_CONTEXT = (
    "domain",
    "action",
    "version",
    "bap_id",
    "bap_uri",
    "transaction_id",
    "message_id",
    "timestamp",
)


def context_error(context: object, *, action: str = "search") -> str | None:
    if not isinstance(context, dict):
        return "context is required"
    missing = [field for field in REQUIRED_CONTEXT if not str(context.get(field, "")).strip()]
    if missing:
        return f"context is missing {missing[0]}"
    if context.get("domain") != "ONDC:AGR10":
        return "domain is not supported"
    if context.get("action") != action:
        return f"action must be {action}"
    if context.get("version") != "2.0.0":
        return "version is not supported"
    return None


def intent_filters(message: object) -> tuple[str | None, str | None]:
    if not isinstance(message, dict):
        return None, None
    intent = message.get("intent")
    if not isinstance(intent, dict):
        return None, None
    item = intent.get("item")
    if not isinstance(item, dict):
        return None, None
    descriptor = item.get("descriptor")
    if not isinstance(descriptor, dict):
        return None, None
    return _text(descriptor.get("name")), _text(descriptor.get("code"))


def grade_matches(stored: str, requested: str | None) -> bool:
    if requested is None:
        return True
    left = stored.casefold()
    right = requested.casefold()
    return left == right or right.startswith(left)


def catalog_item(lot) -> dict:
    tags = [{"code": "enam_lot_id", "value": lot.enam_lot_id}]
    if lot.warehouse_receipt_id:
        tags.append({"code": "warehouse_receipt_id", "value": lot.warehouse_receipt_id})
    return {
        "id": lot.lot_code,
        "descriptor": {"name": lot.commodity, "code": lot.assay.grade},
        "quantity": {
            "available": {"count": 1},
            "measure": {"unit": "metric_ton", "value": str(lot.quantity_mt)},
        },
        "tags": tags,
    }


def build_catalog(lots: list, bpp_name: str) -> dict:
    grouped: dict[str, list[dict]] = {}
    for lot in lots:
        grouped.setdefault(lot.farmer_id, []).append(catalog_item(lot))
    return {
        "bpp/descriptor": {"name": bpp_name},
        "bpp/providers": [{"id": farmer_id, "items": items} for farmer_id, items in grouped.items()],
    }


def response_context(request_context: dict, *, action: str, bpp_id: str, bpp_uri: str) -> dict:
    return {
        "domain": request_context.get("domain", "ONDC:AGR10"),
        "action": action,
        "version": request_context.get("version", "2.0.0"),
        "bap_id": request_context.get("bap_id", ""),
        "bap_uri": request_context.get("bap_uri", ""),
        "bpp_id": bpp_id,
        "bpp_uri": bpp_uri,
        "transaction_id": request_context.get("transaction_id", ""),
        "message_id": request_context.get("message_id", ""),
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def ack(context: dict) -> dict:
    return {"context": context, "message": {"ack": {"status": "ACK"}}}


def nack(context: dict, message: str) -> dict:
    return {
        "context": context,
        "message": {"ack": {"status": "NACK"}},
        "error": {"code": "400", "message": message},
    }


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
