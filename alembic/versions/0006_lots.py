"""create assayed lot tables

Revision ID: 0006_lots
Revises: 0005_consents
Create Date: 2026-09-22

"""

import sqlalchemy as sa
from alembic import op

revision = "0006_lots"
down_revision = "0005_consents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lots",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("lot_code", sa.String(32), nullable=False),
        sa.Column("farmer_id", sa.String(64), nullable=False),
        sa.Column("commodity", sa.String(128), nullable=False),
        sa.Column("variety", sa.String(128), nullable=False),
        sa.Column("quantity_mt", sa.Numeric(12, 3), nullable=False),
        sa.Column("consent_artifact_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("lot_code", name="uq_lots_lot_code"),
        schema="app",
    )
    op.create_index("ix_lots_farmer_id", "lots", ["farmer_id"], schema="app")
    op.create_table(
        "assay_reports",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("lot_id", sa.BigInteger, nullable=False),
        sa.Column("grade", sa.String(64), nullable=False),
        sa.Column("foreign_matter_percent", sa.Numeric(5, 2)),
        sa.Column("moisture_percent", sa.Numeric(5, 2)),
        sa.Column("damaged_percent", sa.Numeric(5, 2)),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["lot_id"],
            ["app.lots.id"],
            name="fk_assay_reports_lot_id_lots",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("lot_id", name="uq_assay_reports_lot_id"),
        schema="app",
    )


def downgrade() -> None:
    op.drop_table("assay_reports", schema="app")
    op.drop_index("ix_lots_farmer_id", table_name="lots", schema="app")
    op.drop_table("lots", schema="app")
