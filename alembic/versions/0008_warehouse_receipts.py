"""store warehouse receipt ids

Revision ID: 0008_warehouse_receipts
Revises: 0007_enam_registration
Create Date: 2026-09-22

"""

import sqlalchemy as sa
from alembic import op

revision = "0008_warehouse_receipts"
down_revision = "0007_enam_registration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lots", sa.Column("warehouse_id", sa.String(64)), schema="app")
    op.add_column("lots", sa.Column("warehouse_receipt_id", sa.String(64)), schema="app")
    op.add_column("lots", sa.Column("warehoused_at", sa.DateTime(timezone=True)), schema="app")
    op.create_unique_constraint("uq_lots_warehouse_receipt_id", "lots", ["warehouse_receipt_id"], schema="app")


def downgrade() -> None:
    op.drop_constraint("uq_lots_warehouse_receipt_id", "lots", schema="app", type_="unique")
    op.drop_column("lots", "warehoused_at", schema="app")
    op.drop_column("lots", "warehouse_receipt_id", schema="app")
    op.drop_column("lots", "warehouse_id", schema="app")
