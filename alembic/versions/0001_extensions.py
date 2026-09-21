"""enable postgis timescaledb and agri schema

Revision ID: 0001_extensions
Revises:
Create Date: 2026-09-21

"""

from alembic import op

revision = "0001_extensions"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # TimescaleDB refuses CREATE EXTENSION inside Alembic's transaction.
    with op.get_context().autocommit_block():
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    op.execute("CREATE SCHEMA IF NOT EXISTS agri")


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS agri CASCADE")
    # Extensions stay installed; other databases on the cluster may use them.
