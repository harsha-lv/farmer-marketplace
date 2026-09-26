"""create assay_models and add edge AI assay columns to assay_reports

Revision ID: 0020_assay_ai_models
Revises: 0019_sync_protocol_and_tombstones
Create Date: 2026-09-25

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0020_assay_ai_models"
down_revision = "0019_sync_protocol_and_tombstones"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create assay_models table in schema app
    op.create_table(
        "assay_models",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("architecture", sa.String(length=64), nullable=False),
        sa.Column("onnx_path", sa.String(length=255), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("input_size", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("class_map", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", "version", name="uq_assay_models_name_version"),
        schema="app",
    )
    op.create_index(
        "ix_assay_models_name_status",
        "assay_models",
        ["name", "status"],
        unique=False,
        schema="app",
    )

    # 2. Add AI inference and tamper-evident columns to assay_reports
    op.add_column("assay_reports", sa.Column("image_hash", sa.String(length=64), nullable=True), schema="app")
    op.add_column("assay_reports", sa.Column("model_versions", postgresql.JSONB(astext_type=sa.Text()), nullable=True), schema="app")
    op.add_column("assay_reports", sa.Column("hmac_signature", sa.String(length=128), nullable=True), schema="app")
    op.add_column("assay_reports", sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True), schema="app")
    op.add_column("assay_reports", sa.Column("discoloration_severity_score", sa.Numeric(precision=5, scale=2), nullable=True), schema="app")
    op.add_column("assay_reports", sa.Column("pest_infestation_score", sa.Numeric(precision=5, scale=2), nullable=True), schema="app")
    op.add_column("assay_reports", sa.Column("grain_size_distribution", postgresql.JSONB(astext_type=sa.Text()), nullable=True), schema="app")
    op.add_column("assay_reports", sa.Column("fallback", sa.String(length=32), nullable=True), schema="app")
    op.add_column("assay_reports", sa.Column("ai_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True), schema="app")


def downgrade() -> None:
    op.drop_column("assay_reports", "ai_details", schema="app")
    op.drop_column("assay_reports", "fallback", schema="app")
    op.drop_column("assay_reports", "grain_size_distribution", schema="app")
    op.drop_column("assay_reports", "pest_infestation_score", schema="app")
    op.drop_column("assay_reports", "discoloration_severity_score", schema="app")
    op.drop_column("assay_reports", "confidence", schema="app")
    op.drop_column("assay_reports", "hmac_signature", schema="app")
    op.drop_column("assay_reports", "model_versions", schema="app")
    op.drop_column("assay_reports", "image_hash", schema="app")
    op.drop_index("ix_assay_models_name_status", table_name="assay_models", schema="app")
    op.drop_table("assay_models", schema="app")
