from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.session import Database


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_database(request: Request) -> Database:
    return request.app.state.database


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    database = get_database(request)
    async with database.session_factory() as session:
        yield session


SettingsDep = Annotated[Settings, Depends(get_settings)]
DatabaseDep = Annotated[Database, Depends(get_database)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
