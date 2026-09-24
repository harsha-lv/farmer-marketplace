"""create timescaledb continuous aggregates for mandi price rollups

Revision ID: 0014_timescaledb_continuous_aggregates
Revises: 0013_pledge_finance
Create Date: 2026-09-24

"""

from alembic import op

revision = "0014_timescaledb_continuous_aggregates"
down_revision = "0013_pledge_finance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # TimescaleDB continuous aggregate view for weekly commodity rollups
    # Conditioned on TimescaleDB extension presence
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
                CREATE MATERIALIZED VIEW IF NOT EXISTS app.mandi_weekly_rollups
                WITH (timescaledb.continuous) AS
                SELECT
                    time_bucket('1 week', arrival_date) AS week_bucket,
                    market_id,
                    commodity_id,
                    variety,
                    grade,
                    min(min_price_inr_per_quintal) AS min_price,
                    max(max_price_inr_per_quintal) AS max_price,
                    round(avg(modal_price_inr_per_quintal)) AS avg_modal_price,
                    sum(arrivals_quintal) AS total_arrivals_quintal,
                    count(DISTINCT arrival_date) AS observation_days
                FROM app.price_observations
                GROUP BY week_bucket, market_id, commodity_id, variety, grade
                WITH NO DATA;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS app.mandi_weekly_rollups CASCADE;")
