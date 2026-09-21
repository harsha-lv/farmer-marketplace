from unittest.mock import AsyncMock, Mock

import pytest

from app.db.session import Database


@pytest.fixture
async def database():
    db = Database("postgresql+asyncpg://app:app@127.0.0.1:1/app")
    yield db
    await db.dispose()


async def test_ping_succeeds_when_query_runs(database: Database, monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    async def select_one() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(database, "_select_one", select_one)

    assert await database.ping() is True
    assert called


async def test_select_one_runs_ping_statement(database: Database) -> None:
    connection = AsyncMock()
    context = AsyncMock()
    context.__aenter__.return_value = connection
    context.__aexit__.return_value = None
    original = database.engine
    database.engine = Mock(connect=Mock(return_value=context))
    try:
        await database._select_one()
    finally:
        database.engine = original

    statement = connection.execute.await_args.args[0]
    assert str(statement) == "SELECT 1"


async def test_ping_fails_closed_when_connect_raises(
    database: Database, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def select_one() -> None:
        raise OSError("connection refused")

    monkeypatch.setattr(database, "_select_one", select_one)

    with caplog.at_level("WARNING"):
        assert await database.ping() is False

    assert "database ping failed" in caplog.text
