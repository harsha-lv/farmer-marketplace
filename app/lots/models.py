from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Lot(Base):
    __tablename__ = "lots"
    __table_args__ = (
        UniqueConstraint("lot_code", name="uq_lots_lot_code"),
        UniqueConstraint("enam_lot_id", name="uq_lots_enam_lot_id"),
        UniqueConstraint("warehouse_receipt_id", name="uq_lots_warehouse_receipt_id"),
        Index("ix_lots_org_id", "org_id"),
        Index("ix_lots_updated_at", "updated_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), Identity(), autoincrement=True, primary_key=True
    )
    lot_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    farmer_id: Mapped[str] = mapped_column(String(64), index=True)
    org_id: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None, index=True)
    fpo_id: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None, index=True)
    commodity: Mapped[str] = mapped_column(String(128))
    variety: Mapped[str] = mapped_column(String(128))
    quantity_mt: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    consent_artifact_id: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    enam_gate_id: Mapped[str | None] = mapped_column(String(64))
    enam_lot_id: Mapped[str | None] = mapped_column(String(64))
    enam_registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    warehouse_id: Mapped[str | None] = mapped_column(String(64))
    warehouse_receipt_id: Mapped[str | None] = mapped_column(String(64))
    warehoused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assay: Mapped["AssayReport"] = relationship(
        back_populates="lot",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )


class AssayReport(Base):
    __tablename__ = "assay_reports"
    __table_args__ = (
        UniqueConstraint("lot_id", name="uq_assay_reports_lot_id"),
        Index("ix_assay_reports_updated_at", "updated_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), Identity(), autoincrement=True, primary_key=True
    )
    lot_id: Mapped[int] = mapped_column(
        ForeignKey("lots.id", name="fk_assay_reports_lot_id_lots", ondelete="CASCADE")
    )
    grade: Mapped[str] = mapped_column(String(64))
    foreign_matter_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    moisture_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    damaged_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    image_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_versions: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    hmac_signature: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    discoloration_severity_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    pest_infestation_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    grain_size_distribution: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    fallback: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ai_details: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    lot: Mapped[Lot] = relationship(back_populates="assay", lazy="raise")
