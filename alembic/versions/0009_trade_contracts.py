"""create draft trade contracts

Revision ID: 0009_trade_contracts
Revises: 0008_warehouse_receipts
Create Date: 2026-09-22

"""

import sqlalchemy as sa
from alembic import op

revision = "0009_trade_contracts"
down_revision = "0008_warehouse_receipts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trade_contracts",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("contract_code", sa.String(160), nullable=False),
        sa.Column("transaction_id", sa.String(128), nullable=False),
        sa.Column("lot_code", sa.String(32), nullable=False),
        sa.Column("farmer_id", sa.String(64), nullable=False),
        sa.Column("buyer_name", sa.String(256), nullable=False),
        sa.Column("buyer_address", sa.String(512), nullable=False),
        sa.Column("buyer_phone", sa.String(32)),
        sa.Column("delivery_gps", sa.String(64), nullable=False),
        sa.Column("quantity_mt", sa.Numeric(12, 3), nullable=False),
        sa.Column("price_inr", sa.BigInteger, nullable=False),
        sa.Column("commission_inr", sa.BigInteger, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("transaction_id", name="uq_trade_contracts_transaction_id"),
        schema="app",
    )


def downgrade() -> None:
    op.drop_table("trade_contracts", schema="app")
