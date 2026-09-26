from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


def delivery_terms(order: dict) -> dict | str:
    billing = order.get("billing")
    if not isinstance(billing, dict):
        return "billing name is required"
    name = str(billing.get("name", "")).strip()
    address = str(billing.get("address", "")).strip()
    if not name:
        return "billing name is required"
    if not address:
        return "billing address is required"
    if len(name) > 256 or len(address) > 512:
        return "billing details are too long"
    phone = billing.get("phone")
    phone_text = str(phone).strip() if phone not in (None, "") else None
    if phone_text is not None and len(phone_text) > 32:
        return "billing details are too long"
    gps = _gps(order.get("fulfillment"))
    if gps is None:
        return "delivery location is required"
    return {"name": name, "address": address, "phone": phone_text, "gps": gps}


def quote_with_commission(quantity_mt: Decimal, modal_inr_per_quintal: int, commission_percent: int) -> dict:
    item_value = int((quantity_mt * Decimal(10) * modal_inr_per_quintal).to_integral_value(rounding=ROUND_HALF_UP))
    percent = min(max(commission_percent, 0), 100)
    commission = int((Decimal(item_value) * percent / Decimal(100)).to_integral_value(rounding=ROUND_HALF_UP))
    total = item_value + commission
    return {
        "price": {"currency": "INR", "value": str(total)},
        "breakup": [
            {"title": "item", "price": {"currency": "INR", "value": str(item_value)}},
            {"title": "delivery", "price": {"currency": "INR", "value": "0"}},
            {"title": "commission", "price": {"currency": "INR", "value": str(commission)}},
        ],
    }


def _gps(fulfillment: object) -> str | None:
    if not isinstance(fulfillment, dict):
        return None
    end = fulfillment.get("end")
    if not isinstance(end, dict):
        return None
    location = end.get("location")
    if not isinstance(location, dict):
        return None
    raw = str(location.get("gps", "")).strip()
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != 2:
        return None
    try:
        latitude = Decimal(parts[0])
        longitude = Decimal(parts[1])
    except InvalidOperation:
        return None
    if latitude < -90 or latitude > 90 or longitude < -180 or longitude > 180:
        return None
    return f"{latitude},{longitude}"
