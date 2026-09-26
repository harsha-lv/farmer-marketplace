"""Extended Multi-Horizon Recommendation Engine (STORE, SELL, HEDGE).

Evaluates commercial holding decisions factoring in:
  - Commodity storage costs (dry warehouse vs cold storage)
  - Capital carrying interest cost (annualized bps over holding horizon)
  - Commodity-specific spoilage and quality deterioration risk
  - Physical facility availability from logistics/warehouse network
  - 7-day, 14-day, and 21-day probabilistic quantile breakdown (p10, p50, p90)
"""

import math
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

from app.prices.tft import HorizonPrediction


@dataclass(frozen=True)
class CommodityPerishabilityProfile:
    daily_spoilage_rate: float  # Fraction lost/deteriorated per day
    storage_type: str  # "DRY_WAREHOUSE" or "COLD_STORAGE"
    default_storage_rate_inr: float  # INR per quintal per day


COMMODITY_PROFILES: dict[str, CommodityPerishabilityProfile] = {
    # Perishables (Cold storage / high spoilage)
    "TOMATO": CommodityPerishabilityProfile(0.0080, "COLD_STORAGE", 3.00),
    "ONION": CommodityPerishabilityProfile(0.0035, "COLD_STORAGE", 2.20),
    "POTATO": CommodityPerishabilityProfile(0.0020, "COLD_STORAGE", 2.00),
    # Oilseeds & Pulses (Moderate)
    "SOYABEAN": CommodityPerishabilityProfile(0.0003, "DRY_WAREHOUSE", 0.60),
    "SOYBEAN": CommodityPerishabilityProfile(0.0003, "DRY_WAREHOUSE", 0.60),
    "MUSTARD": CommodityPerishabilityProfile(0.0002, "DRY_WAREHOUSE", 0.55),
    "CHANA": CommodityPerishabilityProfile(0.0002, "DRY_WAREHOUSE", 0.50),
    "GRAM": CommodityPerishabilityProfile(0.0002, "DRY_WAREHOUSE", 0.50),
    "TUR": CommodityPerishabilityProfile(0.0002, "DRY_WAREHOUSE", 0.50),
    "MOONG": CommodityPerishabilityProfile(0.0002, "DRY_WAREHOUSE", 0.50),
    # Durable Grains (Low spoilage)
    "WHEAT": CommodityPerishabilityProfile(0.0001, "DRY_WAREHOUSE", 0.45),
    "PADDY": CommodityPerishabilityProfile(0.0001, "DRY_WAREHOUSE", 0.45),
    "MAIZE": CommodityPerishabilityProfile(0.0002, "DRY_WAREHOUSE", 0.45),
    "COTTON": CommodityPerishabilityProfile(0.0001, "DRY_WAREHOUSE", 0.70),
}


@dataclass
class HorizonRecommendation:
    horizon_days: int
    target_date: date
    p10_price_inr: float
    p50_price_inr: float
    p90_price_inr: float
    storage_cost_inr: float
    capital_cost_inr: float
    spoilage_cost_inr: float
    total_holding_cost_inr: float
    expected_net_gain_inr: float
    downside_risk_inr: float
    recommendation: str  # "STORE", "SELL", "HEDGE"
    rationale: str
    facility_available: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RecommendationPlan:
    commodity: str
    market: str
    as_of_date: date
    current_modal_price_inr: float
    storage_type: str
    facility_available: bool
    overall_recommendation: str
    primary_horizon_days: int
    horizons: list[HorizonRecommendation]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def generate_recommendation_plan(
    commodity: str,
    market: str,
    as_of_date: date,
    current_price: float,
    predictions: dict[int, HorizonPrediction],
    storage_cost_per_day: float | None = None,
    capital_interest_rate_bps: int = 700,  # 7.00%
    facility_available: bool = True,
) -> RecommendationPlan:
    """Evaluate financial holding economics and return comprehensive multi-horizon recommendations."""
    norm_comm = commodity.strip().upper()
    profile = None
    for key, p in COMMODITY_PROFILES.items():
        if key in norm_comm or norm_comm in key:
            profile = p
            break
    if profile is None:
        profile = CommodityPerishabilityProfile(0.0002, "DRY_WAREHOUSE", 0.50)

    daily_storage = storage_cost_per_day if storage_cost_per_day is not None and storage_cost_per_day > 0 else profile.default_storage_rate_inr
    spoilage_rate = profile.daily_spoilage_rate
    annual_interest = capital_interest_rate_bps / 10000.0

    horizon_results: list[HorizonRecommendation] = []

    for h_days in sorted(predictions.keys()):
        pred = predictions[h_days]
        target_d = as_of_date + timedelta(days=h_days)

        # 1. Costs over horizon
        storage_cost = round(daily_storage * h_days, 2)
        capital_cost = round(current_price * (annual_interest * (h_days / 365.25)), 2)
        # Spoilage cost: percentage of produce deteriorated
        spoilage_fraction = 1.0 - math.pow(1.0 - spoilage_rate, h_days)
        spoilage_cost = round(current_price * spoilage_fraction, 2)
        total_holding_cost = round(storage_cost + capital_cost + spoilage_cost, 2)

        # 2. Net return expectations
        expected_gain = round(pred.p50 - current_price - total_holding_cost, 2)
        downside_risk = round(pred.p10 - current_price - total_holding_cost, 2)

        # 3. Decision Logic
        if not facility_available:
            rec = "SELL"
            rationale = (
                f"No certified {profile.storage_type.replace('_', ' ').lower()} capacity available "
                f"near {market}. Immediate sale is recommended to eliminate holding risks."
            )
        elif expected_gain <= 0:
            rec = "SELL"
            rationale = (
                f"Expected price of ₹{pred.p50} does not cover total holding costs of ₹{total_holding_cost} "
                f"(storage: ₹{storage_cost}, capital: ₹{capital_cost}, spoilage: ₹{spoilage_cost}). "
                f"Expected net loss: ₹{abs(expected_gain)}/qtl over {h_days} days."
            )
        elif downside_risk < -0.06 * current_price:
            # Significant downside tail risk
            rec = "HEDGE"
            rationale = (
                f"Expected price rises to ₹{pred.p50} (net gain ₹{expected_gain}/qtl), but p10 downside "
                f"drops to ₹{pred.p10} (downside risk ₹{abs(downside_risk)}/qtl). "
                f"Lock in price via e-NAM forward contract or warehouse receipt pledge."
            )
        else:
            rec = "STORE"
            rationale = (
                f"Expected price rises to ₹{pred.p50} over {h_days} days. Net gain after holding costs "
                f"(₹{total_holding_cost}) is ₹{expected_gain}/qtl with limited downside risk (p10: ₹{pred.p10})."
            )

        horizon_results.append(
            HorizonRecommendation(
                horizon_days=h_days,
                target_date=target_d,
                p10_price_inr=pred.p10,
                p50_price_inr=pred.p50,
                p90_price_inr=pred.p90,
                storage_cost_inr=storage_cost,
                capital_cost_inr=capital_cost,
                spoilage_cost_inr=spoilage_cost,
                total_holding_cost_inr=total_holding_cost,
                expected_net_gain_inr=expected_gain,
                downside_risk_inr=downside_risk,
                recommendation=rec,
                rationale=rationale,
                facility_available=facility_available,
            )
        )

    # Primary recommendation based on 14-day horizon (or first available)
    primary_h = 14 if 14 in [h.horizon_days for h in horizon_results] else horizon_results[0].horizon_days
    primary_res = next(h for h in horizon_results if h.horizon_days == primary_h)

    return RecommendationPlan(
        commodity=commodity,
        market=market,
        as_of_date=as_of_date,
        current_modal_price_inr=round(current_price, 2),
        storage_type=profile.storage_type,
        facility_available=facility_available,
        overall_recommendation=primary_res.recommendation,
        primary_horizon_days=primary_h,
        horizons=horizon_results,
    )
