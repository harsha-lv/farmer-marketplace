from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Farmer(Base):
    __tablename__ = "farmers"
    __table_args__ = (UniqueConstraint("farmer_id", name="uq_farmers_farmer_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    farmer_id: Mapped[str] = mapped_column(String(64))
    state_lgd_code: Mapped[str] = mapped_column(String(8))
    display_name: Mapped[str] = mapped_column(String(256))
    consent_artifact_id: Mapped[str] = mapped_column(String(128))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    parcels: Mapped[list["LandParcel"]] = relationship(
        back_populates="farmer",
        cascade="all, delete-orphan",
    )


class LandParcel(Base):
    __tablename__ = "land_parcels"
    __table_args__ = (UniqueConstraint("farm_id", name="uq_land_parcels_farm_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    farmer_id: Mapped[int] = mapped_column(
        ForeignKey("farmers.id", name="fk_land_parcels_farmer_id_farmers", ondelete="CASCADE")
    )
    farm_id: Mapped[str] = mapped_column(String(14))
    area_hectares: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    farmer: Mapped[Farmer] = relationship(back_populates="parcels")
    crops: Mapped[list["CropRecord"]] = relationship(
        back_populates="parcel",
        cascade="all, delete-orphan",
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

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    parcel_id: Mapped[int] = mapped_column(
        ForeignKey(
            "land_parcels.id",
            name="fk_crop_records_parcel_id_land_parcels",
            ondelete="CASCADE",
        )
    )
    commodity: Mapped[str] = mapped_column(String(128))
    season: Mapped[str] = mapped_column(String(64))
    parcel: Mapped[LandParcel] = relationship(back_populates="crops")
