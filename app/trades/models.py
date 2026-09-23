from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Identity, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TradeContract(Base):
    __tablename__ = "trade_contracts"
    __table_args__ = (UniqueConstraint("transaction_id", name="uq_trade_contracts_transaction_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    contract_code: Mapped[str] = mapped_column(String(160))
    transaction_id: Mapped[str] = mapped_column(String(128))
    lot_code: Mapped[str] = mapped_column(String(32))
    farmer_id: Mapped[str] = mapped_column(String(64))
    buyer_name: Mapped[str] = mapped_column(String(256))
    buyer_address: Mapped[str] = mapped_column(String(512))
    buyer_phone: Mapped[str | None] = mapped_column(String(32))
    delivery_gps: Mapped[str] = mapped_column(String(64))
    quantity_mt: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    price_inr: Mapped[int] = mapped_column(BigInteger)
    commission_inr: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
