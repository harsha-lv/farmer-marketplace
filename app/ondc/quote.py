from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

QUINTALS_PER_METRIC_TON = Decimal(10)


def build_quote(
    quantity_mt: Decimal,
    modal_inr_per_quintal: int,
    freight_quotes: list[Any] | None = None,
) -> dict:
    item_value = (quantity_mt * QUINTALS_PER_METRIC_TON * modal_inr_per_quintal).to_integral_value(
        rounding=ROUND_HALF_UP
    )
    delivery_price = 0
    if freight_quotes:
        first = freight_quotes[0]
        delivery_price = first.price_inr if hasattr(first, "price_inr") else first.get("price_inr", 0)

    total_price = item_value + delivery_price

    res: dict[str, Any] = {
        "price": {"currency": "INR", "value": str(total_price)},
        "breakup": [
            {"title": "item", "price": {"currency": "INR", "value": str(item_value)}},
            {"title": "delivery", "price": {"currency": "INR", "value": str(delivery_price)}},
        ],
    }
    if freight_quotes:
        res["freight_options"] = [
            f.to_dict() if hasattr(f, "to_dict") else f for f in freight_quotes
        ]
    return res


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
