"""create farmer profile tables

Revision ID: 0004_farmers
Revises: 0003_rename_schema
Create Date: 2026-09-21

"""

import sqlalchemy as sa
from alembic import op

revision = "0004_farmers"
down_revision = "0003_rename_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "farmers",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("farmer_id", sa.String(64), nullable=False),
        sa.Column("state_lgd_code", sa.String(8), nullable=False),
        sa.Column("display_name", sa.String(256), nullable=False),
        sa.Column("consent_artifact_id", sa.String(128), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("farmer_id", name="uq_farmers_farmer_id"),
        schema="app",
    )
    op.create_table(
        "land_parcels",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("farmer_id", sa.BigInteger, nullable=False),
        sa.Column("farm_id", sa.String(14), nullable=False),
        sa.Column("area_hectares", sa.Numeric(12, 4)),
        sa.ForeignKeyConstraint(
            ["farmer_id"],
            ["app.farmers.id"],
            name="fk_land_parcels_farmer_id_farmers",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("farm_id", name="uq_land_parcels_farm_id"),
        schema="app",
    )
    op.create_table(
        "crop_records",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("parcel_id", sa.BigInteger, nullable=False),
        sa.Column("commodity", sa.String(128), nullable=False),
        sa.Column("season", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(
            ["parcel_id"],
            ["app.land_parcels.id"],
            name="fk_crop_records_parcel_id_land_parcels",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "parcel_id",
            "commodity",
            "season",
            name="uq_crop_records_parcel_commodity_season",
        ),
        schema="app",
    )


def downgrade() -> None:
    op.drop_table("crop_records", schema="app")
    op.drop_table("land_parcels", schema="app")
    op.drop_table("farmers", schema="app")
