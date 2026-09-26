"""create buyer_demand and add sync tombstone columns

Revision ID: 0019_sync_protocol_and_tombstones
Revises: 0018_ondc_v2_and_bap
Create Date: 2026-09-25

"""

import sqlalchemy as sa
from alembic import op

revision = "0019_sync_protocol_and_tombstones"
down_revision = "0018_ondc_v2_and_bap"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create buyer_demand table
    op.create_table(
        "buyer_demand",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("demand_id", sa.String(64), nullable=False),
        sa.Column("buyer_id", sa.String(64), nullable=False),
        sa.Column("org_id", sa.String(64), nullable=True),
        sa.Column("commodity", sa.String(128), nullable=False),
        sa.Column("variety", sa.String(128), nullable=True),
        sa.Column("target_grade", sa.String(64), nullable=True),
        sa.Column("quantity_mt", sa.Numeric(12, 3), nullable=False),
        sa.Column("target_price_per_mt", sa.BigInteger, nullable=True),
        sa.Column("delivery_location", sa.String(256), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("demand_id", name="uq_buyer_demand_demand_id"),
        schema="app",
    )
    op.create_index("ix_buyer_demand_org_id", "buyer_demand", ["org_id"], schema="app")
    op.create_index("ix_buyer_demand_status", "buyer_demand", ["status"], schema="app")
    op.create_index("ix_buyer_demand_updated_at", "buyer_demand", ["updated_at"], schema="app")

    # 2. Add soft-delete and sync timestamp columns to existing sync tables
    # farmers
    op.add_column("farmers", sa.Column("org_id", sa.String(64), nullable=True), schema="app")
    op.add_column("farmers", sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), schema="app")
    op.add_column("farmers", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), schema="app")
    op.add_column("farmers", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True), schema="app")
    op.create_index("ix_farmers_org_id", "farmers", ["org_id"], schema="app")
    op.create_index("ix_farmers_updated_at", "farmers", ["updated_at"], schema="app")

    # land_parcels
    op.add_column("land_parcels", sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), schema="app")
    op.add_column("land_parcels", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), schema="app")
    op.add_column("land_parcels", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True), schema="app")
    op.create_index("ix_land_parcels_updated_at", "land_parcels", ["updated_at"], schema="app")

    # lots
    op.add_column("lots", sa.Column("org_id", sa.String(64), nullable=True), schema="app")
    op.add_column("lots", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), schema="app")
    op.add_column("lots", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True), schema="app")
    op.create_index("ix_lots_org_id", "lots", ["org_id"], schema="app")
    op.create_index("ix_lots_updated_at", "lots", ["updated_at"], schema="app")

    # assay_reports
    op.add_column("assay_reports", sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), schema="app")
    op.add_column("assay_reports", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), schema="app")
    op.add_column("assay_reports", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True), schema="app")
    op.create_index("ix_assay_reports_updated_at", "assay_reports", ["updated_at"], schema="app")

    # facilities
    op.add_column("facilities", sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), schema="app")
    op.add_column("facilities", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), schema="app")
    op.add_column("facilities", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True), schema="app")
    op.create_index("ix_facilities_updated_at", "facilities", ["updated_at"], schema="app")

    # trade_contracts
    op.add_column("trade_contracts", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True), schema="app")

    # consent_artifacts
    op.add_column("consent_artifacts", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), schema="app")
    op.add_column("consent_artifacts", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True), schema="app")
    op.create_index("ix_consent_artifacts_updated_at", "consent_artifacts", ["updated_at"], schema="app")


def downgrade() -> None:
    op.drop_table("buyer_demand", schema="app")
    op.drop_column("farmers", "deleted_at", schema="app")
    op.drop_column("farmers", "updated_at", schema="app")
    op.drop_column("farmers", "created_at", schema="app")
    op.drop_column("farmers", "org_id", schema="app")
    op.drop_column("land_parcels", "deleted_at", schema="app")
    op.drop_column("land_parcels", "updated_at", schema="app")
    op.drop_column("land_parcels", "created_at", schema="app")
    op.drop_column("lots", "deleted_at", schema="app")
    op.drop_column("lots", "updated_at", schema="app")
    op.drop_column("lots", "org_id", schema="app")
    op.drop_column("assay_reports", "deleted_at", schema="app")
    op.drop_column("assay_reports", "updated_at", schema="app")
    op.drop_column("assay_reports", "created_at", schema="app")
    op.drop_column("facilities", "deleted_at", schema="app")
    op.drop_column("facilities", "updated_at", schema="app")
    op.drop_column("facilities", "created_at", schema="app")
    op.drop_column("trade_contracts", "deleted_at", schema="app")
    op.drop_column("consent_artifacts", "deleted_at", schema="app")
    op.drop_column("consent_artifacts", "updated_at", schema="app")
