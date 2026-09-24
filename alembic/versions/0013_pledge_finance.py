"""create pledge_loans table for post-harvest eNWR financing

Revision ID: 0013_pledge_finance
Revises: 0012_trade_fulfillment
Create Date: 2026-09-24

"""

import sqlalchemy as sa
from alembic import op

revision = "0013_pledge_finance"
down_revision = "0012_trade_fulfillment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pledge_loans",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("loan_id", sa.String(64), nullable=False),
        sa.Column("warehouse_receipt_id", sa.String(64), nullable=False),
        sa.Column("lot_code", sa.String(32), nullable=False),
        sa.Column("farmer_id", sa.String(64), nullable=False),
        sa.Column("commodity", sa.String(128), nullable=False),
        sa.Column("quantity_mt", sa.Numeric(12, 3), nullable=False),
        sa.Column("valuation_inr", sa.BigInteger, nullable=False),
        sa.Column("principal_amount_inr", sa.BigInteger, nullable=False),
        sa.Column("interest_rate_bps", sa.BigInteger, nullable=False),
        sa.Column("tenure_days", sa.BigInteger, nullable=False),
        sa.Column("lien_status", sa.String(32), nullable=False),
        sa.Column("loan_status", sa.String(32), nullable=False),
        sa.Column("lender_name", sa.String(128), nullable=False),
        sa.Column("disbursement_mode", sa.String(32), nullable=False),
        sa.Column("disbursement_ref", sa.String(128), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disbursed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("repaid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_repaid_inr", sa.BigInteger, nullable=True),
        sa.UniqueConstraint("loan_id", name="uq_pledge_loans_loan_id"),
        sa.UniqueConstraint("warehouse_receipt_id", name="uq_pledge_loans_warehouse_receipt_id"),
        schema="app",
    )
    op.create_index("ix_app_pledge_loans_loan_id", "pledge_loans", ["loan_id"], schema="app")
    op.create_index("ix_app_pledge_loans_receipt_id", "pledge_loans", ["warehouse_receipt_id"], schema="app")
    op.create_index("ix_app_pledge_loans_lot_code", "pledge_loans", ["lot_code"], schema="app")
    op.create_index("ix_app_pledge_loans_farmer_id", "pledge_loans", ["farmer_id"], schema="app")


def downgrade() -> None:
    op.drop_table("pledge_loans", schema="app")
