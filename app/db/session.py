import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        self.engine: AsyncEngine = create_async_engine(url, pool_pre_ping=True)
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
