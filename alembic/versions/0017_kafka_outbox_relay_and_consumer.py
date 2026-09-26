"""create processed_events table and extend outbox_events with kafka metadata

Revision ID: 0017_kafka_outbox_relay_and_consumer
Revises: 0016_auth_and_authorization
Create Date: 2026-09-25

"""

import sqlalchemy as sa
from alembic import op

revision = "0017_kafka_outbox_relay_and_consumer"
down_revision = "0016_auth_and_authorization"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add Kafka tracking columns to outbox_events
    op.add_column("outbox_events", sa.Column("kafka_topic", sa.String(128), nullable=True), schema="app")
    op.add_column("outbox_events", sa.Column("kafka_partition", sa.Integer(), nullable=True), schema="app")
    op.add_column("outbox_events", sa.Column("kafka_offset", sa.BigInteger(), nullable=True), schema="app")
    op.add_column(
        "outbox_events",
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        schema="app",
    )
    op.add_column("outbox_events", sa.Column("last_error", sa.Text(), nullable=True), schema="app")

    # 2. Create processed_events table for consumer idempotency
    op.create_table(
        "processed_events",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("consumer_group", sa.String(64), nullable=False),
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("consumer_group", "event_id", name="uq_processed_events_group_event"),
        schema="app",
    )
    op.create_index("ix_processed_events_event_id", "processed_events", ["event_id"], schema="app")


def downgrade() -> None:
    op.drop_index("ix_processed_events_event_id", table_name="processed_events", schema="app")
    op.drop_table("processed_events", schema="app")

    op.drop_column("outbox_events", "last_error", schema="app")
    op.drop_column("outbox_events", "retry_count", schema="app")
    op.drop_column("outbox_events", "kafka_offset", schema="app")
    op.drop_column("outbox_events", "kafka_partition", schema="app")
    op.drop_column("outbox_events", "kafka_topic", schema="app")
