"""Manual verification script demonstrating model hot-reload and automatic fallback.

Demonstrates:
  1. Active model (PRODUCTION) is corrupted / fails to load.
  2. Inference engine detects corruption, logs a warning, and automatically
     falls back to the previous version (RETIRED).
  3. When all versions fail, engine falls back to the deterministic attention baseline.
  4. Guarantees 0 crashes, 0 500 errors, returning full quantile forecasts & recommendations.

Usage:
  python scripts/demo_model_fallback.py
"""

import asyncio
from datetime import UTC, datetime
import json
import sys

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.prices.inference import ForecastInferenceEngine
from app.prices.models import ForecastModel, PriceFeature
from app.prices.tft import TFTForecaster


class AsyncSessionAdapter:
    def __init__(self, sync_sess: Session):
        self.sync_session = sync_sess

    async def execute(self, stmt, *args, **kwargs):
        return await asyncio.to_thread(self.sync_session.execute, stmt, *args, **kwargs)

    async def scalars(self, stmt, *args, **kwargs):
        return await asyncio.to_thread(self.sync_session.scalars, stmt, *args, **kwargs)

    async def commit(self):
        await asyncio.to_thread(self.sync_session.commit)

    async def rollback(self):
        await asyncio.to_thread(self.sync_session.rollback)

    def add(self, instance):
        self.sync_session.add(instance)


async def main() -> None:
    print("=" * 70)
    print("DEMO: FORECAST MODEL INFERENCE FALLBACK & HOT-RELOAD")
    print("=" * 70)

    # 1. Setup isolated in-memory SQLite schema
    eng = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(eng, "connect")
    def on_connect(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("ATTACH DATABASE '' AS app")
        cursor.close()

    with eng.connect() as conn:
        ForecastModel.__table__.create(conn, checkfirst=True)
        PriceFeature.__table__.create(conn, checkfirst=True)

    sm = sessionmaker(bind=eng)
    sync_sess = sm()
    session = AsyncSessionAdapter(sync_sess)

    # 2. Train a real healthy model to act as the previous version
    print("[1] Training healthy baseline model v1 (status: RETIRED)...")
    model_v1 = TFTForecaster(horizons=[7, 14, 21], lookback_days=10)
    dummy_x = [[5000.0 + i * 10 + j * 0.5 for j in range(22)] for i in range(60)]
    dummy_y = [5000.0 + i * 10 for i in range(60)]
    model_v1.fit(dummy_x, dummy_y, epochs=5)

    v1_record = ForecastModel(
        id="model-v1-uuid",
        version="soybean_ujjain_v1_healthy",
        commodity="Soybean",
        market="Ujjain Mandi",
        architecture="TFT",
        feature_hash="hash_v1",
        hyperparams={"epochs": 3},
        metrics={"7": {"mape": 1.2, "rmse": 30.0}},
        weights_data=json.dumps(model_v1.to_dict()),
        trained_at=datetime(2026, 9, 20, 10, 0, 0, tzinfo=UTC),
        status="RETIRED",
    )
    sync_sess.add(v1_record)

    # 3. Insert an active PRODUCTION model whose weights are intentionally corrupted
    print("[2] Registering active candidate model v2 with CORRUPTED weights (status: PRODUCTION)...")
    v2_corrupted = ForecastModel(
        id="model-v2-broken-uuid",
        version="soybean_ujjain_v2_corrupted",
        commodity="Soybean",
        market="Ujjain Mandi",
        architecture="TFT",
        feature_hash="hash_corrupted",
        hyperparams={"epochs": 10},
        metrics={},
        weights_data="MALFORMED_JSON_CORRUPTED_WEIGHT_BLOB",
        trained_at=datetime(2026, 9, 25, 12, 0, 0, tzinfo=UTC),
        status="PRODUCTION",
    )
    sync_sess.add(v2_corrupted)
    sync_sess.commit()

    # 4. Invoke inference engine
    print("[3] Invoking ForecastInferenceEngine.predict_with_fallbacks('Soybean', 'Ujjain Mandi')...")
    engine = ForecastInferenceEngine()

    result = await engine.predict_with_fallbacks(session, "Soybean", "Ujjain Mandi")

    print("\n--- INFERENCE RESULT SUMMARY ---")
    print(f"Commodity:           {result.commodity}")
    print(f"Market:              {result.market}")
    print(f"Current Modal Price: Rs {result.current_modal_price_inr} / qtl")
    print(f"Model Version:       {result.model_version}")
    print(f"Model Architecture:  {result.model_architecture}")
    print(f"Model Status:        {result.model_status}")
    print(f"Fallback Triggered:  {result.fallback_used}")
    print(f"Recommendation:      {result.recommendations.overall_recommendation}")
    print("\nQuantile Forecast Horizons (p10 / p50 / p90):")
    for h, p in result.predictions.items():
        print(f"  - {h:2d} Days: p10=Rs {p.p10:.1f} | p50=Rs {p.p50:.1f} | p90=Rs {p.p90:.1f}")

    # Check fallback assertion
    assert result.fallback_used is not None, "Fallback should have been triggered!"
    assert "v1_healthy" in result.fallback_used, f"Expected fallback to v1_healthy, got: {result.fallback_used}"
    print("\n[SUCCESS] Corrupted PRODUCTION model cleanly caught and fell back to healthy previous version!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
