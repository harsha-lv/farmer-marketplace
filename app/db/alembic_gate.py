"""Startup database schema verification gate against Alembic migrations.

Ensures the database schema is at Alembic 'head' before accepting traffic.
If the database schema is behind or missing migrations, raises RuntimeError and aborts startup.
"""

import logging
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

logger = logging.getLogger("app.db.alembic_gate")


def get_sync_database_url(async_url: str) -> str:
    """Convert async SQLAlchemy database URL to sync driver URL for Alembic inspection."""
    if "postgresql+asyncpg://" in async_url:
        return async_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    elif "sqlite+aiosqlite://" in async_url:
        return async_url.replace("sqlite+aiosqlite://", "sqlite://")
    return async_url


def verify_database_at_alembic_head(database_url: str) -> bool:
    """Inspects the database revision and compares it to Alembic script directory head.

    Returns True if at head, or raises RuntimeError if behind head.
    """
    repo_root = Path(__file__).parent.parent.parent
    alembic_ini_path = repo_root / "alembic.ini"
    alembic_dir_path = repo_root / "alembic"

    if not alembic_ini_path.exists():
        logger.warning("alembic.ini not found at %s; skipping Alembic head check.", alembic_ini_path)
        return True

    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("script_location", str(alembic_dir_path))

    script_dir = ScriptDirectory.from_config(alembic_cfg)
    expected_head = script_dir.get_current_head()

    if not expected_head:
        logger.warning("No Alembic migration head found in repository.")
        return True

    sync_url = get_sync_database_url(database_url)
    engine = create_engine(sync_url)

    try:
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()

            if current_rev != expected_head:
                msg = (
                    f"CRITICAL: Database schema revision '{current_rev}' is not at Alembic head '{expected_head}'. "
                    f"Startup aborted. Run 'alembic upgrade head' before starting the application."
                )
                logger.critical(msg)
                raise RuntimeError(msg)

            logger.info("Database schema validated at Alembic head '%s'.", current_rev)
            return True
    finally:
        engine.dispose()
