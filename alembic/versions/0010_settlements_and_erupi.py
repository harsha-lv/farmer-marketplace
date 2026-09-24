"""create settlements and erupi tables

Revision ID: 0010_settlements_and_erupi
Revises: 0009_trade_contracts
Create Date: 2026-09-24

"""

import sqlalchemy as sa
from alembic import op

revision = "0010_settlements_and_erupi"
down_revision = "0009_trade_contracts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "settlement_records",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("settlement_id", sa.String(64), nullable=False),
        sa.Column("transaction_id", sa.String(128), nullable=False),
        sa.Column("farmer_id", sa.String(64), nullable=False),
        sa.Column("gross_amount_inr", sa.BigInteger, nullable=False),
        sa.Column("commission_inr", sa.BigInteger, nullable=False),
        sa.Column("tds_inr", sa.BigInteger, nullable=False),
        sa.Column("net_payout_inr", sa.BigInteger, nullable=False),
        sa.Column("payout_mode", sa.String(32), nullable=False),
        sa.Column("settlement_due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("payout_ref", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("settlement_id", name="uq_settlement_records_settlement_id"),
        sa.UniqueConstraint("transaction_id", name="uq_settlement_records_transaction_id"),
        schema="app",
    )
    op.create_index(
        "ix_app_settlement_records_settlement_id",
        "settlement_records",
        ["settlement_id"],
        schema="app",
    )
    op.create_index(
        "ix_app_settlement_records_transaction_id",
        "settlement_records",
        ["transaction_id"],
        schema="app",
    )

    op.create_table(
        "erupi_vouchers",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("voucher_code", sa.String(64), nullable=False),
        sa.Column("settlement_id", sa.String(64), nullable=False),
        sa.Column("transaction_id", sa.String(128), nullable=False),
        sa.Column("farmer_id", sa.String(64), nullable=False),
        sa.Column("beneficiary_phone", sa.String(32), nullable=False),
        sa.Column("beneficiary_name", sa.String(256), nullable=False),
        sa.Column("amount_inr", sa.BigInteger, nullable=False),
        sa.Column("purpose_code", sa.String(64), nullable=False),
        sa.Column("issuer", sa.String(64), nullable=False),
        sa.Column("qr_payload", sa.String(512), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("voucher_code", name="uq_erupi_vouchers_voucher_code"),
        schema="app",
    )
    op.create_index(
        "ix_app_erupi_vouchers_voucher_code",
        "erupi_vouchers",
        ["voucher_code"],
        schema="app",
    )
    op.create_index(
        "ix_app_erupi_vouchers_settlement_id",
        "erupi_vouchers",
        ["settlement_id"],
        schema="app",
    )
    op.create_index(
        "ix_app_erupi_vouchers_transaction_id",
        "erupi_vouchers",
        ["transaction_id"],
        schema="app",
    )


def downgrade() -> None:
    op.drop_table("erupi_vouchers", schema="app")
    op.drop_table("settlement_records", schema="app")
