"""create consent artifact inventory

Revision ID: 0005_consents
Revises: 0004_farmers
Create Date: 2026-09-21

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_consents"
down_revision = "0004_farmers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consent_artifacts",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("artifact_id", sa.String(128), nullable=False),
        sa.Column("farmer_id", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(160), nullable=False),
        sa.Column("attributes", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True)),
        sa.Column("signature", sa.String(64), nullable=False),
        sa.UniqueConstraint("artifact_id", name="uq_consent_artifacts_artifact_id"),
        sa.CheckConstraint(
            "status IN ('active', 'withdrawn')",
            name="ck_consent_artifacts_status_known",
        ),
        schema="app",
    )


def downgrade() -> None:
    op.drop_table("consent_artifacts", schema="app")
