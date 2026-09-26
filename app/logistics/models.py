from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
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


class Facility(Base):
    __tablename__ = "facilities"
    __table_args__ = (
        Index("ix_facilities_updated_at", "updated_at"),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), Identity(), autoincrement=True, primary_key=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    facility_type: Mapped[str] = mapped_column(String(32), nullable=False)  # WAREHOUSE, MANDI, COLD_STORAGE
    wdra_registration_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    state: Mapped[str] = mapped_column(String(128), nullable=False)
    district: Mapped[str] = mapped_column(String(128), nullable=False)
    pincode: Mapped[str | None] = mapped_column(String(12), nullable=True)
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    capacity_quintals: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    available_quintals: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cold_storage: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    daily_charge_inr_per_quintal: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=Decimal("0.50")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)


class Shipment(Base):
    """Fulfillment and logistics shipment reference tracking ONDC LSP or internal movements."""
    __tablename__ = "shipments"
    __table_args__ = (
        UniqueConstraint("shipment_id", name="uq_shipments_shipment_id"),
        Index("ix_shipments_transaction_id", "transaction_id"),
        Index("ix_shipments_lsp_id", "lsp_id"),
        Index("ix_shipments_state", "state"),
        Index("ix_shipments_sla_status", "sla_status"),
        Index("ix_shipments_eta_delivery_at", "eta_delivery_at"),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), Identity(), autoincrement=True, primary_key=True
    )
    shipment_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    transaction_id: Mapped[str] = mapped_column(String(128), index=True)
    order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    trade_contract_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), nullable=True
    )
    contract_code: Mapped[str | None] = mapped_column(String(160), nullable=True)
    lsp_id: Mapped[str] = mapped_column(String(128), index=True)
    lsp_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lsp_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    quote_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="network")  # "network" | "internal"
    state: Mapped[str] = mapped_column(String(64), default="CREATED")  # CREATED, ASSIGNED, PICKUP_SCHEDULED, IN_TRANSIT, DELIVERED, CANCELLED, BREACHED
    pickup_gps: Mapped[str] = mapped_column(String(64))
    drop_gps: Mapped[str] = mapped_column(String(64))
    pickup_window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pickup_window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_pickup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    eta_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_gps: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_gps_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tracking_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    vehicle_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vehicle_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cold_chain: Mapped[bool] = mapped_column(Boolean, default=False)
    freight_charge_inr: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), default=0
    )
    sla_status: Mapped[str] = mapped_column(String(32), default="ON_TIME")  # ON_TIME, PICKUP_BREACHED, DELIVERY_BREACHED
    igm_ticket_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

