"""store enam gate and lot ids

Revision ID: 0007_enam_registration
Revises: 0006_lots
Create Date: 2026-09-22

"""

import sqlalchemy as sa
from alembic import op

revision = "0007_enam_registration"
down_revision = "0006_lots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lots", sa.Column("enam_gate_id", sa.String(64)), schema="app")
    op.add_column("lots", sa.Column("enam_lot_id", sa.String(64)), schema="app")
    op.add_column("lots", sa.Column("enam_registered_at", sa.DateTime(timezone=True)), schema="app")
    op.create_unique_constraint("uq_lots_enam_lot_id", "lots", ["enam_lot_id"], schema="app")


def downgrade() -> None:
    op.drop_constraint("uq_lots_enam_lot_id", "lots", schema="app", type_="unique")
    op.drop_column("lots", "enam_registered_at", schema="app")
    op.drop_column("lots", "enam_lot_id", schema="app")
    op.drop_column("lots", "enam_gate_id", schema="app")
