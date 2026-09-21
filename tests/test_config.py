from app.config import Settings, get_settings


def test_settings_read_prefixed_environment(monkeypatch) -> None:
    monkeypatch.setenv("AGRI_ENVIRONMENT", "staging")
    monkeypatch.setenv("AGRI_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv(
        "AGRI_DATABASE_URL",
        "postgresql+asyncpg://agri:agri@db.internal:5432/agri",
    )
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.environment == "staging"
        assert settings.log_level == "DEBUG"
        assert settings.database_url == "postgresql+asyncpg://agri:agri@db.internal:5432/agri"
    finally:
        get_settings.cache_clear()


def test_explicit_settings_override_environment(monkeypatch) -> None:
    monkeypatch.setenv("AGRI_ENVIRONMENT", "staging")

    settings = Settings(environment="test")

    assert settings.environment == "test"
