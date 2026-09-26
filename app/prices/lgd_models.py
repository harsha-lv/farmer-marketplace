"""LGD reference data models for state, district, market, and commodity normalization.

These tables support AgriStack and ONDC interoperability by providing canonical
LGD (Local Government Directory) codes for entities identified by AGMARKNET
string names.
"""

from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LgdState(Base):
    """Indian state/UT with its 2-character short code and LGD numeric code."""

    __tablename__ = "lgd_states"
    __table_args__ = (
        UniqueConstraint("lgd_code", name="uq_lgd_states_lgd_code"),
        UniqueConstraint("state_code", name="uq_lgd_states_state_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state_code: Mapped[str] = mapped_column(String(4), nullable=False)
    state_name: Mapped[str] = mapped_column(String(128), nullable=False)
    lgd_code: Mapped[str] = mapped_column(String(8), nullable=False)


class LgdDistrict(Base):
    """District with its LGD code linked to a parent state."""

    __tablename__ = "lgd_districts"
    __table_args__ = (
        UniqueConstraint("lgd_code", name="uq_lgd_districts_lgd_code"),
        Index("ix_lgd_districts_state_lgd_code", "state_lgd_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    district_name: Mapped[str] = mapped_column(String(128), nullable=False)
    lgd_code: Mapped[str] = mapped_column(String(8), nullable=False)
    state_lgd_code: Mapped[str] = mapped_column(String(8), nullable=False)


class LgdMarket(Base):
    """Regulated mandi / APMC yard with its canonical LGD identifiers and geo-coordinates."""

    __tablename__ = "lgd_markets"
    __table_args__ = (
        Index("ix_lgd_markets_district_lgd_code", "district_lgd_code"),
        Index("ix_lgd_markets_state_lgd_code", "state_lgd_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_name: Mapped[str] = mapped_column(String(256), nullable=False)
    district_lgd_code: Mapped[str] = mapped_column(String(8), nullable=False)
    state_lgd_code: Mapped[str] = mapped_column(String(8), nullable=False)
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)


class LgdCommodity(Base):
    """Commodity with group, grade/variety classification, and standard code."""

    __tablename__ = "lgd_commodities"
    __table_args__ = (
        UniqueConstraint("commodity_name", "grade", name="uq_lgd_commodities_name_grade"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    commodity_name: Mapped[str] = mapped_column(String(128), nullable=False)
    group_name: Mapped[str | None] = mapped_column(String(128))
    grade: Mapped[str] = mapped_column(String(64), nullable=False, default="FAQ")
    standard_code: Mapped[str | None] = mapped_column(String(32))


class LgdMarketAlias(Base):
    """Admin-editable alias mapping raw AGMARKNET names to canonical LGD market ids."""

    __tablename__ = "lgd_market_aliases"
    __table_args__ = (
        UniqueConstraint("raw_name", name="uq_lgd_market_aliases_raw_name"),
        Index("ix_lgd_market_aliases_market_id", "market_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    raw_name: Mapped[str] = mapped_column(String(256), nullable=False)
    market_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class LgdUnresolved(Base):
    """Review queue for AGMARKNET names that could not be automatically resolved to LGD codes."""

    __tablename__ = "lgd_unresolved"
    __table_args__ = (
        UniqueConstraint("raw_name", "entity_type", name="uq_lgd_unresolved_raw_name_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    raw_name: Mapped[str] = mapped_column(String(256), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)  # market|district|state
    state_hint: Mapped[str | None] = mapped_column(String(128))
    district_hint: Mapped[str | None] = mapped_column(String(128))
    best_guess_lgd_code: Mapped[str | None] = mapped_column(String(8))
    confidence: Mapped[float | None] = mapped_column(Float)
    resolution_method: Mapped[str | None] = mapped_column(String(32))
    resolved: Mapped[bool] = mapped_column(default=False)
    resolved_lgd_code: Mapped[str | None] = mapped_column(String(8))
    resolved_by: Mapped[str | None] = mapped_column(String(128))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
