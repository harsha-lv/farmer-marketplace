from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Lot(Base):
    __tablename__ = "lots"
    __table_args__ = (
        UniqueConstraint("lot_code", name="uq_lots_lot_code"),
        UniqueConstraint("enam_lot_id", name="uq_lots_enam_lot_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    lot_code: Mapped[str] = mapped_column(String(32))
    farmer_id: Mapped[str] = mapped_column(String(64), index=True)
    commodity: Mapped[str] = mapped_column(String(128))
    variety: Mapped[str] = mapped_column(String(128))
    quantity_mt: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    consent_artifact_id: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    enam_gate_id: Mapped[str | None] = mapped_column(String(64))
    enam_lot_id: Mapped[str | None] = mapped_column(String(64))
    enam_registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assay: Mapped["AssayReport"] = relationship(
        back_populates="lot",
        uselist=False,
        cascade="all, delete-orphan",
    )


class AssayReport(Base):
    __tablename__ = "assay_reports"
    __table_args__ = (UniqueConstraint("lot_id", name="uq_assay_reports_lot_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    lot_id: Mapped[int] = mapped_column(
        ForeignKey("lots.id", name="fk_assay_reports_lot_id_lots", ondelete="CASCADE")
    )
    grade: Mapped[str] = mapped_column(String(64))
    foreign_matter_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    moisture_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    damaged_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lot: Mapped[Lot] = relationship(back_populates="assay")
