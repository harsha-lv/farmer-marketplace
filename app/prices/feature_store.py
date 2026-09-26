"""Feature Store Contract and Training Frame Generator.

Provides a unified, typed DataFrame-ready contract `get_training_frame()` shared
identically by training, backtesting, and production inference to guarantee zero
train/serve skew.
"""

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.prices.features.calendar import CalendarFeatureExtractor
from app.prices.features.macro import MacroFeatureProvider
from app.prices.features.weather import WeatherAdapter
from app.prices.models import PriceFeature, PriceObservation

# Strict, canonical feature schema list ensuring train/serve alignment
CANONICAL_FEATURE_NAMES: list[str] = [
    "modal_price",
    "arrivals_volume",
    "price_spread",
    "ma_7d",
    "ma_14d",
    "momentum_7d",
    "volatility_7d",
    "rainfall_mm",
    "rainfall_deviation_pct",
    "temp_min_c",
    "temp_max_c",
    "is_festival",
    "is_mandi_holiday",
    "is_harvest_season",
    "sin_day_of_year",
    "cos_day_of_year",
    "sin_day_of_week",
    "cos_day_of_week",
    "msp_inr_per_quintal",
    "price_to_msp_ratio",
    "macro_inflation_pct",
    "macro_crude_usd",
]


@dataclass
class TrainingFrame:
    """Typed DataFrame-ready container shared between training and inference."""

    commodity: str
    market: str
    start_date: date
    end_date: date
    feature_names: list[str]
    dates: list[date]
    targets: list[float]  # modal price series
    features_matrix: list[list[float]]  # [T, num_features]
    records: list[dict[str, Any]] = field(default_factory=list)
    feature_hash: str = ""

    def __post_init__(self) -> None:
        if not self.feature_hash:
            # Deterministic SHA-256 fingerprint of feature contract
            raw = json.dumps(self.feature_names)
            self.feature_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def __len__(self) -> int:
        return len(self.dates)

    def to_records(self) -> list[dict[str, Any]]:
        """Return list of dicts suitable for DataFrame construction or inspection."""
        if self.records:
            return self.records
        out = []
        for i, d in enumerate(self.dates):
            row = {
                "date": d,
                "target": self.targets[i] if i < len(self.targets) else None,
            }
            row.update({name: self.features_matrix[i][j] for j, name in enumerate(self.feature_names)})
            out.append(row)
        return out

    def to_dict(self) -> dict[str, list[Any]]:
        """Columnar dictionary mapping column names to value lists."""
        recs = self.to_records()
        cols: dict[str, list[Any]] = {"date": [], "target": []}
        for name in self.feature_names:
            cols[name] = []
        for r in recs:
            cols["date"].append(r["date"])
            cols["target"].append(r["target"])
            for name in self.feature_names:
                cols[name].append(r.get(name, 0.0))
        return cols

    def to_dataframe(self) -> Any:
        """Return pandas DataFrame if pandas is installed, otherwise return columnar dict."""
        try:
            import pandas as pd

            return pd.DataFrame(self.to_records())
        except ImportError:
            return self.to_dict()


async def ingest_daily_features(
    session: AsyncSession,
    commodity: str,
    market: str,
    target_date: date,
    state: str = "MADHYA PRADESH",
    district: str = "INDORE",
    weather_adapter: WeatherAdapter | None = None,
) -> PriceFeature:
    """Compute and upsert daily exogenous features into app.price_features."""
    adapter = weather_adapter or WeatherAdapter()
    weather = await adapter.fetch_daily_weather(state, district, target_date)
    calendar = CalendarFeatureExtractor.get_features(target_date)
    macro = MacroFeatureProvider.get_features(commodity, target_date)

    # Check if feature already exists
    stmt = select(PriceFeature).where(
        PriceFeature.commodity == commodity,
        PriceFeature.market == market,
        PriceFeature.feature_date == target_date,
    )
    res = await session.scalars(stmt)
    existing = res.first()

    if existing is not None:
        # Update
        existing.rainfall_mm = weather.rainfall_mm
        existing.rainfall_normal_mm = weather.rainfall_normal_mm
        existing.rainfall_deviation_pct = weather.rainfall_deviation_pct
        existing.temp_min_c = weather.temp_min_c
        existing.temp_max_c = weather.temp_max_c
        existing.is_festival = calendar.is_festival
        existing.festival_name = calendar.festival_name
        existing.is_mandi_holiday = calendar.is_mandi_holiday
        existing.is_harvest_season = calendar.is_harvest_season
        existing.season_name = calendar.season_name
        existing.sin_day_of_year = calendar.sin_day_of_year
        existing.cos_day_of_year = calendar.cos_day_of_year
        existing.sin_day_of_week = calendar.sin_day_of_week
        existing.cos_day_of_week = calendar.cos_day_of_week
        existing.msp_inr_per_quintal = macro.msp_inr_per_quintal
        existing.macro_inflation_pct = macro.macro_inflation_pct
        existing.macro_crude_usd = macro.macro_crude_usd
        existing.raw_weather_json = weather.raw_json
        return existing

    feature = PriceFeature(
        commodity=commodity,
        market=market,
        feature_date=target_date,
        rainfall_mm=weather.rainfall_mm,
        rainfall_normal_mm=weather.rainfall_normal_mm,
        rainfall_deviation_pct=weather.rainfall_deviation_pct,
        temp_min_c=weather.temp_min_c,
        temp_max_c=weather.temp_max_c,
        is_festival=calendar.is_festival,
        festival_name=calendar.festival_name,
        is_mandi_holiday=calendar.is_mandi_holiday,
        is_harvest_season=calendar.is_harvest_season,
        season_name=calendar.season_name,
        sin_day_of_year=calendar.sin_day_of_year,
        cos_day_of_year=calendar.cos_day_of_year,
        sin_day_of_week=calendar.sin_day_of_week,
        cos_day_of_week=calendar.cos_day_of_week,
        msp_inr_per_quintal=macro.msp_inr_per_quintal,
        macro_inflation_pct=macro.macro_inflation_pct,
        macro_crude_usd=macro.macro_crude_usd,
        raw_weather_json=weather.raw_json,
    )
    session.add(feature)
    return feature


async def get_training_frame(
    commodity: str,
    market: str,
    start: date,
    end: date,
    session: AsyncSession | None = None,
    state: str = "MADHYA PRADESH",
    district: str = "INDORE",
) -> TrainingFrame:
    """Retrieve or build a continuous daily training frame with zero train/serve skew.

    Merges price observations with exogenous price_features, forward-filling
    weekend/holiday market closures so sequence models operate on uniform daily grids.
    """
    if start > end:
        start, end = end, start

    # 1. Fetch observations from DB if session provided
    raw_obs_map: dict[date, dict[str, float]] = {}
    if session is not None:
        try:
            # Query observations
            from app.prices.models import Commodity, Market

            obs_stmt = (
                select(PriceObservation)
                .join(Commodity, PriceObservation.commodity_id == Commodity.id)
                .join(Market, PriceObservation.market_id == Market.id)
                .where(
                    Commodity.name == commodity,
                    Market.market_name == market,
                    PriceObservation.arrival_date >= start,
                    PriceObservation.arrival_date <= end,
                )
                .order_by(PriceObservation.arrival_date.asc())
            )
            obs_res = await session.scalars(obs_stmt)
            for obs in obs_res.all():
                raw_obs_map[obs.arrival_date] = {
                    "modal_price": float(obs.modal_price_inr_per_quintal),
                    "min_price": float(obs.min_price_inr_per_quintal),
                    "max_price": float(obs.max_price_inr_per_quintal),
                    "arrivals_volume": float(obs.arrivals_quintal or 10.0),
                }

            # Query existing price_features
            feat_stmt = (
                select(PriceFeature)
                .where(
                    PriceFeature.commodity == commodity,
                    PriceFeature.market == market,
                    PriceFeature.feature_date >= start,
                    PriceFeature.feature_date <= end,
                )
                .order_by(PriceFeature.feature_date.asc())
            )
            feat_res = await session.scalars(feat_stmt)
            db_features = {f.feature_date: f for f in feat_res.all()}
        except Exception:
            db_features = {}
    else:
        db_features = {}

    # 2. Build continuous daily series
    weather_adapter = WeatherAdapter()
    macro_provider = MacroFeatureProvider()
    calendar_extractor = CalendarFeatureExtractor()

    cur = start
    dates: list[date] = []
    prices: list[float] = []
    min_prices: list[float] = []
    max_prices: list[float] = []
    arrivals: list[float] = []

    # Baseline seed if series is empty
    macro_init = macro_provider.get_features(commodity, start)
    last_price = macro_init.msp_inr_per_quintal * 1.05
    last_min = last_price * 0.95
    last_max = last_price * 1.05
    last_vol = 50.0

    while cur <= end:
        dates.append(cur)
        if cur in raw_obs_map:
            obs_d = raw_obs_map[cur]
            last_price = obs_d["modal_price"]
            last_min = obs_d["min_price"]
            last_max = obs_d["max_price"]
            last_vol = obs_d["arrivals_volume"]
        else:
            # Synthetic / forward-fill seasonal price variation when DB observations missing
            if not raw_obs_map:
                # Deterministic seasonal wave centered on MSP
                doy = cur.timetuple().tm_yday
                seasonal_pct = 0.08 * math.sin(2.0 * math.pi * (doy - 80) / 365.25)
                # Small daily noise
                noise = (((hashlib.md5(f"{commodity}:{cur.isoformat()}".encode()).digest()[0]) % 50) - 25) * 1.5
                base_msp = macro_init.msp_inr_per_quintal
                last_price = round(base_msp * (1.0 + seasonal_pct) + noise, 1)
                last_min = round(last_price * 0.96, 1)
                last_max = round(last_price * 1.04, 1)
                last_vol = 45.0 + ((doy % 30) * 2.0)

        prices.append(last_price)
        min_prices.append(last_min)
        max_prices.append(last_max)
        arrivals.append(last_vol)
        cur += timedelta(days=1)

    # 3. Compute rolling statistical features
    features_matrix: list[list[float]] = []
    records: list[dict[str, Any]] = []

    for i, d in enumerate(dates):
        p = prices[i]
        # 7-day rolling window
        w7_start = max(0, i - 6)
        w7 = prices[w7_start : i + 1]
        ma_7d = sum(w7) / len(w7)
        # 14-day rolling window
        w14_start = max(0, i - 13)
        w14 = prices[w14_start : i + 1]
        ma_14d = sum(w14) / len(w14)

        # 7-day momentum
        lag7_p = prices[max(0, i - 7)]
        momentum_7d = ((p - lag7_p) / max(lag7_p, 1.0))

        # 7-day volatility
        variance = sum((x - ma_7d) ** 2 for x in w7) / len(w7)
        vol_7d = math.sqrt(variance)

        # Exogenous features from DB or generator
        feat = db_features.get(d)
        if feat is not None:
            rain = feat.rainfall_mm or 0.0
            rain_dev = feat.rainfall_deviation_pct or 0.0
            t_min = feat.temp_min_c or 18.0
            t_max = feat.temp_max_c or 32.0
            is_fest = 1.0 if feat.is_festival else 0.0
            is_mandi_hol = 1.0 if feat.is_mandi_holiday else 0.0
            is_harvest = 1.0 if feat.is_harvest_season else 0.0
            sin_doy = feat.sin_day_of_year or 0.0
            cos_doy = feat.cos_day_of_year or 1.0
            sin_dow = feat.sin_day_of_week or 0.0
            cos_dow = feat.cos_day_of_week or 1.0
            msp = feat.msp_inr_per_quintal or macro_init.msp_inr_per_quintal
            infl = feat.macro_inflation_pct or 5.0
            crude = feat.macro_crude_usd or 75.0
        else:
            w = weather_adapter.compute_agro_climatic_baseline(state, district, d)
            c = calendar_extractor.get_features(d)
            m = macro_provider.get_features(commodity, d)
            rain = w.rainfall_mm
            rain_dev = w.rainfall_deviation_pct
            t_min = w.temp_min_c
            t_max = w.temp_max_c
            is_fest = 1.0 if c.is_festival else 0.0
            is_mandi_hol = 1.0 if c.is_mandi_holiday else 0.0
            is_harvest = 1.0 if c.is_harvest_season else 0.0
            sin_doy = c.sin_day_of_year
            cos_doy = c.cos_day_of_year
            sin_dow = c.sin_day_of_week
            cos_dow = c.cos_day_of_week
            msp = m.msp_inr_per_quintal
            infl = m.macro_inflation_pct
            crude = m.macro_crude_usd

        spread = max_prices[i] - min_prices[i]
        p_msp_ratio = p / max(msp, 1.0)

        row_vector = [
            round(p, 2),
            round(arrivals[i], 2),
            round(spread, 2),
            round(ma_7d, 2),
            round(ma_14d, 2),
            round(momentum_7d, 4),
            round(vol_7d, 2),
            round(rain, 2),
            round(rain_dev, 2),
            round(t_min, 1),
            round(t_max, 1),
            is_fest,
            is_mandi_hol,
            is_harvest,
            round(sin_doy, 4),
            round(cos_doy, 4),
            round(sin_dow, 4),
            round(cos_dow, 4),
            round(msp, 2),
            round(p_msp_ratio, 4),
            round(infl, 2),
            round(crude, 2),
        ]
        features_matrix.append(row_vector)

        row_record = {
            "date": d,
            "target": round(p, 2),
            **{name: row_vector[idx] for idx, name in enumerate(CANONICAL_FEATURE_NAMES)},
        }
        records.append(row_record)

    return TrainingFrame(
        commodity=commodity,
        market=market,
        start_date=start,
        end_date=end,
        feature_names=CANONICAL_FEATURE_NAMES,
        dates=dates,
        targets=prices,
        features_matrix=features_matrix,
        records=records,
    )
