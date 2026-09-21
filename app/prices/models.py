from datetime import date
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
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
