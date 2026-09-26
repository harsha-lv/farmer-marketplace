"""Rolling-Origin Backtest Harness for Probabilistic Price Forecasting.

Evaluates forecasting models over rolling origins across historical seasons:
  - Generates walk-forward rolling-origin evaluation splits
  - Computes out-of-sample MAPE, RMSE, and pinball loss per horizon
  - Performs calibration check: verifies empirical coverage of the p10-p90 prediction band is ~80%
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.prices.feature_store import get_training_frame
from app.prices.tft import (
    TFTForecaster,
    calculate_mape,
    calculate_rmse,
    mean_pinball_loss,
)


@dataclass
class BacktestHorizonResult:
    horizon_days: int
    num_evaluations: int
    mape: float
    rmse: float
    pinball_p10: float
    pinball_p50: float
    pinball_p90: float
    empirical_coverage_pct: float
    is_calibrated: bool


@dataclass
class BacktestReport:
    commodity: str
    market: str
    seasons: int
    total_evaluations: int
    start_date: date
    end_date: date
    horizon_results: dict[int, BacktestHorizonResult]
    overall_coverage_pct: float
    calibration_passed: bool

    def print_summary(self) -> None:
        print("\n" + "=" * 70)
        print("ROLLING-ORIGIN BACKTEST ACCURACY & CALIBRATION REPORT")
        print("=" * 70)
        print(f"Commodity:        {self.commodity}")
        print(f"Market:           {self.market}")
        print(f"Evaluation Period: {self.start_date} to {self.end_date} (~{self.seasons} agricultural seasons)")
        print(f"Total Test Cuts:  {self.total_evaluations} rolling origins")
        print("-" * 70)
        print(f"{'Horizon':<10} {'MAPE (%)':<10} {'RMSE':<10} {'P10 Loss':<10} {'P50 Loss':<10} {'P90 Loss':<10} {'P10-P90 Coverage':<18} {'Calibrated'}")
        print("-" * 70)
        for h, res in sorted(self.horizon_results.items()):
            calib_str = "PASS (~80%)" if res.is_calibrated else f"FAIL ({res.empirical_coverage_pct}%)"
            print(
                f"{h} days     {res.mape:<10.2f} {res.rmse:<10.2f} {res.pinball_p10:<10.2f} "
                f"{res.pinball_p50:<10.2f} {res.pinball_p90:<10.2f} "
                f"{res.empirical_coverage_pct:<6.1f}%           {calib_str}"
            )
        print("-" * 70)
        overall_status = "PASSED" if self.calibration_passed else "ATTENTION NEEDED"
        print(f"Overall Empirical Coverage: {self.overall_coverage_pct:.1f}% (Nominal target: 80.0%) | Status: {overall_status}")
        print("=" * 70 + "\n")


async def run_backtest(
    commodity: str,
    market: str,
    seasons: int = 3,
    horizons: list[int] | None = None,
    lookback_days: int = 30,
    step_days: int = 14,
    session: AsyncSession | None = None,
) -> BacktestReport:
    """Execute rolling-origin evaluation over the last N agricultural seasons."""
    eval_horizons = horizons or [7, 14, 21]
    total_days = max(lookback_days + max(eval_horizons) + 60, seasons * 120)
    end = date.today()
    start = end - timedelta(days=total_days)

    if session is not None:
        frame = await get_training_frame(commodity, market, start, end, session=session)
    else:
        from app.config import get_settings
        from app.db.session import Database

        settings = get_settings()
        db = Database(settings.database_url)
        try:
            async with db.session_factory() as sess:
                frame = await get_training_frame(commodity, market, start, end, session=sess)
        finally:
            await db.dispose()

    T = len(frame)
    max_h = max(eval_horizons)
    min_train = lookback_days + 30

    if T < min_train + max_h:
        raise ValueError(f"Insufficient history ({T} days) for rolling backtest with lookback={lookback_days} and horizons={eval_horizons}")

    # Collect actuals and predictions per horizon
    horizon_actuals: dict[int, list[float]] = {h: [] for h in eval_horizons}
    horizon_p10: dict[int, list[float]] = {h: [] for h in eval_horizons}
    horizon_p50: dict[int, list[float]] = {h: [] for h in eval_horizons}
    horizon_p90: dict[int, list[float]] = {h: [] for h in eval_horizons}
    horizon_covered: dict[int, list[bool]] = {h: [] for h in eval_horizons}

    # Step through rolling origins
    cutoffs = list(range(min_train, T - max_h, step_days))

    for cutoff in cutoffs:
        train_features = frame.features_matrix[:cutoff]
        train_targets = frame.targets[:cutoff]

        # Train model on history up to origin
        model = TFTForecaster(horizons=eval_horizons, lookback_days=lookback_days, feature_names=frame.feature_names)
        model.fit(train_features, train_targets, epochs=15)

        # Predict from origin
        recent_seq = train_features[-lookback_days:]
        preds = model.predict(recent_seq)

        # Evaluate against future ground truth at each horizon
        for h in eval_horizons:
            actual = frame.targets[cutoff + h]
            pred = preds[h]

            horizon_actuals[h].append(actual)
            horizon_p10[h].append(pred.p10)
            horizon_p50[h].append(pred.p50)
            horizon_p90[h].append(pred.p90)
            # Calibration check: does actual fall inside [p10, p90] interval?
            is_inside = (pred.p10 <= actual <= pred.p90)
            horizon_covered[h].append(is_inside)

    # Calculate metrics per horizon
    results: dict[int, BacktestHorizonResult] = {}
    all_coverage_flags: list[bool] = []

    for h in eval_horizons:
        y_true = horizon_actuals[h]
        y_10 = horizon_p10[h]
        y_50 = horizon_p50[h]
        y_90 = horizon_p90[h]
        cov_flags = horizon_covered[h]
        all_coverage_flags.extend(cov_flags)

        n_evals = len(y_true)
        mape_val = calculate_mape(y_true, y_50)
        rmse_val = calculate_rmse(y_true, y_50)
        p10_loss = round(mean_pinball_loss(y_true, y_10, 0.10), 2)
        p50_loss = round(mean_pinball_loss(y_true, y_50, 0.50), 2)
        p90_loss = round(mean_pinball_loss(y_true, y_90, 0.90), 2)

        cov_pct = round((sum(1 for c in cov_flags if c) / max(1, len(cov_flags))) * 100.0, 1)
        # Calibrated if empirical coverage is within 70% to 90% (nominal 80%)
        is_calib = 70.0 <= cov_pct <= 90.0

        results[h] = BacktestHorizonResult(
            horizon_days=h,
            num_evaluations=n_evals,
            mape=mape_val,
            rmse=rmse_val,
            pinball_p10=p10_loss,
            pinball_p50=p50_loss,
            pinball_p90=p90_loss,
            empirical_coverage_pct=cov_pct,
            is_calibrated=is_calib,
        )

    overall_cov = round((sum(1 for c in all_coverage_flags if c) / max(1, len(all_coverage_flags))) * 100.0, 1)
    overall_pass = 70.0 <= overall_cov <= 90.0

    return BacktestReport(
        commodity=commodity,
        market=market,
        seasons=seasons,
        total_evaluations=len(cutoffs),
        start_date=start,
        end_date=end,
        horizon_results=results,
        overall_coverage_pct=overall_cov,
        calibration_passed=overall_pass,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rolling-origin backtest for price forecasting models.")
    parser.add_argument("--commodity", type=str, required=True, help="Commodity name (e.g. Wheat, Paddy)")
    parser.add_argument("--market", type=str, required=True, help="Market name (e.g. 'Indore Mandi')")
    parser.add_argument("--seasons", type=int, default=3, help="Number of agricultural seasons to backtest over (default: 3)")
    parser.add_argument("--horizons", type=str, default="7,14,21", help="Horizons in days (default: 7,14,21)")
    parser.add_argument("--lookback", type=int, default=30, help="Lookback window in days (default: 30)")
    parser.add_argument("--step", type=int, default=14, help="Rolling origin step in days (default: 14)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    horizons = [int(h.strip()) for h in args.horizons.split(",") if h.strip()]

    try:
        report = asyncio.run(
            run_backtest(
                commodity=args.commodity,
                market=args.market,
                seasons=args.seasons,
                horizons=horizons,
                lookback_days=args.lookback,
                step_days=args.step,
            )
        )
        report.print_summary()
    except Exception as exc:
        print(f"[!] Backtest failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
