from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Identity, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PledgeLoan(Base):
    __tablename__ = "pledge_loans"
    __table_args__ = (
        UniqueConstraint("loan_id", name="uq_pledge_loans_loan_id"),
        UniqueConstraint("warehouse_receipt_id", name="uq_pledge_loans_warehouse_receipt_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    loan_id: Mapped[str] = mapped_column(String(64), index=True)
    warehouse_receipt_id: Mapped[str] = mapped_column(String(64), index=True)
    lot_code: Mapped[str] = mapped_column(String(32), index=True)
    farmer_id: Mapped[str] = mapped_column(String(64), index=True)
    commodity: Mapped[str] = mapped_column(String(128))
    quantity_mt: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    valuation_inr: Mapped[int] = mapped_column(BigInteger)
    principal_amount_inr: Mapped[int] = mapped_column(BigInteger)
    interest_rate_bps: Mapped[int] = mapped_column(BigInteger)  # e.g., 700 = 7.00% p.a.
    tenure_days: Mapped[int] = mapped_column(BigInteger)
    lien_status: Mapped[str] = mapped_column(String(32))  # LIEN_MARKED, LIEN_RELEASED
    loan_status: Mapped[str] = mapped_column(String(32))  # APPROVED, DISBURSED, REPAID, DEFAULTED
    lender_name: Mapped[str] = mapped_column(String(128))
    disbursement_mode: Mapped[str] = mapped_column(String(32))  # BANK_TRANSFER, ERUPI_VOUCHER
    disbursement_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    disbursed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    repaid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_repaid_inr: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
