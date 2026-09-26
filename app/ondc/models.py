"""Database models for ONDC Beckn v2.0.0, IGM Grievances, Ratings, TLC, and BAP state."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class IgmTicket(Base):
    """Integrated Grievance Management (IGM) issue ticket with escalation ladder."""
    __tablename__ = "igm_tickets"
    __table_args__ = (
        UniqueConstraint("ticket_id", name="uq_igm_tickets_ticket_id"),
        Index("ix_igm_tickets_transaction_id", "transaction_id"),
        Index("ix_igm_tickets_status", "status"),
        Index("ix_igm_tickets_sla_expires_at", "sla_expires_at"),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), Identity(), autoincrement=True, primary_key=True
    )
    ticket_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    transaction_id: Mapped[str] = mapped_column(String(128), index=True)
    category: Mapped[str] = mapped_column(String(64))  # QUALITY, DELIVERY_DELAY, SHORT_QUANTITY, SETTLEMENT_PAYOUT
    sub_category: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="OPEN")  # OPEN, PROCESSING, RESOLVED, ESCALATED_L2, ESCALATED_L3, CLOSED
    escalation_level: Mapped[int] = mapped_column(Integer, default=1)  # 1: FPO Nodal Officer, 2: Network ONDC, 3: Regulator
    expected_response_time: Mapped[str] = mapped_column(String(32), default="PT48H")
    complainant_info: Mapped[dict[str, Any]] = mapped_column(JSON)
    respondent_info: Mapped[dict[str, Any]] = mapped_column(JSON)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    refund_amount_inr: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), default=0)
    settlement_paused: Mapped[bool] = mapped_column(Boolean, default=True)
    sla_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class RatingRecord(Base):
    """Post-fulfillment buyer/seller/logistics ratings."""
    __tablename__ = "rating_records"
    __table_args__ = (
        Index("ix_rating_records_transaction_id", "transaction_id"),
        Index("ix_rating_records_target_id", "target_id"),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), Identity(), autoincrement=True, primary_key=True
    )
    transaction_id: Mapped[str] = mapped_column(String(128), index=True)
    rating_category: Mapped[str] = mapped_column(String(32))  # seller, logistics, lot_quality
    target_id: Mapped[str] = mapped_column(String(128), index=True)  # farmer_id, bpp_id, carrier_id
    score: Mapped[int] = mapped_column(Integer)  # 1 to 5
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TlcRecord(Base):
    """Immutable Transaction-Level Contract (TLC) records."""
    __tablename__ = "tlc_records"
    __table_args__ = (
        UniqueConstraint("transaction_id", name="uq_tlc_records_transaction_id"),
        Index("ix_tlc_records_tlc_hash", "tlc_hash"),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), Identity(), autoincrement=True, primary_key=True
    )
    contract_code: Mapped[str] = mapped_column(String(160))
    transaction_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    tlc_hash: Mapped[str] = mapped_column(String(64), index=True)
    tlc_terms_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    signature: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BapSearchRequest(Base):
    """Outbound BAP broadcast search requests and responses."""
    __tablename__ = "bap_search_requests"
    __table_args__ = (
        UniqueConstraint("transaction_id", name="uq_bap_search_requests_transaction_id"),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), Identity(), autoincrement=True, primary_key=True
    )
    transaction_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    message_id: Mapped[str] = mapped_column(String(128), index=True)
    commodity: Mapped[str | None] = mapped_column(String(64), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BapQuote(Base):
    """Multi-BPP catalog and quote responses collected by BAP for comparison."""
    __tablename__ = "bap_quotes"
    __table_args__ = (
        Index("ix_bap_quotes_transaction_id", "transaction_id"),
        {"schema": "app"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), Identity(), autoincrement=True, primary_key=True
    )
    transaction_id: Mapped[str] = mapped_column(String(128), index=True)
    message_id: Mapped[str] = mapped_column(String(128))
    bpp_id: Mapped[str] = mapped_column(String(128))
    bpp_uri: Mapped[str] = mapped_column(String(512))
    lot_code: Mapped[str] = mapped_column(String(64))
    commodity: Mapped[str] = mapped_column(String(64))
    grade: Mapped[str | None] = mapped_column(String(32), nullable=True)
    quantity_mt: Mapped[float] = mapped_column(Float, default=0.0)
    price_inr: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), default=0)
    seller_score: Mapped[float] = mapped_column(Float, default=4.0)
    raw_quote_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
