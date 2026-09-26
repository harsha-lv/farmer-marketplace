import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)


class Database:
    def __init__(
        self,
        url: str,
        statement_timeout_ms: int | None = None,
    ) -> None:
        self.url = url
        connect_args: dict[str, Any] = {}
        try:
            from app.config import get_settings
            settings = get_settings()
            stmt_timeout = (
                statement_timeout_ms
                if statement_timeout_ms is not None
                else getattr(settings, "db_statement_timeout_ms", 15000)
            )
            if "postgresql+asyncpg" in url:
                connect_args["server_settings"] = {
                    "statement_timeout": str(stmt_timeout),
                }
                connect_args["timeout"] = float(getattr(settings, "http_connect_timeout_seconds", 5.0))
        except Exception:
            pass

        self.engine: AsyncEngine = create_async_engine(
            url,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        self._engine = self.engine
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def ping(self) -> bool:
        try:
            await self._select_one()
            return True
        except Exception as exc:
            logger.warning("database ping failed: %s", exc)
            return False

    async def _select_one(self) -> None:
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def dispose(self) -> None:
        await self.engine.dispose()
