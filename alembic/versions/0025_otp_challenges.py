"""Alembic migration 0025: OTP challenges for phone authentication and user profile completion.

Creates:
  - app.otp_challenges: Phone-based one-time password challenges with rate-limiting and audit tracking
  - Adds app.users.profile_complete flag

Revision ID: 0025_otp_challenges
Revises: 0024_forecast_features_and_models
Create Date: 2026-09-26
"""

import sqlalchemy as sa
from alembic import op

revision = "0025_otp_challenges"
down_revision = "0024_forecast_features_and_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    schema = "app" if is_postgres else None

    # 1. Create otp_challenges table
    op.create_table(
        "otp_challenges",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("phone_number", sa.String(32), nullable=False),
        sa.Column("code_hash", sa.String(128), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False, server_default="login"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="5"),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=schema,
    )

    # 2. Indexes
    op.create_index(
        "ix_otp_challenges_phone_number",
        "otp_challenges",
        ["phone_number"],
        schema=schema,
    )
    if is_postgres:
        op.create_index(
            "ix_otp_challenges_phone_created_desc",
            "otp_challenges",
            ["phone_number", sa.text("created_at DESC")],
            schema=schema,
        )
    else:
        op.create_index(
            "ix_otp_challenges_phone_created_desc",
            "otp_challenges",
            ["phone_number", "created_at"],
            schema=schema,
        )

    # 3. Add profile_complete column to users if not present
    op.add_column(
        "users",
        sa.Column("profile_complete", sa.Boolean(), nullable=False, server_default="false"),
        schema=schema,
    )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    schema = "app" if is_postgres else None

    op.drop_column("users", "profile_complete", schema=schema)
    op.drop_index("ix_otp_challenges_phone_created_desc", table_name="otp_challenges", schema=schema)
    op.drop_index("ix_otp_challenges_phone_number", table_name="otp_challenges", schema=schema)
    op.drop_table("otp_challenges", schema=schema)
