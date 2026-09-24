"""create outbox_events table for event-sourcing and audit log

Revision ID: 0011_outbox_events
Revises: 0010_settlements_and_erupi
Create Date: 2026-09-24

"""

import sqlalchemy as sa
from alembic import op

revision = "0011_outbox_events"
down_revision = "0010_settlements_and_erupi"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("stream_id", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("partition_key", sa.String(128), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("consent_artifact_id", sa.String(64)),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("event_id", name="uq_outbox_events_event_id"),
        schema="app",
    )
    op.create_index(
        "ix_app_outbox_events_event_id",
        "outbox_events",
        ["event_id"],
        schema="app",
    )
    op.create_index(
        "ix_app_outbox_events_stream_id",
        "outbox_events",
        ["stream_id"],
        schema="app",
    )
    op.create_index(
        "ix_app_outbox_events_event_type",
        "outbox_events",
        ["event_type"],
        schema="app",
    )
    op.create_index(
        "ix_app_outbox_events_partition_key",
        "outbox_events",
        ["partition_key"],
        schema="app",
    )
    op.create_index(
        "ix_app_outbox_events_consent_artifact_id",
        "outbox_events",
        ["consent_artifact_id"],
        schema="app",
    )
    op.create_index(
        "ix_app_outbox_events_occurred_at",
        "outbox_events",
        ["occurred_at"],
        schema="app",
    )
    op.create_index(
        "ix_app_outbox_events_published_at",
        "outbox_events",
        ["published_at"],
        schema="app",
    )


def downgrade() -> None:
    op.drop_table("outbox_events", schema="app")
