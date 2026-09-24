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
    ondc_bpp_id: str = "market.local"
    ondc_bpp_uri: str = "http://127.0.0.1:8000/beckn"
    ondc_bpp_name: str = "Market desk"
    ondc_commission_percent: int = 0
    ondc_support_phone: str = "+911800123456"
    ondc_support_email: str = "grievance@market.local"
    ondc_tracking_base_url: str = "https://track.market.local/shipments"
    erupi_issuer_id: str = "ONDC-RSP-PARTNER-BANK"
    erupi_validity_days: int = 30
    settlement_tds_rate_bps: int = 100


@lru_cache
def get_settings() -> Settings:
    return Settings()
