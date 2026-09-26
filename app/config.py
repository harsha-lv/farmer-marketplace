"""Application settings — single source of truth for every configurable value.

Loaded by pydantic-settings with:
  - env_prefix = "APP_"          (primary canonical form)
  - nested_model_delimiter = "__" (e.g. APP_KAFKA__BOOTSTRAP_SERVERS for future nesting)
  - env_file = ".env"            (lowest priority, overridden by real env vars)

OTEL vars (OTEL_*) and a handful of legacy aliases are accepted via AliasChoices.
Never rename existing field names — only ADD new fields.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        populate_by_name=True,
    )

    # ── Application ───────────────────────────────────────────────────────────
    app_name: str = "Agri-Market Intelligence Platform"
    app_version: str = "0.1.0"
    environment: str = Field(
        default="local",
        description="Runtime tier: local | staging | production",
    )
    log_level: str = Field(
        default="INFO",
        validation_alias=AliasChoices("APP_LOG_LEVEL", "LOG_LEVEL"),
    )

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://app:app@localhost:5432/app",
        description="SQLAlchemy async DSN (asyncpg driver required).",
    )
    db_statement_timeout_ms: int = Field(
        default=15000,
        validation_alias=AliasChoices("APP_DB_STATEMENT_TIMEOUT_MS", "DB_STATEMENT_TIMEOUT_MS"),
    )
    check_alembic_head: bool = Field(
        default=False,
        validation_alias=AliasChoices("APP_CHECK_ALEMBIC_HEAD", "CHECK_ALEMBIC_HEAD"),
    )

    # ── Security / JWT ────────────────────────────────────────────────────────
    jwt_secret_key: str = Field(
        default="dev-secret-key-change-in-production-at-least-32-chars-long",
        description="HMAC-SHA256 secret for JWT signing. Must be >= 32 chars in production.",
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 30

    # ── OTP Authentication ───────────────────────────────────────────────────
    otp_ttl_seconds: int = Field(
        default=300,
        validation_alias=AliasChoices("APP_OTP_TTL_SECONDS", "OTP_TTL_SECONDS"),
        description="OTP validity period in seconds (default 5 minutes).",
    )
    otp_pepper: str = Field(
        default="agri-otp-pepper-salt-secret-key-32chars",
        validation_alias=AliasChoices("APP_OTP_PEPPER", "OTP_PEPPER"),
        description="HMAC pepper for hashing OTP verification codes.",
    )
    otp_provider: str = Field(
        default="log",
        validation_alias=AliasChoices("APP_OTP_PROVIDER", "OTP_PROVIDER"),
        description="OTP delivery provider: 'log' for dev or 'sms' for production SMS.",
    )
    otp_sms_adapter: str = Field(
        default="msg91",
        validation_alias=AliasChoices("APP_OTP_SMS_ADAPTER", "OTP_SMS_ADAPTER"),
        description="SMS Gateway adapter: 'msg91' | 'twilio' | 'gupshup'",
    )
    otp_sms_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("APP_OTP_SMS_API_KEY", "OTP_SMS_API_KEY"),
    )
    otp_sms_sender_id: str = Field(
        default="MTMNDI",
        validation_alias=AliasChoices("APP_OTP_SMS_SENDER_ID", "OTP_SMS_SENDER_ID"),
    )
    otp_sms_template_id: str = Field(
        default="",
        validation_alias=AliasChoices("APP_OTP_SMS_TEMPLATE_ID", "OTP_SMS_TEMPLATE_ID"),
    )
    otp_max_attempts: int = Field(default=5, description="Max invalid OTP verification attempts before lockout.")
    otp_lockout_seconds: int = Field(default=900, description="Lockout duration after max attempts (15 min).")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in ("production", "prod")


    # ── Redis / Cache ─────────────────────────────────────────────────────────
    redis_url: str = Field(
        default="",
        validation_alias=AliasChoices("APP_REDIS_URL", "REDIS_URL"),
        description="Redis DSN, e.g. redis://localhost:6379/0",
    )
    redis_pool_size: int = Field(
        default=50,
        validation_alias=AliasChoices("APP_REDIS_POOL_SIZE", "REDIS_POOL_SIZE"),
    )
    redis_timeout_ms: int = Field(
        default=1500,
        validation_alias=AliasChoices("APP_REDIS_TIMEOUT_MS", "REDIS_TIMEOUT_MS"),
    )
    cache_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("APP_CACHE_ENABLED", "CACHE_ENABLED"),
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: str = Field(
        default="http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5500,http://localhost:5500",
        validation_alias=AliasChoices("APP_CORS_ORIGINS", "CORS_ORIGINS"),
        description="Comma-separated list of allowed CORS origins.",
    )

    # ── Kafka ─────────────────────────────────────────────────────────────────
    kafka_bootstrap_servers: str = Field(
        default="",
        description="Comma-separated Kafka broker list, e.g. broker1:9092,broker2:9092",
    )
    kafka_client_id: str = "agri-platform"
    kafka_acks: str = "all"
    kafka_enable_idempotence: bool = True
    kafka_linger_ms: int = 10
    kafka_max_batch_size: int = 16384
    kafka_max_retry_attempts: int = 5
    kafka_retry_backoff_ms: int = 100
    kafka_dlq_topic: str = "agri.dlq"
    kafka_default_retention_ms: int = 604800000
    kafka_compliance_retention_ms: int = 31536000000

    # ── NATS JetStream ────────────────────────────────────────────────────────
    nats_url: str = Field(
        default="",
        description="NATS server URL, e.g. nats://localhost:4222",
    )
    nats_jetstream_max_messages: int = 100000
    nats_jetstream_max_bytes: int = 104857600
    nats_jetstream_max_age_seconds: int = 604800
    nats_jetstream_dedup_window_seconds: int = 120

    # ── Event Outbox / Relay ──────────────────────────────────────────────────
    event_outbox_batch_size: int = 100

    # ── External Data APIs ────────────────────────────────────────────────────
    data_gov_api_key: str = Field(
        default="",
        description="data.gov.in API key for AGMARKNET price ingestion.",
    )
    data_gov_resource_url: str = (
        "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
    )

    openweather_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("APP_OPENWEATHER_API_KEY", "OPENWEATHER_API_KEY"),
        description="OpenWeatherMap API key. Falls back to imd_api_key if unset.",
    )
    imd_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("APP_IMD_API_KEY", "IMD_API_KEY"),
        description="IMD API key (secondary weather source).",
    )

    # ── AgriStack / UFSI ─────────────────────────────────────────────────────
    ufsi_base_url: str = Field(
        default="",
        description="Unified Farmer Service Interface base URL.",
    )
    agristack_api_key: str = Field(default="", description="AgriStack API key.")
    agristack_base_url: str = ""

    # ── Consent / Signing ─────────────────────────────────────────────────────
    consent_signing_secret: str = Field(
        default="",
        description="HMAC secret used for consent artifact signing. Must be set in production.",
    )
    consent_manager_webhook_secret: str = Field(
        default="",
        validation_alias=AliasChoices(
            "APP_CONSENT_MANAGER_WEBHOOK_SECRET",
            "CONSENT_MANAGER_WEBHOOK_SECRET",
            "APP_CONSENT_SIGNING_SECRET",
            "CONSENT_SIGNING_SECRET",
        ),
        description="HMAC secret used for verifying inbound Consent Manager webhooks.",
    )
    allow_legacy_cm_signature: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "APP_ALLOW_LEGACY_CM_SIGNATURE",
            "ALLOW_LEGACY_CM_SIGNATURE",
        ),
        description="Whether to permit reconstructed canonical signature fallback for legacy Consent Managers.",
    )
    assay_hmac_secret: str = Field(
        default="assay-tamper-evident-hmac-secret-key-32chars",
        validation_alias=AliasChoices("APP_ASSAY_HMAC_SECRET", "ASSAY_HMAC_SECRET"),
        description="HMAC secret for assay report tamper-evidence. Must be set in production.",
    )

    # ── ONDC / Beckn BPP ─────────────────────────────────────────────────────
    ondc_bpp_id: str = "market.local"
    ondc_bpp_uri: str = "http://127.0.0.1:8000/beckn"
    ondc_bpp_name: str = "Market desk"
    ondc_commission_percent: int = 0
    ondc_support_phone: str = "+911800123456"
    ondc_support_email: str = "grievance@market.local"
    ondc_tracking_base_url: str = "https://track.market.local/shipments"
    ondc_auth_enabled: bool = False
    ondc_signing_private_key_hex: str = Field(
        default="",
        validation_alias=AliasChoices(
            "APP_ONDC_SIGNING_PRIVATE_KEY_HEX", "ONDC_SIGNING_PRIVATE_KEY_HEX"
        ),
        description=(
            "Hex-encoded 32-byte Ed25519 private key seed for Beckn request signing. "
            "Required in production when ondc_auth_enabled=true."
        ),
    )
    ondc_unique_key_id: str = "key-1"

    # ── ONDC / Beckn BAP ─────────────────────────────────────────────────────
    ondc_bap_id: str = "buyer.market.local"
    ondc_bap_uri: str = "http://127.0.0.1:8000/beckn/bap"
    ondc_registry_url: str = "http://127.0.0.1:8000/beckn/registry"

    # ── eNAM ─────────────────────────────────────────────────────────────────
    enam_base_url: str = ""

    # ── e-RUPI / Settlement ───────────────────────────────────────────────────
    erupi_issuer_id: str = "ONDC-RSP-PARTNER-BANK"
    erupi_validity_days: int = 30
    settlement_tds_rate_bps: int = 100

    # ── Pledge Finance ────────────────────────────────────────────────────────
    pledge_finance_default_ltv_bps: int = 7500
    pledge_finance_default_interest_bps: int = 700
    pledge_finance_default_lender: str = "NABARD Agri-Credit Partner Bank"

    # ── HTTP Client ───────────────────────────────────────────────────────────
    http_connect_timeout_seconds: float = Field(
        default=5.0,
        validation_alias=AliasChoices(
            "APP_HTTP_CONNECT_TIMEOUT_SECONDS", "HTTP_CONNECT_TIMEOUT_SECONDS"
        ),
    )
    http_read_timeout_seconds: float = Field(
        default=15.0,
        validation_alias=AliasChoices(
            "APP_HTTP_READ_TIMEOUT_SECONDS", "HTTP_READ_TIMEOUT_SECONDS"
        ),
    )
    http_write_timeout_seconds: float = Field(
        default=10.0,
        validation_alias=AliasChoices(
            "APP_HTTP_WRITE_TIMEOUT_SECONDS", "HTTP_WRITE_TIMEOUT_SECONDS"
        ),
    )
    http_pool_timeout_seconds: float = Field(
        default=5.0,
        validation_alias=AliasChoices(
            "APP_HTTP_POOL_TIMEOUT_SECONDS", "HTTP_POOL_TIMEOUT_SECONDS"
        ),
    )
    http_max_redirects: int = Field(
        default=5,
        validation_alias=AliasChoices("APP_HTTP_MAX_REDIRECTS", "HTTP_MAX_REDIRECTS"),
    )
    http_ssrf_allow_private: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "APP_HTTP_SSRF_ALLOW_PRIVATE", "HTTP_SSRF_ALLOW_PRIVATE"
        ),
    )
    max_request_body_size_bytes: int = 52428800

    # ── Server ────────────────────────────────────────────────────────────────
    server_request_timeout_seconds: float = Field(
        default=30.0,
        validation_alias=AliasChoices(
            "APP_SERVER_REQUEST_TIMEOUT_SECONDS", "SERVER_REQUEST_TIMEOUT_SECONDS"
        ),
    )

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    rate_limit_per_minute_default: int = 100
    rate_limit_per_minute_auth: int = 20
    rate_limit_per_minute_prices: int = 500

    # ── Inference / ML ────────────────────────────────────────────────────────
    inference_concurrency: int = Field(
        default=4,
        validation_alias=AliasChoices("APP_INFERENCE_CONCURRENCY", "INFERENCE_CONCURRENCY"),
    )
    inference_timeout_ms: int = Field(
        default=5000,
        validation_alias=AliasChoices("APP_INFERENCE_TIMEOUT_MS", "INFERENCE_TIMEOUT_MS"),
    )
    models_dir: str = Field(
        default="models",
        validation_alias=AliasChoices("APP_MODELS_DIR", "MODELS_DIR"),
        description="Filesystem path to the ONNX model artefacts directory.",
    )

    # ── Observability ─────────────────────────────────────────────────────────
    otel_exporter_otlp_endpoint: str = Field(
        default="",
        validation_alias=AliasChoices(
            "APP_OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLP_ENDPOINT"
        ),
        description="OTLP gRPC endpoint, e.g. http://otel-collector:4317",
    )
    otel_service_name: str = Field(
        default="agri-platform-backend",
        validation_alias=AliasChoices("APP_OTEL_SERVICE_NAME", "OTEL_SERVICE_NAME"),
    )
    otel_exporter_otlp_insecure: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "APP_OTEL_EXPORTER_OTLP_INSECURE", "OTEL_EXPORTER_OTLP_INSECURE"
        ),
    )
    metrics_token: str = Field(
        default="",
        validation_alias=AliasChoices("APP_METRICS_TOKEN", "METRICS_BEARER_TOKEN"),
        description="Bearer token protecting the /metrics endpoint. Required in production.",
    )

    # ── Worker process ────────────────────────────────────────────────────────
    run_workers_inline: bool = Field(
        default=False,
        validation_alias=AliasChoices("APP_RUN_WORKERS_INLINE", "RUN_WORKERS_INLINE"),
        description="Run background workers inside the web process (dev convenience only).",
    )

    # ── Validators ────────────────────────────────────────────────────────────
    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_log_level(cls, v: Any) -> str:
        return str(v).upper()

    @field_validator("environment", mode="before")
    @classmethod
    def _lower_environment(cls, v: Any) -> str:
        return str(v).lower()

    def validate_production(self) -> None:
        """Raise ValueError for any insecure or missing setting in production.

        Call this once during app startup when environment == 'production'.
        """
        if self.environment != "production":
            return

        errors: list[str] = []

        _weak_jwt = "dev-secret-key-change-in-production-at-least-32-chars-long"
        if not self.jwt_secret_key or self.jwt_secret_key == _weak_jwt:
            errors.append("APP_JWT_SECRET_KEY must be set to a strong secret in production.")
        if len(self.jwt_secret_key) < 32:
            errors.append("APP_JWT_SECRET_KEY must be at least 32 characters.")

        if not self.redis_url:
            errors.append("APP_REDIS_URL (or REDIS_URL) must be set in production.")
        if not self.kafka_bootstrap_servers:
            errors.append("APP_KAFKA_BOOTSTRAP_SERVERS must be set in production.")
        if not self.nats_url:
            errors.append("APP_NATS_URL must be set in production.")
        if not self.metrics_token:
            errors.append(
                "APP_METRICS_TOKEN (or METRICS_BEARER_TOKEN) must be set in production "
                "to protect the /metrics endpoint."
            )
        if not self.consent_signing_secret:
            errors.append("APP_CONSENT_SIGNING_SECRET must be set in production.")

        _weak_assay = "assay-tamper-evident-hmac-secret-key-32chars"
        if not self.assay_hmac_secret or self.assay_hmac_secret == _weak_assay:
            errors.append(
                "APP_ASSAY_HMAC_SECRET (or ASSAY_HMAC_SECRET) must be set in production."
            )
        if self.ondc_auth_enabled and not self.ondc_signing_private_key_hex:
            errors.append(
                "APP_ONDC_SIGNING_PRIVATE_KEY_HEX must be set when APP_ONDC_AUTH_ENABLED=true."
            )
        if not self.data_gov_api_key:
            errors.append(
                "APP_DATA_GOV_API_KEY should be set for price ingestion in production."
            )

        if errors:
            joined = "\n  - ".join(errors)
            raise ValueError(
                f"Production configuration is invalid. Fix the following:\n  - {joined}"
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
