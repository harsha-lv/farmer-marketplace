from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Farmer(Base):
    __tablename__ = "farmers"
    __table_args__ = (
        UniqueConstraint("farmer_id", name="uq_farmers_farmer_id"),
        Index("ix_farmers_org_id", "org_id"),
        Index("ix_farmers_updated_at", "updated_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), Identity(), autoincrement=True, primary_key=True
    )
    farmer_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    state_lgd_code: Mapped[str] = mapped_column(String(8))
    display_name: Mapped[str] = mapped_column(String(256))
    consent_artifact_id: Mapped[str] = mapped_column(String(128))
    org_id: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    parcels: Mapped[list["LandParcel"]] = relationship(
        back_populates="farmer",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )


class LandParcel(Base):
    __tablename__ = "land_parcels"
    __table_args__ = (
        UniqueConstraint("farm_id", name="uq_land_parcels_farm_id"),
        Index("ix_land_parcels_updated_at", "updated_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), Identity(), autoincrement=True, primary_key=True
    )
    farmer_id: Mapped[int] = mapped_column(
        ForeignKey("farmers.id", name="fk_land_parcels_farmer_id_farmers", ondelete="CASCADE")
    )
    farm_id: Mapped[str] = mapped_column(String(14))
    area_hectares: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    farmer: Mapped[Farmer] = relationship(back_populates="parcels", lazy="raise")
    crops: Mapped[list["CropRecord"]] = relationship(
        back_populates="parcel",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )


class CropRecord(Base):
    __tablename__ = "crop_records"
    __table_args__ = (
        UniqueConstraint(
            "parcel_id",
            "commodity",
            "season",
            name="uq_crop_records_parcel_commodity_season",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), Identity(), autoincrement=True, primary_key=True
    )
    parcel_id: Mapped[int] = mapped_column(
        ForeignKey(
            "land_parcels.id",
            name="fk_crop_records_parcel_id_land_parcels",
            ondelete="CASCADE",
        )
    )
    commodity: Mapped[str] = mapped_column(String(128))
    season: Mapped[str] = mapped_column(String(64))
    parcel: Mapped[LandParcel] = relationship(back_populates="crops", lazy="raise")
