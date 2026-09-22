from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_local_desk_origin_is_allowed() -> None:
    application = create_app(
        Settings(
            environment="test",
            log_level="WARNING",
            database_url="postgresql+asyncpg://app:app@127.0.0.1:1/app",
            cors_origins="http://127.0.0.1:5173",
        )
    )

    with TestClient(application) as client:
        response = client.get("/health", headers={"Origin": "http://127.0.0.1:5173"})

    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_unknown_origin_is_not_allowed() -> None:
    application = create_app(
        Settings(
            environment="test",
            log_level="WARNING",
            database_url="postgresql+asyncpg://app:app@127.0.0.1:1/app",
            cors_origins="http://127.0.0.1:5173",
        )
    )

    with TestClient(application) as client:
        response = client.get("/health", headers={"Origin": "http://evil.example"})

    assert "access-control-allow-origin" not in response.headers
