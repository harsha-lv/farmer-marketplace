import math
from collections import defaultdict
from collections.abc import Sequence
from datetime import date, timedelta

from app.prices.schemas import (
    MandiVolatilityResponse,
    PriceRollupPoint,
)


def _week_bounds(d: date) -> tuple[date, date, str]:
    """Return (monday, sunday, iso_label) for a given date."""
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    iso_year, iso_week, _ = monday.isocalendar()
    label = f"{iso_year}-W{iso_week:02d}"
    return monday, sunday, label


def _month_bounds(d: date) -> tuple[date, date, str]:
    """Return (first_day, last_day, label) for a given date."""
    first_day = date(d.year, d.month, 1)
    if d.month == 12:
        next_month = date(d.year + 1, 1, 1)
    else:
        next_month = date(d.year, d.month + 1, 1)
    last_day = next_month - timedelta(days=1)
    label = f"{d.year}-{d.month:02d}"
    return first_day, last_day, label


def aggregate_weekly_rollups(
    series: Sequence[tuple[date, int, float, int, int]],
    lookback_weeks: int = 12,
) -> list[PriceRollupPoint]:
    """Aggregate daily observations (arrival_date, modal_price, arrivals_q, min_p, max_p)

    into weekly continuous rollups with Volume-Weighted Average Price (VWAP).
    """
    if not series:
        return []

    buckets: dict[date, list[tuple[date, int, float, int, int]]] = defaultdict(list)
    bound_map: dict[date, tuple[date, date, str]] = {}

    for row in series:
        monday, sunday, label = _week_bounds(row[0])
        buckets[monday].append(row)
        bound_map[monday] = (monday, sunday, label)

    sorted_weeks = sorted(buckets.keys())
    if lookback_weeks > 0 and len(sorted_weeks) > lookback_weeks:
        sorted_weeks = sorted_weeks[-lookback_weeks:]

    rollups: list[PriceRollupPoint] = []
    for week_start in sorted_weeks:
        rows = buckets[week_start]
        start_d, end_d, label = bound_map[week_start]

        min_price = min(r[3] for r in rows)
        max_price = max(r[4] for r in rows)
        avg_modal = int(round(sum(r[1] for r in rows) / len(rows)))

        total_vol = sum(r[2] for r in rows)
        weighted_val = sum(r[1] * r[2] for r in rows)
        if total_vol > 0:
            vwap = int(round(weighted_val / total_vol))
        else:
            vwap = avg_modal

        obs_days = len(set(r[0] for r in rows))

        rollups.append(
            PriceRollupPoint(
                period_start=start_d,
                period_end=end_d,
                period_label=label,
                min_price_inr=min_price,
                max_price_inr=max_price,
                avg_modal_price_inr=avg_modal,
                vwap_modal_price_inr=vwap,
                total_arrivals_quintal=round(float(total_vol), 2),
                observation_days=obs_days,
            )
        )

    return rollups


def aggregate_monthly_rollups(
    series: Sequence[tuple[date, int, float, int, int]],
    lookback_months: int = 12,
) -> list[PriceRollupPoint]:
    """Aggregate daily observations into monthly rollups with VWAP."""
    if not series:
        return []

    buckets: dict[date, list[tuple[date, int, float, int, int]]] = defaultdict(list)
    bound_map: dict[date, tuple[date, date, str]] = {}

    for row in series:
        first_d, last_d, label = _month_bounds(row[0])
        buckets[first_d].append(row)
        bound_map[first_d] = (first_d, last_d, label)

    sorted_months = sorted(buckets.keys())
    if lookback_months > 0 and len(sorted_months) > lookback_months:
        sorted_months = sorted_months[-lookback_months:]

    rollups: list[PriceRollupPoint] = []
    for m_start in sorted_months:
        rows = buckets[m_start]
        start_d, end_d, label = bound_map[m_start]

        min_price = min(r[3] for r in rows)
        max_price = max(r[4] for r in rows)
        avg_modal = int(round(sum(r[1] for r in rows) / len(rows)))

        total_vol = sum(r[2] for r in rows)
        weighted_val = sum(r[1] * r[2] for r in rows)
        if total_vol > 0:
            vwap = int(round(weighted_val / total_vol))
        else:
            vwap = avg_modal

        obs_days = len(set(r[0] for r in rows))

        rollups.append(
            PriceRollupPoint(
                period_start=start_d,
                period_end=end_d,
                period_label=label,
                min_price_inr=min_price,
                max_price_inr=max_price,
                avg_modal_price_inr=avg_modal,
                vwap_modal_price_inr=vwap,
                total_arrivals_quintal=round(float(total_vol), 2),
                observation_days=obs_days,
            )
        )

    return rollups


def calculate_mandi_volatility(
    series: Sequence[tuple[date, int, float, int, int]],
    *,
    commodity: str,
    lookback_days: int = 30,
    state: str | None = None,
    district: str | None = None,
    market: str | None = None,
) -> MandiVolatilityResponse:
    """Compute market volatility metrics, CV%, spread, and arrival volume shocks."""
    n = len(series)
    if n == 0:
        raise ValueError("Series cannot be empty for volatility calculation")

    modal_prices = [r[1] for r in series]
    mean_price = sum(modal_prices) / n
    mean_modal_price_inr = int(round(mean_price))

    if n > 1:
        variance = sum((p - mean_price) ** 2 for p in modal_prices) / (n - 1)
        std_dev = math.sqrt(variance)
    else:
        std_dev = 0.0

    cv = (std_dev / mean_price * 100.0) if mean_price > 0 else 0.0

    min_p = min(r[3] for r in series)
    max_p = max(r[4] for r in series)
    spread = max_p - min_p

    if cv < 5.0:
        rating = "LOW_VOLATILITY"
    elif cv <= 15.0:
        rating = "MODERATE_VOLATILITY"
    else:
        rating = "HIGH_VOLATILITY"

    # Volume shock analysis
    volumes = [r[2] for r in series]
    latest_vol = volumes[-1]
    avg_vol = sum(volumes) / n

    if avg_vol > 0:
        ratio = round(latest_vol / avg_vol, 2)
        if ratio > 1.5:
            is_shock = True
            shock_type = "SURGE"
        elif ratio < 0.5:
            is_shock = True
            shock_type = "DROP"
        else:
            is_shock = False
            shock_type = "NONE"
    else:
        is_shock = False
        shock_type = "NONE"
        ratio = None

    # Construct market commentary
    rating_desc = rating.replace("_", " ").lower()
    commentary = (
        f"Market exhibits {rating_desc} with a coefficient of variation of {cv:.2f}%. "
        f"Price spread over the {n} observation day(s) is INR {spread}/quintal."
    )
    if shock_type == "SURGE":
        surge_pct = int(round((ratio - 1.0) * 100))
        commentary += f" Supply surge detected: latest arrivals are {surge_pct}% above the historical baseline."
    elif shock_type == "DROP":
        drop_pct = int(round((1.0 - ratio) * 100))
        commentary += f" Supply deficit detected: latest arrivals are {drop_pct}% below the historical baseline."
    else:
        commentary += " Daily arrival volumes remain stable within the normal baseline."

    return MandiVolatilityResponse(
        commodity=commodity,
        state=state,
        district=district,
        market=market,
        lookback_days=lookback_days,
        observations=n,
        mean_modal_price_inr=mean_modal_price_inr,
        std_dev_inr=round(std_dev, 2),
        coefficient_of_variation_pct=round(cv, 2),
        min_price_inr=min_p,
        max_price_inr=max_p,
        price_spread_inr=spread,
        volatility_rating=rating,
        is_volume_shock=is_shock,
        volume_shock_type=shock_type,
        volume_shock_ratio=ratio,
        market_commentary=commentary,
    )
