"""create mandi price tables

Revision ID: 0002_price_observations
Revises: 0001_extensions
Create Date: 2026-09-21

"""

import sqlalchemy as sa
from alembic import op

revision = "0002_price_observations"
down_revision = "0001_extensions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "markets",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("state_name", sa.String(128), nullable=False),
        sa.Column("state_lgd_code", sa.String(8)),
        sa.Column("district_name", sa.String(128), nullable=False),
        sa.Column("district_lgd_code", sa.String(8)),
        sa.Column("market_name", sa.String(128), nullable=False),
        sa.UniqueConstraint(
            "state_name",
            "district_name",
            "market_name",
            name="uq_markets_state_district_market",
        ),
        schema="agri",
    )
    op.create_table(
        "commodities",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("group_name", sa.String(128)),
        sa.UniqueConstraint("name", name="uq_commodities_name"),
        schema="agri",
    )
    op.create_table(
        "price_observations",
        sa.Column("arrival_date", sa.Date, nullable=False),
        sa.Column("market_id", sa.BigInteger, nullable=False),
        sa.Column("commodity_id", sa.BigInteger, nullable=False),
        sa.Column("variety", sa.String(128), nullable=False),
        sa.Column("grade", sa.String(64), nullable=False),
        sa.Column("min_price_inr_per_quintal", sa.BigInteger, nullable=False),
        sa.Column("max_price_inr_per_quintal", sa.BigInteger, nullable=False),
        sa.Column("modal_price_inr_per_quintal", sa.BigInteger, nullable=False),
        sa.Column("arrivals_quintal", sa.Numeric(14, 2)),
        sa.ForeignKeyConstraint(
            ["market_id"],
            ["agri.markets.id"],
            name="fk_price_observations_market_id_markets",
        ),
        sa.ForeignKeyConstraint(
            ["commodity_id"],
            ["agri.commodities.id"],
            name="fk_price_observations_commodity_id_commodities",
        ),
        sa.PrimaryKeyConstraint(
            "arrival_date",
            "market_id",
            "commodity_id",
            "variety",
            "grade",
            name="pk_price_observations",
        ),
        sa.CheckConstraint(
            "min_price_inr_per_quintal >= 0",
            name="ck_price_observations_min_price_nonnegative",
        ),
        sa.CheckConstraint(
            "max_price_inr_per_quintal >= 0",
            name="ck_price_observations_max_price_nonnegative",
        ),
        sa.CheckConstraint(
            "modal_price_inr_per_quintal >= 0",
            name="ck_price_observations_modal_price_nonnegative",
        ),
        sa.CheckConstraint(
            "arrivals_quintal IS NULL OR arrivals_quintal >= 0",
            name="ck_price_observations_arrivals_nonnegative",
        ),
        schema="agri",
    )
    op.create_index(
        "ix_price_observations_commodity_arrival",
        "price_observations",
        ["commodity_id", "arrival_date"],
        schema="agri",
    )
    # Partition column must already be part of the primary key.
    op.execute(
        "SELECT create_hypertable("
        "'agri.price_observations', 'arrival_date', if_not_exists => TRUE)"
    )


def downgrade() -> None:
    op.drop_index(
        "ix_price_observations_commodity_arrival",
        table_name="price_observations",
        schema="agri",
    )
    op.drop_table("price_observations", schema="agri")
    op.drop_table("commodities", schema="agri")
    op.drop_table("markets", schema="agri")
