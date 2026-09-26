"""Alembic migration 0024: Exogenous price features and ML forecast model registry.

Creates:
  - app.price_features: Exogenous weather, calendar, harvest season, MSP, and macro variables
  - app.forecast_models: Versioned ML model registry (TFT/LSTM) with hyperparameters, metrics, and weights

Revision ID: 0024_forecast_features_and_models
Revises: 0023_performance_indexes_and_timescale
Create Date: 2026-09-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0024_forecast_features_and_models"
down_revision = "0023_performance_indexes_and_timescale"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    schema = "app" if is_postgres else None
    json_type = postgresql.JSONB(astext_type=sa.Text()) if is_postgres else sa.JSON()

    # 1. Create price_features table
    op.create_table(
        "price_features",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("commodity", sa.String(128), nullable=False),
        sa.Column("market", sa.String(128), nullable=False),
        sa.Column("feature_date", sa.Date(), nullable=False),
        sa.Column("rainfall_mm", sa.Float(), nullable=True),
        sa.Column("rainfall_normal_mm", sa.Float(), nullable=True),
        sa.Column("rainfall_deviation_pct", sa.Float(), nullable=True),
        sa.Column("temp_min_c", sa.Float(), nullable=True),
        sa.Column("temp_max_c", sa.Float(), nullable=True),
        sa.Column("is_festival", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("festival_name", sa.String(64), nullable=True),
        sa.Column("is_mandi_holiday", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_harvest_season", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("season_name", sa.String(32), nullable=True),
        sa.Column("sin_day_of_year", sa.Float(), nullable=True),
        sa.Column("cos_day_of_year", sa.Float(), nullable=True),
        sa.Column("sin_day_of_week", sa.Float(), nullable=True),
        sa.Column("cos_day_of_week", sa.Float(), nullable=True),
        sa.Column("msp_inr_per_quintal", sa.Float(), nullable=True),
        sa.Column("macro_inflation_pct", sa.Float(), nullable=True),
        sa.Column("macro_crude_usd", sa.Float(), nullable=True),
        sa.Column("raw_weather_json", json_type, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "commodity",
            "market",
            "feature_date",
            name="uq_price_features_comm_mkt_date",
        ),
        schema=schema,
    )
    op.create_index(
        "ix_price_features_comm_mkt_date",
        "price_features",
        ["commodity", "market", "feature_date"],
        unique=False,
        schema=schema,
    )

    # 2. Create forecast_models table
    op.create_table(
        "forecast_models",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("version", sa.String(64), unique=True, nullable=False),
        sa.Column("commodity", sa.String(128), nullable=False),
        sa.Column("market", sa.String(128), nullable=False),
        sa.Column("architecture", sa.String(32), nullable=False),
        sa.Column("feature_hash", sa.String(64), nullable=False),
        sa.Column("hyperparams", json_type, nullable=False),
        sa.Column("metrics", json_type, nullable=False),
        sa.Column("artifact_path", sa.String(256), nullable=True),
        sa.Column("weights_data", sa.Text(), nullable=True),
        sa.Column(
            "trained_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="CANDIDATE"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        schema=schema,
    )
    op.create_index(
        "ix_forecast_models_comm_mkt_status",
        "forecast_models",
        ["commodity", "market", "status"],
        unique=False,
        schema=schema,
    )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    schema = "app" if is_postgres else None

    op.drop_table("forecast_models", schema=schema)
    op.drop_table("price_features", schema=schema)
