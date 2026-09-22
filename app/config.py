from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "Agri-Market Intelligence Platform"
    app_version: str = "0.1.0"
    environment: str = "local"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://app:app@localhost:5432/app"
    data_gov_api_key: str = ""
    data_gov_resource_url: str = (
        "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
    )
    ufsi_base_url: str = ""
    consent_signing_secret: str = ""
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    enam_base_url: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
