from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class PriceRecord(BaseModel):
    arrival_date: date
    state: str
    state_lgd_code: str | None
    district: str
    district_lgd_code: str | None
    market: str
    commodity: str
    commodity_group: str | None
    variety: str
    grade: str
    min_price_inr_per_quintal: int
    max_price_inr_per_quintal: int
    modal_price_inr_per_quintal: int
    arrivals_quintal: Decimal | None


class PageMeta(BaseModel):
    limit: int
    offset: int
    count: int


class PriceListResponse(BaseModel):
    data: list[PriceRecord]
    meta: PageMeta


class IngestResponse(BaseModel):
    fetched: int
    stored: int
    skipped: int


class SaleWindowResponse(BaseModel):
    commodity: str
    state: str | None
    district: str | None
    market: str | None
    horizon_days: int
    lookback_days: int
    observations: int
    latest_arrival_date: date | None
    latest_modal_price_inr_per_quintal: int | None
    average_modal_price_inr_per_quintal: int | None
    projected_modal_price_inr_per_quintal: int | None
    storage_cost_inr_per_quintal: int
    recommendation: str
    reason: str


class PriceFilter(BaseModel):
    state: str | None = None
    district: str | None = None
    market: str | None = None
    commodity: str | None = None
    commodity_group: str | None = None
    variety: str | None = None
    grade: str | None = None
    arrival_from: date | None = None
    arrival_to: date | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class TftHorizonPoint(BaseModel):
    day_offset: int
    forecast_date: date
    p10_price_inr: int
    p50_price_inr: int
    p90_price_inr: int


class TftForecastResponse(BaseModel):
    commodity: str
    state: str | None = None
    district: str | None = None
    market: str | None = None
    horizon_days: int
    lookback_days: int
    observations: int
    latest_date: date | None = None
    latest_modal_price_inr: int | None = None
    p10_terminal_price_inr: int | None = None
    p50_terminal_price_inr: int | None = None
    p90_terminal_price_inr: int | None = None
    storage_cost_inr: int
    capital_cost_inr: int
    total_holding_cost_inr: int
    expected_net_gain_inr: int
    recommendation: str
    rationale: str
    horizons: list[TftHorizonPoint]
    attention_weights: list[float]


class PriceRollupPoint(BaseModel):
    period_start: date
    period_end: date
    period_label: str
    min_price_inr: int
    max_price_inr: int
    avg_modal_price_inr: int
    vwap_modal_price_inr: int
    total_arrivals_quintal: float
    observation_days: int


class WeeklyRollupResponse(BaseModel):
    commodity: str
    state: str | None = None
    district: str | None = None
    market: str | None = None
    lookback_weeks: int
    rollups: list[PriceRollupPoint]


class MonthlyRollupResponse(BaseModel):
    commodity: str
    state: str | None = None
    district: str | None = None
    market: str | None = None
    lookback_months: int
    rollups: list[PriceRollupPoint]


class MandiVolatilityResponse(BaseModel):
    commodity: str
    state: str | None = None
    district: str | None = None
    market: str | None = None
    lookback_days: int
    observations: int
    mean_modal_price_inr: int
    std_dev_inr: float
    coefficient_of_variation_pct: float
    min_price_inr: int
    max_price_inr: int
    price_spread_inr: int
    volatility_rating: str
    is_volume_shock: bool
    volume_shock_type: str
    volume_shock_ratio: float | None = None
    market_commentary: str


class IngestJobTrigger(BaseModel):
    job_id: str
    state: str | None = None
    commodity: str | None = None
    max_records: int = 100
    trigger_type: str = "SCHEDULED"
    rate_limit_delay_seconds: float = 0.05
    timestamp: datetime


class IngestJobStatusResponse(BaseModel):
    job_id: str
    status: str  # PENDING, RUNNING, SUCCESS, FAILED
    state: str | None = None
    commodity: str | None = None
    fetched: int = 0
    stored: int = 0
    skipped: int = 0
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    retries: int = 0


class HorizonRecommendationSchema(BaseModel):
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
    recommendation: str  # STORE, SELL, HEDGE
    rationale: str
    facility_available: bool


class MlForecastResponse(BaseModel):
    commodity: str
    market: str
    as_of_date: date
    current_modal_price_inr: float
    model_version: str
    model_architecture: str
    model_status: str
    fallback_used: str | None = None
    storage_type: str
    facility_available: bool
    overall_recommendation: str
    primary_horizon_days: int
    horizons: list[HorizonRecommendationSchema]
    shadow_evaluation: dict[str, Any] | None = None




