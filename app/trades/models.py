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
    fulfillment_status: Mapped[str | None] = mapped_column(String(32), nullable=True, default=None)
    tracking_url: Mapped[str | None] = mapped_column(String(512), nullable=True, default=None)
    carrier_name: Mapped[str | None] = mapped_column(String(128), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SettlementRecord(Base):
    __tablename__ = "settlement_records"
    __table_args__ = (
        UniqueConstraint("settlement_id", name="uq_settlement_records_settlement_id"),
        UniqueConstraint("transaction_id", name="uq_settlement_records_transaction_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    settlement_id: Mapped[str] = mapped_column(String(64), index=True)
    transaction_id: Mapped[str] = mapped_column(String(128), index=True)
    farmer_id: Mapped[str] = mapped_column(String(64))
    gross_amount_inr: Mapped[int] = mapped_column(BigInteger)
    commission_inr: Mapped[int] = mapped_column(BigInteger)
    tds_inr: Mapped[int] = mapped_column(BigInteger)
    net_payout_inr: Mapped[int] = mapped_column(BigInteger)
    payout_mode: Mapped[str] = mapped_column(String(32))
    settlement_due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32))
    payout_ref: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ErupiVoucher(Base):
    __tablename__ = "erupi_vouchers"
    __table_args__ = (
        UniqueConstraint("voucher_code", name="uq_erupi_vouchers_voucher_code"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    voucher_code: Mapped[str] = mapped_column(String(64), index=True)
    settlement_id: Mapped[str] = mapped_column(String(64), index=True)
    transaction_id: Mapped[str] = mapped_column(String(128), index=True)
    farmer_id: Mapped[str] = mapped_column(String(64))
    beneficiary_phone: Mapped[str] = mapped_column(String(32))
    beneficiary_name: Mapped[str] = mapped_column(String(256))
    amount_inr: Mapped[int] = mapped_column(BigInteger)
    purpose_code: Mapped[str] = mapped_column(String(64))
    issuer: Mapped[str] = mapped_column(String(64))
    qr_payload: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

