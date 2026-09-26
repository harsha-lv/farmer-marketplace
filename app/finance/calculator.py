from decimal import ROUND_HALF_UP, Decimal


def calculate_pledge_eligibility(
    quantity_mt: Decimal,
    modal_price_per_mt: int,
    ltv_ratio: Decimal = Decimal("0.75"),
) -> tuple[int, int]:
    """Calculate total crop valuation and maximum allowable pledge loan amount under LTV cap.

    Returns:
        tuple[int, int]: (valuation_inr, max_borrowable_inr)
    """
    if quantity_mt <= Decimal(0) or modal_price_per_mt <= 0 or ltv_ratio <= Decimal(0):
        return 0, 0

    valuation = (quantity_mt * Decimal(modal_price_per_mt)).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    valuation_inr = int(valuation)
    max_borrowable = (Decimal(valuation_inr) * ltv_ratio).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return valuation_inr, int(max_borrowable)


def calculate_accrued_interest(
    principal_inr: int,
    interest_rate_bps: int,
    days_elapsed: int,
) -> int:
    """Calculate simple accrued interest on a pledge loan using basis points per annum.

    Formula: principal * (bps / 10000) * (days / 365)
    """
    if principal_inr <= 0 or interest_rate_bps <= 0 or days_elapsed <= 0:
        return 0

    annual_rate = Decimal(interest_rate_bps) / Decimal(10000)
    time_fraction = Decimal(days_elapsed) / Decimal(365)
    accrued = (Decimal(principal_inr) * annual_rate * time_fraction).quantize(
        Decimal(1), rounding=ROUND_HALF_UP
    )
    return int(accrued)


def calculate_total_payoff(
    principal_inr: int,
    interest_rate_bps: int,
    days_elapsed: int,
) -> tuple[int, int]:
    """Calculate total payoff breakdown for loan closure.

    Returns:
        tuple[int, int]: (accrued_interest_inr, total_payoff_inr)
    """
    interest_inr = calculate_accrued_interest(principal_inr, interest_rate_bps, days_elapsed)
    return interest_inr, principal_inr + interest_inr
