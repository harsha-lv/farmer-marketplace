"""Alembic migration 0023: Performance indexes and TimescaleDB policies.

Creates high-performance query indexes for hot query patterns:
  - price_observations (commodity_id, market_id, arrival_date DESC)
  - price_observations (market_id, arrival_date DESC) INCLUDE (modal_price_inr_per_quintal)
  - lots (status, fpo_id) partial index WHERE status = 'ACTIVE'
  - outbox_events (processed_at) partial index WHERE processed_at IS NULL
  - consent_artifacts (farmer_id, status)
  - trade_contracts (status, created_at)
  - assay_reports (lot_id, created_at DESC)

Adds TimescaleDB policies for app.mandi_weekly_rollups continuous aggregate:
  - Continuous aggregate refresh policy: schedule every 30 min, end_offset 5 min, start_offset 1 month
  - Raw price_observations compression policy: compress chunks older than 30 days
  - Raw price_observations retention policy: drop chunks older than 365 days

Revision ID: 0023_performance_indexes_and_timescale
Revises: 0022_logistics_shipments
Create Date: 2026-09-25
"""

import sqlalchemy as sa
from alembic import op

revision = "0023_performance_indexes_and_timescale"
down_revision = "0022_logistics_shipments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    # 1. Add fpo_id to lots if missing
    try:
        op.add_column("lots", sa.Column("fpo_id", sa.String(64), nullable=True), schema="app")
    except Exception:
        pass

    # 2. Add processed_at to outbox_events if missing
    try:
        op.add_column(
            "outbox_events",
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
            schema="app",
        )
    except Exception:
        pass

    # 3. Price observations composite index (commodity_id, market_id, arrival_date DESC)
    op.create_index(
        "ix_price_observations_commodity_market_arrival",
        "price_observations",
        ["commodity_id", "market_id", sa.text("arrival_date DESC")],
        schema="app" if dialect_name == "postgresql" else None,
        if_not_exists=True,
    )

    # 4. Covering index for market prices: (market_id, arrival_date DESC) INCLUDE (modal_price)
    if dialect_name == "postgresql":
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_price_observations_market_arrival_modal
            ON app.price_observations (market_id, arrival_date DESC)
            INCLUDE (modal_price_inr_per_quintal);
            """
        )
    else:
        op.create_index(
            "ix_price_observations_market_arrival_modal",
            "price_observations",
            ["market_id", sa.text("arrival_date DESC")],
            if_not_exists=True,
        )

    # 5. Partial index on active lots: lots (status, fpo_id) WHERE status = 'ACTIVE'
    if dialect_name == "postgresql":
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_lots_status_fpo_active
            ON app.lots (status, fpo_id)
            WHERE status = 'ACTIVE' OR status = 'active';
            """
        )
    else:
        op.create_index(
            "ix_lots_status_fpo_active",
            "lots",
            ["status", "fpo_id"],
            postgresql_where=sa.text("status = 'ACTIVE' OR status = 'active'"),
            if_not_exists=True,
        )

    # 6. Partial index on unprocessed outbox events: outbox_events (processed_at) WHERE processed_at IS NULL
    if dialect_name == "postgresql":
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_outbox_events_unprocessed
            ON app.outbox_events (processed_at)
            WHERE processed_at IS NULL;
            """
        )
    else:
        op.create_index(
            "ix_outbox_events_unprocessed",
            "outbox_events",
            ["processed_at"],
            postgresql_where=sa.text("processed_at IS NULL"),
            if_not_exists=True,
        )

    # 7. Consent artifacts query index: (farmer_id, status)
    op.create_index(
        "ix_consent_artifacts_farmer_status",
        "consent_artifacts",
        ["farmer_id", "status"],
        schema="app" if dialect_name == "postgresql" else None,
        if_not_exists=True,
    )

    # 8. Trade contracts status and temporal ordering: (status, created_at)
    op.create_index(
        "ix_trade_contracts_status_created_at",
        "trade_contracts",
        ["status", "created_at"],
        schema="app" if dialect_name == "postgresql" else None,
        if_not_exists=True,
    )

    # 9. Assay reports by lot and latest first: (lot_id, created_at DESC)
    op.create_index(
        "ix_assay_reports_lot_id_created_at",
        "assay_reports",
        ["lot_id", sa.text("created_at DESC")],
        schema="app" if dialect_name == "postgresql" else None,
        if_not_exists=True,
    )

    # 10. TimescaleDB continuous aggregate policies (refresh, compression, retention)
    if dialect_name == "postgresql":
        op.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
                    -- Add refresh policy for continuous aggregate view
                    BEGIN
                        PERFORM add_continuous_aggregate_policy(
                            'app.mandi_weekly_rollups',
                            start_offset => INTERVAL '1 month',
                            end_offset => INTERVAL '5 minutes',
                            schedule_interval => INTERVAL '30 minutes',
                            if_not_exists => TRUE
                        );
                    EXCEPTION WHEN OTHERS THEN
                        RAISE NOTICE 'Could not add continuous aggregate policy: %', SQLERRM;
                    END;

                    -- Add compression policy for raw price observations
                    BEGIN
                        ALTER TABLE app.price_observations SET (
                            timescaledb.compress,
                            timescaledb.compress_segmentby = 'market_id, commodity_id'
                        );
                    EXCEPTION WHEN OTHERS THEN
                        NULL;
                    END;

                    BEGIN
                        PERFORM add_compression_policy(
                            'app.price_observations',
                            INTERVAL '30 days',
                            if_not_exists => TRUE
                        );
                    EXCEPTION WHEN OTHERS THEN
                        NULL;
                    END;

                    -- Add retention policy for raw price observations
                    BEGIN
                        PERFORM add_retention_policy(
                            'app.price_observations',
                            INTERVAL '365 days',
                            if_not_exists => TRUE
                        );
                    EXCEPTION WHEN OTHERS THEN
                        NULL;
                    END;
                END IF;
            END $$;
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    schema_name = "app" if dialect_name == "postgresql" else None

    if dialect_name == "postgresql":
        op.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
                    BEGIN
                        PERFORM remove_continuous_aggregate_policy('app.mandi_weekly_rollups', if_exists => TRUE);
                        PERFORM remove_compression_policy('app.price_observations', if_exists => TRUE);
                        PERFORM remove_retention_policy('app.price_observations', if_exists => TRUE);
                    EXCEPTION WHEN OTHERS THEN
                        NULL;
                    END;
                END IF;
            END $$;
            """
        )

    op.drop_index("ix_assay_reports_lot_id_created_at", table_name="assay_reports", schema=schema_name)
    op.drop_index("ix_trade_contracts_status_created_at", table_name="trade_contracts", schema=schema_name)
    op.drop_index("ix_consent_artifacts_farmer_status", table_name="consent_artifacts", schema=schema_name)
    op.drop_index("ix_outbox_events_unprocessed", table_name="outbox_events", schema=schema_name)
    op.drop_index("ix_lots_status_fpo_active", table_name="lots", schema=schema_name)
    op.drop_index("ix_price_observations_market_arrival_modal", table_name="price_observations", schema=schema_name)
    op.drop_index("ix_price_observations_commodity_market_arrival", table_name="price_observations", schema=schema_name)
