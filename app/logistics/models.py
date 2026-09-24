from decimal import Decimal
from sqlalchemy import BigInteger, Boolean, Identity, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Facility(Base):
    __tablename__ = "facilities"
    __table_args__ = {"schema": "app"}

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
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
