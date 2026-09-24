"""create facilities table for postgis spatial routing and allocation

Revision ID: 0015_spatial_facilities
Revises: 0014_timescaledb_continuous_aggregates
Create Date: 2026-09-24

"""

import sqlalchemy as sa
from alembic import op

revision = "0015_spatial_facilities"
down_revision = "0014_timescaledb_continuous_aggregates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "facilities",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("facility_type", sa.String(32), nullable=False),
        sa.Column("wdra_registration_no", sa.String(64), nullable=True),
        sa.Column("state", sa.String(128), nullable=False),
        sa.Column("district", sa.String(128), nullable=False),
        sa.Column("pincode", sa.String(12), nullable=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("capacity_quintals", sa.Numeric(12, 2), nullable=False),
        sa.Column("available_quintals", sa.Numeric(12, 2), nullable=False),
        sa.Column("cold_storage", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column(
            "daily_charge_inr_per_quintal",
            sa.Numeric(8, 2),
            nullable=False,
            server_default="0.50",
        ),
        schema="app",
    )
    op.create_index(
        "ix_facilities_location",
        "facilities",
        ["latitude", "longitude"],
        schema="app",
    )
    op.create_index(
        "ix_facilities_type_state",
        "facilities",
        ["facility_type", "state"],
        schema="app",
    )


def downgrade() -> None:
    op.drop_index("ix_facilities_type_state", table_name="facilities", schema="app")
    op.drop_index("ix_facilities_location", table_name="facilities", schema="app")
    op.drop_table("facilities", schema="app")
