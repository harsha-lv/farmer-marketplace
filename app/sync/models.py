"""Sync domain database models."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class BuyerDemand(Base):
    """Aggregated buyer intent/demand for agricultural produce."""
    __tablename__ = "buyer_demand"
    __table_args__ = (
        UniqueConstraint("demand_id", name="uq_buyer_demand_demand_id"),
        Index("ix_buyer_demand_org_id", "org_id"),
        Index("ix_buyer_demand_status", "status"),
        Index("ix_buyer_demand_updated_at", "updated_at"),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), Identity(), autoincrement=True, primary_key=True
    )
    demand_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    buyer_id: Mapped[str] = mapped_column(String(64), index=True)
    org_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    commodity: Mapped[str] = mapped_column(String(128))
    variety: Mapped[str | None] = mapped_column(String(128), nullable=True)
    target_grade: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quantity_mt: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    target_price_per_mt: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    delivery_location: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
