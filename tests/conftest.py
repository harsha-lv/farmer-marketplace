import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environment="test",
        log_level="WARNING",
        database_url="postgresql+asyncpg://app:app@127.0.0.1:1/app",
    )


@pytest.fixture
def client(settings: Settings):
    application = create_app(settings)
    with TestClient(application) as test_client:
        yield test_client
