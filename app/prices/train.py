"""CLI Training script for versioned Price Forecasting Models.

Usage:
    python -m app.prices.train --commodity Wheat --market "Indore Mandi" --horizons 7,14,21
    python -m app.prices.train --commodity Wheat --market "Indore Mandi" --build-frame
    python -m app.prices.train --commodity Wheat --market "Indore Mandi" --publish
"""

import argparse
import asyncio
import json
import os
import sys
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.prices.feature_store import get_training_frame
from app.prices.models import ForecastModel
from app.prices.tft import LSTMForecaster, TFTForecaster


async def train_model(
    commodity: str,
    market: str,
    horizons: list[int],
    architecture: str = "TFT",
    lookback_days: int = 30,
    epochs: int = 25,
    start_date: date | None = None,
    end_date: date | None = None,
    publish: bool = False,
    build_frame_only: bool = False,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """Execute training pipeline, evaluate metrics, and save model to registry."""
    if session is not None:
        return await _train_with_session(
            session=session,
            commodity=commodity,
            market=market,
            horizons=horizons,
            architecture=architecture,
            lookback_days=lookback_days,
            epochs=epochs,
            start_date=start_date,
            end_date=end_date,
            publish=publish,
            build_frame_only=build_frame_only,
        )

    from app.config import get_settings
    from app.db.session import Database

    settings = get_settings()
    db = Database(settings.database_url)
    try:
        async with db.session_factory() as sess:
            return await _train_with_session(
                session=sess,
                commodity=commodity,
                market=market,
                horizons=horizons,
                architecture=architecture,
                lookback_days=lookback_days,
                epochs=epochs,
                start_date=start_date,
                end_date=end_date,
                publish=publish,
                build_frame_only=build_frame_only,
            )
    except Exception as exc:
        print(f"[*] Note: Primary database offline ({exc}), using local SQLite registry (forecast_registry.db)...")
        from sqlalchemy import create_engine, event
        from sqlalchemy.orm import Session, sessionmaker

        from app.prices.models import ForecastModel, PriceFeature

        eng = create_engine("sqlite:///forecast_registry.db", connect_args={"check_same_thread": False})

        @event.listens_for(eng, "connect")
        def on_connect(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("ATTACH DATABASE '' AS app")
            cursor.close()

        ForecastModel.__table__.create(eng, checkfirst=True)
        PriceFeature.__table__.create(eng, checkfirst=True)
        sm = sessionmaker(bind=eng)

        class AsyncSessionAdapter:
            def __init__(self, sync_sess: Session):
                self.sync_session = sync_sess

            async def execute(self, stmt: Any, *args: Any, **kwargs: Any) -> Any:
                return await asyncio.to_thread(self.sync_session.execute, stmt, *args, **kwargs)

            async def scalars(self, stmt: Any, *args: Any, **kwargs: Any) -> Any:
                return await asyncio.to_thread(self.sync_session.scalars, stmt, *args, **kwargs)

            async def commit(self) -> None:
                await asyncio.to_thread(self.sync_session.commit)

            async def rollback(self) -> None:
                await asyncio.to_thread(self.sync_session.rollback)

            def add(self, instance: Any) -> None:
                self.sync_session.add(instance)

            def delete(self, instance: Any) -> None:
                self.sync_session.delete(instance)

        sync_sess = sm()
        adapter = AsyncSessionAdapter(sync_sess)
        try:
            return await _train_with_session(
                session=adapter,  # type: ignore
                commodity=commodity,
                market=market,
                horizons=horizons,
                architecture=architecture,
                lookback_days=lookback_days,
                epochs=epochs,
                start_date=start_date,
                end_date=end_date,
                publish=publish,
                build_frame_only=build_frame_only,
            )
        finally:
            sync_sess.close()
            eng.dispose()
    finally:
        try:
            await db.dispose()
        except Exception:
            pass


async def _train_with_session(
    session: AsyncSession,
    commodity: str,
    market: str,
    horizons: list[int],
    architecture: str = "TFT",
    lookback_days: int = 30,
    epochs: int = 25,
    start_date: date | None = None,
    end_date: date | None = None,
    publish: bool = False,
    build_frame_only: bool = False,
) -> dict[str, Any]:
    today = date.today()
    end = end_date or today
    start = start_date or (end - timedelta(days=365))

    # 1. Fetch feature frame through shared contract (zero train/serve skew)
    print(f"[*] Building training frame for {commodity} at {market} [{start} to {end}]...")
    frame = await get_training_frame(commodity, market, start, end, session=session)
    print(f"[*] Training frame ready: {len(frame)} daily steps, {len(frame.feature_names)} features, hash={frame.feature_hash}")

    if build_frame_only:
        recs = frame.to_records()
        print("\n--- Training Frame Contract Preview ---")
        print(f"Commodity: {frame.commodity} | Market: {frame.market}")
        print(f"Features ({len(frame.feature_names)}): {', '.join(frame.feature_names)}")
        print(f"Start date: {frame.start_date} | End date: {frame.end_date}")
        print(f"Total rows: {len(recs)}")
        if recs:
            print("First record:")
            print(json.dumps({k: v for k, v in recs[0].items() if k != "date"}, indent=2))
            print("Latest record:")
            print(json.dumps({k: v for k, v in recs[-1].items() if k != "date"}, indent=2))
        return {"frame_length": len(frame), "feature_hash": frame.feature_hash}

    # 2. Instantiate Architecture
    print(f"[*] Initializing {architecture} forecaster with horizons={horizons}, lookback={lookback_days}d...")
    if architecture.upper() == "LSTM":
        model = LSTMForecaster(
            horizons=horizons,
            lookback_days=lookback_days,
            feature_names=frame.feature_names,
        )
    else:
        model = TFTForecaster(
            horizons=horizons,
            lookback_days=lookback_days,
            feature_names=frame.feature_names,
        )

    # 3. Fit model with quantile pinball loss
    print(f"[*] Fitting {architecture} model with quantile (p10/p50/p90) pinball loss over {epochs} epochs...")
    metrics = model.fit(frame.features_matrix, frame.targets, epochs=epochs)
    print("[*] Training completed. In-sample validation metrics:")
    for h, m in metrics.items():
        print(f"    Horizon {h}d: MAPE={m['mape']}% | RMSE={m['rmse']} | Pinball[p10={m['pinball_p10']}, p50={m['pinball_p50']}, p90={m['pinball_p90']}]")

    # 4. Generate version and artifact
    now = datetime.now(UTC)
    comm_slug = commodity.lower().replace(" ", "_")
    mkt_slug = market.lower().replace(" ", "_")
    timestamp_slug = now.strftime("%Y%m%d%H%M%S")
    version = f"{comm_slug}_{mkt_slug}_{architecture.lower()}_{timestamp_slug}_{uuid.uuid4().hex[:6]}"
    model_id = str(uuid.uuid4())

    hyperparams = {
        "architecture": architecture,
        "horizons": horizons,
        "lookback_days": lookback_days,
        "epochs": epochs,
        "features": frame.feature_names,
        "training_samples": len(frame),
    }
    weights_data = json.dumps(model.to_dict())

    # Ensure directory for artifacts
    artifact_dir = os.path.join("models", "forecast")
    os.makedirs(artifact_dir, exist_ok=True)
    artifact_path = os.path.join(artifact_dir, f"{version}.json")
    with open(artifact_path, "w", encoding="utf-8") as f:
        f.write(weights_data)

    # 5. Persist to app.forecast_models registry
    new_status = "PRODUCTION" if publish else "CANDIDATE"

    if publish:
        # Retire any previous PRODUCTION models for this commodity and market
        await session.execute(
            update(ForecastModel)
            .where(
                ForecastModel.commodity == commodity,
                ForecastModel.market == market,
                ForecastModel.status == "PRODUCTION",
            )
            .values(status="RETIRED")
        )

    record = ForecastModel(
        id=model_id,
        version=version,
        commodity=commodity,
        market=market,
        architecture=architecture,
        feature_hash=frame.feature_hash,
        hyperparams=hyperparams,
        metrics=metrics,
        artifact_path=artifact_path,
        weights_data=weights_data,
        trained_at=now,
        status=new_status,
    )
    session.add(record)
    await session.commit()

    print("\n[+] Successfully saved model to registry:")
    print(f"    ID:           {model_id}")
    print(f"    Version:      {version}")
    print(f"    Status:       {new_status}")
    print(f"    Feature Hash: {frame.feature_hash}")
    print(f"    Artifact:     {artifact_path}")

    return {
        "id": model_id,
        "version": version,
        "commodity": commodity,
        "market": market,
        "status": new_status,
        "metrics": metrics,
        "feature_hash": frame.feature_hash,
        "artifact_path": artifact_path,
    }



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train agricultural price forecasting models.")
    parser.add_argument("--commodity", type=str, required=True, help="Commodity name (e.g. Wheat, Paddy, Mustard)")
    parser.add_argument("--market", type=str, required=True, help="Market/Mandi name (e.g. 'Indore Mandi')")
    parser.add_argument("--horizons", type=str, default="7,14,21", help="Comma-separated forecast horizons in days (default: 7,14,21)")
    parser.add_argument("--architecture", type=str, choices=["TFT", "LSTM"], default="TFT", help="Forecasting model architecture (default: TFT)")
    parser.add_argument("--lookback", type=int, default=30, help="Lookback window in days (default: 30)")
    parser.add_argument("--epochs", type=int, default=25, help="Number of training epochs (default: 25)")
    parser.add_argument("--start", type=str, default=None, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument("--publish", action="store_true", help="Publish directly to PRODUCTION status in registry")
    parser.add_argument("--build-frame", action="store_true", help="Only build and inspect the training frame without training")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    horizons = [int(h.strip()) for h in args.horizons.split(",") if h.strip()]
    start_d = date.fromisoformat(args.start) if args.start else None
    end_d = date.fromisoformat(args.end) if args.end else None

    try:
        asyncio.run(
            train_model(
                commodity=args.commodity,
                market=args.market,
                horizons=horizons,
                architecture=args.architecture,
                lookback_days=args.lookback,
                epochs=args.epochs,
                start_date=start_d,
                end_date=end_d,
                publish=args.publish,
                build_frame_only=args.build_frame,
            )
        )
    except Exception as exc:
        print(f"[!] Training failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
