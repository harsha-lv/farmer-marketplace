"""add fulfillment tracking fields to trade_contracts

Revision ID: 0012_trade_fulfillment
Revises: 0011_outbox_events
Create Date: 2026-09-24

"""

import sqlalchemy as sa
from alembic import op

revision = "0012_trade_fulfillment"
down_revision = "0011_outbox_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trade_contracts",
        sa.Column("fulfillment_status", sa.String(32), nullable=True),
        schema="app",
    )
    op.add_column(
        "trade_contracts",
        sa.Column("tracking_url", sa.String(512), nullable=True),
        schema="app",
    )
    op.add_column(
        "trade_contracts",
        sa.Column("carrier_name", sa.String(128), nullable=True),
        schema="app",
    )


def downgrade() -> None:
    op.drop_column("trade_contracts", "carrier_name", schema="app")
    op.drop_column("trade_contracts", "tracking_url", schema="app")
    op.drop_column("trade_contracts", "fulfillment_status", schema="app")
