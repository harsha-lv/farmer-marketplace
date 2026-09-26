"""create authentication, authorization, and audit tables

Revision ID: 0016_auth_and_authorization
Revises: 0015_spatial_facilities
Create Date: 2026-09-25

"""

import sqlalchemy as sa
from alembic import op

revision = "0016_auth_and_authorization"
down_revision = "0015_spatial_facilities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("fpo_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("phone", name="uq_users_phone"),
        schema="app",
    )
    op.create_index("ix_users_fpo_id", "users", ["fpo_id"], schema="app")
    op.create_index("ix_users_status", "users", ["status"], schema="app")

    # 2. roles
    roles_table = op.create_table(
        "roles",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.UniqueConstraint("name", name="uq_roles_name"),
        schema="app",
    )
    op.bulk_insert(
        roles_table,
        [
            {"name": "farmer", "description": "Agricultural producer with parcel/lot ownership"},
            {"name": "fpo_operator", "description": "Farmer Producer Organization administrator"},
            {"name": "assayer", "description": "Quality inspection and lot assay verifier"},
            {"name": "buyer", "description": "Commercial buyer and marketplace participant"},
            {"name": "bank", "description": "Financial institution / lender for pledge loans"},
            {"name": "logistics", "description": "Warehouse and transport service provider"},
            {"name": "admin", "description": "Platform system administrator with full access"},
            {"name": "regulator", "description": "Compliance and statutory audit observer"},
        ],
    )

    # 3. user_roles
    op.create_table(
        "user_roles",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("app.users.id", name="fk_user_roles_user_id_users", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            sa.BigInteger,
            sa.ForeignKey("app.roles.id", name="fk_user_roles_role_id_roles", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("org_id", sa.String(128), nullable=True),
        sa.UniqueConstraint("user_id", "role_id", "org_id", name="uq_user_roles_user_role_org"),
        schema="app",
    )

    # 4. api_clients
    op.create_table(
        "api_clients",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("hashed_api_key", sa.String(256), nullable=False),
        sa.Column("key_prefix", sa.String(16), nullable=False),
        sa.Column("scopes", sa.String(512), nullable=False, server_default="lots:read,prices:read"),
        sa.Column("allowed_origins", sa.String(512), nullable=False, server_default=""),
        sa.Column("rate_limit_tier", sa.String(32), nullable=False, server_default="standard"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("client_id", name="uq_api_clients_client_id"),
        schema="app",
    )
    op.create_index("ix_api_clients_key_prefix", "api_clients", ["key_prefix"], schema="app")

    # 5. refresh_tokens
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("token_hash", sa.String(256), nullable=False),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("app.users.id", name="fk_refresh_tokens_user_id_users", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("family_id", sa.String(64), nullable=False),
        sa.Column("is_revoked", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
        schema="app",
    )
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"], schema="app")

    # 6. audit_log
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("actor_id", sa.String(128), nullable=True),
        sa.Column("actor_type", sa.String(32), nullable=False, server_default="user"),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("consent_artifact_id", sa.String(128), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("details", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="app",
    )
    op.create_index("ix_audit_log_actor_id", "audit_log", ["actor_id"], schema="app")
    op.create_index("ix_audit_log_request_id", "audit_log", ["request_id"], schema="app")
    op.create_index("ix_audit_log_action", "audit_log", ["action"], schema="app")


def downgrade() -> None:
    op.drop_index("ix_audit_log_action", table_name="audit_log", schema="app")
    op.drop_index("ix_audit_log_request_id", table_name="audit_log", schema="app")
    op.drop_index("ix_audit_log_actor_id", table_name="audit_log", schema="app")
    op.drop_table("audit_log", schema="app")

    op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens", schema="app")
    op.drop_table("refresh_tokens", schema="app")

    op.drop_index("ix_api_clients_key_prefix", table_name="api_clients", schema="app")
    op.drop_table("api_clients", schema="app")

    op.drop_table("user_roles", schema="app")
    op.drop_table("roles", schema="app")

    op.drop_index("ix_users_status", table_name="users", schema="app")
    op.drop_index("ix_users_fpo_id", table_name="users", schema="app")
    op.drop_table("users", schema="app")
