"""rename the domain schema to app

Revision ID: 0003_rename_schema
Revises: 0002_price_observations
Create Date: 2026-09-21

"""

from alembic import op

revision = "0003_rename_schema"
down_revision = "0002_price_observations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Databases created before the schema was renamed still have the old name.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'agri')
               AND NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'app') THEN
                ALTER SCHEMA agri RENAME TO app;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    pass
