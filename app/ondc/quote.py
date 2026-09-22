from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

QUINTALS_PER_METRIC_TON = Decimal(10)


def build_quote(quantity_mt: Decimal, modal_inr_per_quintal: int) -> dict:
    item_value = (quantity_mt * QUINTALS_PER_METRIC_TON * modal_inr_per_quintal).to_integral_value(
        rounding=ROUND_HALF_UP
    )
    return {
        "price": {"currency": "INR", "value": str(item_value)},
        "breakup": [
            {"title": "item", "price": {"currency": "INR", "value": str(item_value)}},
            {"title": "delivery", "price": {"currency": "INR", "value": "0"}},
        ],
    }


def selected_quantity(item: dict, available_mt: Decimal) -> Decimal | str:
    quantity = item.get("quantity")
    measure = quantity.get("measure") if isinstance(quantity, dict) else None
    raw = measure.get("value") if isinstance(measure, dict) else None
    if raw in (None, ""):
        return available_mt
    try:
        requested = Decimal(str(raw))
    except InvalidOperation:
        return "quantity is not a number"
    if requested <= 0 or requested > available_mt:
        return "quantity is not available"
    return requested
