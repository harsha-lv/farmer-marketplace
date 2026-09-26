"""Production Forecasting Inference Engine.

Features:
  - Model hot-reload from app.forecast_models without server restart
  - Shadow-mode comparison of Candidate vs Production models
  - Automatic fallback hierarchy:
      1. Production Model
      2. Previous / Retired Model version
      3. Deterministic attention baseline (tft_multivariate_forecast)
  - Zero-500 guarantee: never crashes on model corruption or missing artifacts
  - Retraining trigger and Kafka price replay consumer
"""

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.prices.feature_store import get_training_frame
from app.prices.models import ForecastModel
from app.prices.recommendations import RecommendationPlan, generate_recommendation_plan
from app.prices.tft import BaseForecastEngine, HorizonPrediction
from app.prices.tft_forecasting import tft_multivariate_forecast

logger = logging.getLogger(__name__)


@dataclass
class ShadowEvaluation:
    candidate_version: str
    production_version: str
    commodity: str
    market: str
    candidate_predictions: dict[int, dict[str, float]]
    production_predictions: dict[int, dict[str, float]]
    deltas_p50: dict[int, float]


@dataclass
class ForecastInferenceResult:
    commodity: str
    market: str
    as_of_date: date
    current_modal_price_inr: float
    model_version: str
    model_architecture: str
    model_status: str
    fallback_used: str | None
    recommendations: RecommendationPlan
    predictions: dict[int, HorizonPrediction]
    shadow_evaluation: ShadowEvaluation | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "commodity": self.commodity,
            "market": self.market,
            "as_of_date": self.as_of_date.isoformat(),
            "current_modal_price_inr": self.current_modal_price_inr,
            "model_version": self.model_version,
            "model_architecture": self.model_architecture,
            "model_status": self.model_status,
            "fallback_used": self.fallback_used,
            "predictions": {
                str(h): {
                    "horizon_days": p.horizon_days,
                    "p10": p.p10,
                    "p50": p.p50,
                    "p90": p.p90,
                }
                for h, p in self.predictions.items()
            },
            "recommendations": self.recommendations.to_dict(),
            "shadow_evaluation": asdict(self.shadow_evaluation) if self.shadow_evaluation else None,
        }


class ForecastInferenceEngine:
    """Manages model registry caching, hot-reloading, shadow evaluations, and fallbacks."""

    def __init__(self) -> None:
        # Cache of loaded models: (commodity, market) -> (version, model_instance)
        self._loaded_models: dict[tuple[str, str], tuple[str, BaseForecastEngine]] = {}
        self._lock = asyncio.Lock()

    def _load_model_from_record(self, record: ForecastModel) -> BaseForecastEngine:
        """Instantiate model from stored weights data."""
        if not record.weights_data:
            raise ValueError(f"Model {record.version} has no weights_data")
        data = json.loads(record.weights_data)
        return BaseForecastEngine.from_dict(data)

    async def get_production_model(
        self,
        session: AsyncSession,
        commodity: str,
        market: str,
    ) -> tuple[BaseForecastEngine, ForecastModel] | None:
        """Fetch active production model from cache or DB with hot-reload support."""
        cache_key = (commodity, market)

        # Query database for current active PRODUCTION model
        stmt = (
            select(ForecastModel)
            .where(
                ForecastModel.commodity == commodity,
                ForecastModel.market == market,
                ForecastModel.status == "PRODUCTION",
            )
            .order_by(desc(ForecastModel.trained_at))
            .limit(1)
        )
        res = await session.scalars(stmt)
        record = res.first()

        if record is None:
            return None

        self._last_attempted_version = record.version

        # Check if cache is fresh
        cached = self._loaded_models.get(cache_key)
        if cached is not None and cached[0] == record.version:
            return cached[1], record

        # Hot-reload from weights data
        async with self._lock:
            # Double-check inside lock
            cached = self._loaded_models.get(cache_key)
            if cached is not None and cached[0] == record.version:
                return cached[1], record

            logger.info("Hot-reloading production model %s for (%s, %s)", record.version, commodity, market)
            model = self._load_model_from_record(record)
            self._loaded_models[cache_key] = (record.version, model)
            return model, record

    async def get_candidate_model(
        self,
        session: AsyncSession,
        commodity: str,
        market: str,
    ) -> tuple[BaseForecastEngine, ForecastModel] | None:
        """Fetch latest candidate model for shadow-mode evaluation."""
        stmt = (
            select(ForecastModel)
            .where(
                ForecastModel.commodity == commodity,
                ForecastModel.market == market,
                ForecastModel.status.in_(["CANDIDATE", "SHADOW"]),
            )
            .order_by(desc(ForecastModel.trained_at))
            .limit(1)
        )
        res = await session.scalars(stmt)
        record = res.first()
        if record is None:
            return None
        try:
            model = self._load_model_from_record(record)
            return model, record
        except Exception as exc:
            logger.warning("Failed to load candidate model %s: %s", record.version, exc)
            return None

    async def get_previous_model(
        self,
        session: AsyncSession,
        commodity: str,
        market: str,
        failed_version: str,
    ) -> tuple[BaseForecastEngine, ForecastModel] | None:
        """Fallback tier 2: fetch previous valid retired or candidate model version."""
        stmt = (
            select(ForecastModel)
            .where(
                ForecastModel.commodity == commodity,
                ForecastModel.market == market,
                ForecastModel.version != failed_version,
                ForecastModel.status.in_(["RETIRED", "PRODUCTION", "CANDIDATE"]),
            )
            .order_by(desc(ForecastModel.trained_at))
        )
        res = await session.scalars(stmt)
        records = res.all()
        for rec in records:
            try:
                model = self._load_model_from_record(rec)
                return model, rec
            except Exception as exc:
                logger.warning("Failed to load previous model %s: %s", rec.version, exc)
                continue
        return None

    async def predict_with_fallbacks(
        self,
        session: AsyncSession,
        commodity: str,
        market: str,
        lookback_days: int = 30,
        storage_cost_per_day: float | None = None,
        capital_interest_rate_bps: int = 700,
        facility_available: bool = True,
    ) -> ForecastInferenceResult:
        """Generate multi-horizon forecasts and recommendations with automatic fallbacks and shadow evaluations."""
        today = date.today()
        start = today - timedelta(days=lookback_days + 30)

        # 1. Fetch feature frame shared contract
        frame = await get_training_frame(commodity, market, start, today, session=session)
        recent_features = frame.features_matrix[-lookback_days:]
        current_price = frame.targets[-1] if frame.targets else 2500.0

        model: BaseForecastEngine | None = None
        record: ForecastModel | None = None
        fallback_used: str | None = None

        # Tier 1: Try active PRODUCTION model
        try:
            prod_tuple = await self.get_production_model(session, commodity, market)
            if prod_tuple is not None:
                model, record = prod_tuple
                preds = model.predict(recent_features)
            else:
                raise RuntimeError(f"No PRODUCTION model registered for {commodity} at {market}")
        except Exception as exc_prod:
            logger.warning("Production model failed: %s. Attempting fallback to previous version...", exc_prod)
            failed_ver = record.version if record else getattr(self, "_last_attempted_version", "NONE")
            
            # Tier 2: Try previous / retired version
            try:
                prev_tuple = await self.get_previous_model(session, commodity, market, failed_ver)
                if prev_tuple is not None:
                    model, record = prev_tuple
                    preds = model.predict(recent_features)
                    fallback_used = f"PREVIOUS_VERSION:{record.version}"
                    logger.info("Successfully fell back to previous model version %s", record.version)
                else:
                    raise RuntimeError("No previous model version available")
            except Exception as exc_prev:
                logger.warning("Previous version fallback failed: %s. Falling back to deterministic attention engine...", exc_prev)
                # Tier 3: Deterministic attention baseline
                preds = self._deterministic_attention_fallback(frame, current_price)
                fallback_used = "DETERMINISTIC_ATTENTION_BASELINE"

        # Shadow-Mode Evaluation
        shadow_eval: ShadowEvaluation | None = None
        try:
            cand_tuple = await self.get_candidate_model(session, commodity, market)
            if cand_tuple is not None and record is not None and cand_tuple[1].version != record.version:
                cand_model, cand_record = cand_tuple
                cand_preds = cand_model.predict(recent_features)
                
                deltas = {h: round(cand_preds[h].p50 - preds[h].p50, 1) for h in preds.keys()}
                shadow_eval = ShadowEvaluation(
                    candidate_version=cand_record.version,
                    production_version=record.version,
                    commodity=commodity,
                    market=market,
                    candidate_predictions={h: asdict(cand_preds[h]) for h in cand_preds.keys()},
                    production_predictions={h: asdict(preds[h]) for h in preds.keys()},
                    deltas_p50=deltas,
                )
                logger.info("Shadow evaluation: candidate %s vs prod %s | p50 deltas: %s", cand_record.version, record.version, deltas)
        except Exception as exc_shadow:
            logger.debug("Shadow evaluation skipped: %s", exc_shadow)

        # Recommendations
        rec_plan = generate_recommendation_plan(
            commodity=commodity,
            market=market,
            as_of_date=today,
            current_price=current_price,
            predictions=preds,
            storage_cost_per_day=storage_cost_per_day,
            capital_interest_rate_bps=capital_interest_rate_bps,
            facility_available=facility_available,
        )

        return ForecastInferenceResult(
            commodity=commodity,
            market=market,
            as_of_date=today,
            current_modal_price_inr=current_price,
            model_version=record.version if record else "RULE_BASED_BASELINE",
            model_architecture=record.architecture if record else "ATTENTION_V1",
            model_status=record.status if record else "FALLBACK",
            fallback_used=fallback_used,
            recommendations=rec_plan,
            predictions=preds,
            shadow_evaluation=shadow_eval,
        )

    def _deterministic_attention_fallback(
        self,
        frame: Any,
        current_price: float,
    ) -> dict[int, HorizonPrediction]:
        """Deterministic attention forecaster fallback guaranteeing zero 500s."""
        # Convert frame to simple series tuples
        series = [
            (
                d,
                int(round(frame.targets[i])),
                int(round(frame.features_matrix[i][1])),  # arrivals
                int(round(frame.features_matrix[i][2])),  # spread
            )
            for i, d in enumerate(frame.dates)
        ]
        base_forecast = tft_multivariate_forecast(series, horizon_days=21)

        preds: dict[int, HorizonPrediction] = {}
        for h_point in base_forecast.horizons:
            if h_point.day_offset in (7, 14, 21):
                preds[h_point.day_offset] = HorizonPrediction(
                    horizon_days=h_point.day_offset,
                    p10=float(h_point.p10_price_inr),
                    p50=float(h_point.p50_price_inr),
                    p90=float(h_point.p90_price_inr),
                )
        if not preds:
            for h in (7, 14, 21):
                preds[h] = HorizonPrediction(
                    horizon_days=h,
                    p10=round(current_price * 0.95, 1),
                    p50=round(current_price * 1.02, 1),
                    p90=round(current_price * 1.08, 1),
                )
        return preds


# Global engine singleton
global_inference_engine = ForecastInferenceEngine()


class ScheduledRetrainingJob:
    """Consumes Kafka replay or periodic triggers to retrain candidate models."""

    def __init__(self, engine: ForecastInferenceEngine) -> None:
        self.engine = engine
        self._running = False

    async def run_retrain_cycle(
        self,
        commodity: str,
        market: str,
        horizons: list[int] | None = None,
        session: AsyncSession | None = None,
    ) -> dict[str, Any]:
        """Trigger an automated retraining run and evaluate candidate model."""
        from app.prices.train import train_model

        eval_horizons = horizons or [7, 14, 21]
        logger.info("Executing scheduled retraining for (%s, %s)...", commodity, market)
        res = await train_model(
            commodity=commodity,
            market=market,
            horizons=eval_horizons,
            architecture="TFT",
            publish=False,  # Enters as CANDIDATE for shadow evaluation
            session=session,
        )
        return res

    async def handle_kafka_replay_event(
        self,
        event_payload: dict[str, Any],
        session: AsyncSession | None = None,
    ) -> dict[str, Any] | None:
        """Handle incoming price ingest / replay event from Kafka or NATS and retrain candidate."""
        commodity = event_payload.get("commodity")
        market = event_payload.get("market") or event_payload.get("state")
        if not commodity or not market:
            logger.info("Kafka replay event missing commodity or market, skipping retraining")
            return None
        logger.info("Retraining candidate model triggered by Kafka replay event for (%s, %s)", commodity, market)
        return await self.run_retrain_cycle(commodity=commodity, market=market, session=session)


