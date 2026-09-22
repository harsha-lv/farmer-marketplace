from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SaleWindow:
    observations: int
    latest_arrival_date: date | None
    latest_modal_price_inr_per_quintal: int | None
    average_modal_price_inr_per_quintal: int | None
    projected_modal_price_inr_per_quintal: int | None
    storage_cost_inr_per_quintal: int
    recommendation: str
    reason: str


def recommend_sale_window(
    series: list[tuple[date, int]],
    *,
    horizon_days: int,
    storage_cost_per_quintal_per_day: int,
) -> SaleWindow:
    storage_cost = storage_cost_per_quintal_per_day * horizon_days
    if not series:
        return SaleWindow(
            observations=0,
            latest_arrival_date=None,
            latest_modal_price_inr_per_quintal=None,
            average_modal_price_inr_per_quintal=None,
            projected_modal_price_inr_per_quintal=None,
            storage_cost_inr_per_quintal=storage_cost,
            recommendation="sell",
            reason="no stored prices are available for this selection",
        )

    latest_date, latest_price = series[-1]
    average = int(round(sum(price for _, price in series) / len(series)))
    projected = _project(series, horizon_days)
    gain = projected - latest_price
    if len(series) < 2:
        recommendation = "sell"
        reason = "only one price is stored, so there is no trend to justify storage"
    elif gain > storage_cost:
        recommendation = "store"
        reason = (
            f"straight-line projection rises by {gain} rupees per quintal "
            f"over {horizon_days} days, above the {storage_cost} rupee storage cost"
        )
    else:
        recommendation = "sell"
        reason = (
            f"straight-line projection changes by {gain} rupees per quintal "
            f"over {horizon_days} days, which does not cover the {storage_cost} rupee storage cost"
        )
    return SaleWindow(
        observations=len(series),
        latest_arrival_date=latest_date,
        latest_modal_price_inr_per_quintal=latest_price,
        average_modal_price_inr_per_quintal=average,
        projected_modal_price_inr_per_quintal=projected,
        storage_cost_inr_per_quintal=storage_cost,
        recommendation=recommendation,
        reason=reason,
    )


def _project(series: list[tuple[date, int]], horizon_days: int) -> int:
    if len(series) < 2:
        return series[-1][1]
    start = series[0][0]
    points = [((day - start).days, price) for day, price in series]
    count = len(points)
    sum_x = sum(day for day, _ in points)
    sum_y = sum(price for _, price in points)
    sum_xy = sum(day * price for day, price in points)
    sum_xx = sum(day * day for day, _ in points)
    denominator = count * sum_xx - sum_x * sum_x
    if denominator == 0:
        return points[-1][1]
    slope = (count * sum_xy - sum_x * sum_y) / denominator
    intercept = (sum_y - slope * sum_x) / count
    projected = int(round(intercept + slope * (points[-1][0] + horizon_days)))
    return max(projected, 0)
