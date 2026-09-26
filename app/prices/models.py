from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Market(Base):
    """A regulated wholesale market (mandi) identified by its AGMARKNET name."""

    __tablename__ = "markets"
    __table_args__ = (
        UniqueConstraint(
            "state_name",
            "district_name",
            "market_name",
            name="uq_markets_state_district_market",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    state_name: Mapped[str] = mapped_column(String(128))
    state_lgd_code: Mapped[str | None] = mapped_column(String(8))
    district_name: Mapped[str] = mapped_column(String(128))
    district_lgd_code: Mapped[str | None] = mapped_column(String(8))
    market_name: Mapped[str] = mapped_column(String(128))


class Commodity(Base):
    __tablename__ = "commodities"
    __table_args__ = (UniqueConstraint("name", name="uq_commodities_name"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    group_name: Mapped[str | None] = mapped_column(String(128))


class PriceObservation(Base):
    """One AGMARKNET price report.

    Prices are INR per quintal. ``arrival_date`` leads the primary key because
    TimescaleDB requires the hypertable partition column in every unique index.
    Blank variety or grade is stored as an empty string so the key stays complete
    when the source report omits them.
    """

    __tablename__ = "price_observations"
    __table_args__ = (
        CheckConstraint(
            "min_price_inr_per_quintal >= 0",
            name="min_price_nonnegative",
        ),
        CheckConstraint(
            "max_price_inr_per_quintal >= 0",
            name="max_price_nonnegative",
        ),
        CheckConstraint(
            "modal_price_inr_per_quintal >= 0",
            name="modal_price_nonnegative",
        ),
        CheckConstraint(
            "arrivals_quintal IS NULL OR arrivals_quintal >= 0",
            name="arrivals_nonnegative",
        ),
        Index(
            "ix_price_observations_commodity_arrival",
            "commodity_id",
            "arrival_date",
        ),
    )

    arrival_date: Mapped[date] = mapped_column(Date, primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), primary_key=True)
    commodity_id: Mapped[int] = mapped_column(ForeignKey("commodities.id"), primary_key=True)
    variety: Mapped[str] = mapped_column(String(128), primary_key=True, default="")
    grade: Mapped[str] = mapped_column(String(64), primary_key=True, default="")
    min_price_inr_per_quintal: Mapped[int] = mapped_column(BigInteger)
    max_price_inr_per_quintal: Mapped[int] = mapped_column(BigInteger)
    modal_price_inr_per_quintal: Mapped[int] = mapped_column(BigInteger)
    arrivals_quintal: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    lgd_market_id: Mapped[int | None] = mapped_column(BigInteger)
    lgd_commodity_id: Mapped[int | None] = mapped_column(BigInteger)
    lgd_resolution_method: Mapped[str | None] = mapped_column(String(32))
    lgd_resolution_confidence: Mapped[float | None] = mapped_column(Float)


class PriceFeature(Base):
    """Daily exogenous features for (commodity, market, date).

    Consolidates weather, calendar, harvest season, MSP benchmarks, and macro indicators.
    """

    __tablename__ = "price_features"
    __table_args__ = (
        UniqueConstraint(
            "commodity",
            "market",
            "feature_date",
            name="uq_price_features_comm_mkt_date",
        ),
        Index("ix_price_features_comm_mkt_date", "commodity", "market", "feature_date"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), Identity(), autoincrement=True, primary_key=True
    )
    commodity: Mapped[str] = mapped_column(String(128), nullable=False)
    market: Mapped[str] = mapped_column(String(128), nullable=False)
    feature_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Weather variables
    rainfall_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    rainfall_normal_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    rainfall_deviation_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    temp_min_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    temp_max_c: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Calendar and Seasonality
    is_festival: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    festival_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_mandi_holiday: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_harvest_season: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    season_name: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sin_day_of_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    cos_day_of_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    sin_day_of_week: Mapped[float | None] = mapped_column(Float, nullable=True)
    cos_day_of_week: Mapped[float | None] = mapped_column(Float, nullable=True)

    # MSP & Macroeconomic benchmarks
    msp_inr_per_quintal: Mapped[float | None] = mapped_column(Float, nullable=True)
    macro_inflation_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    macro_crude_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_weather_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ForecastModel(Base):
    """Machine learning model artifact and evaluation metrics registry."""

    __tablename__ = "forecast_models"
    __table_args__ = (
        Index("ix_forecast_models_comm_mkt_status", "commodity", "market", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    commodity: Mapped[str] = mapped_column(String(128), nullable=False)
    market: Mapped[str] = mapped_column(String(128), nullable=False)
    architecture: Mapped[str] = mapped_column(String(32), nullable=False)  # "TFT", "LSTM"
    feature_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hyperparams: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    metrics: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    artifact_path: Mapped[str | None] = mapped_column(String(256), nullable=True)
    weights_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    trained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), default="CANDIDATE", nullable=False
    )  # "PRODUCTION", "CANDIDATE", "SHADOW", "RETIRED", "FAILED"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

