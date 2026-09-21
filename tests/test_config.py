from app.config import Settings, get_settings


def test_settings_read_prefixed_environment(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "staging")
    monkeypatch.setenv("APP_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv(
        "APP_DATABASE_URL",
        "postgresql+asyncpg://app:app@db.internal:5432/app",
    )
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.environment == "staging"
        assert settings.log_level == "DEBUG"
        assert settings.database_url == "postgresql+asyncpg://app:app@db.internal:5432/app"
    finally:
        get_settings.cache_clear()


def test_explicit_settings_override_environment(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "staging")

    settings = Settings(environment="test")

    assert settings.environment == "test"
