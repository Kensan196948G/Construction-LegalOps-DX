"""Application settings loaded from environment variables.

All configuration is typed and validated via ``pydantic-settings``. The
:func:`get_settings` accessor caches the singleton instance so importers
never re-parse the environment on each call.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

type Environment = Literal["development", "staging", "production", "test"]
type LogLevel = Literal["debug", "info", "warning", "error", "critical"]


class Settings(BaseSettings):
    """Typed, immutable application settings."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ----- Runtime -----
    app_env: Environment = Field(default="development", alias="APP_ENV")
    log_level: LogLevel = Field(default="info", alias="LOG_LEVEL")
    tz: str = Field(default="Asia/Tokyo", alias="TZ")
    app_name: str = Field(default="Construction-LegalOps-DX", alias="APP_NAME")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    debug: bool = Field(default=False, alias="DEBUG")

    # ----- Networking -----
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")
    cors_origins_raw: str = Field(
        default="http://localhost:3000,http://localhost",
        alias="CORS_ORIGINS",
    )
    trusted_hosts_raw: str = Field(
        default="*",
        alias="TRUSTED_HOSTS",
    )

    # ----- Database -----
    db_url: SecretStr = Field(
        default=SecretStr("postgresql+asyncpg://legalops:legalops_dev@postgres:5432/legalops"),
        alias="DB_URL",
    )
    db_pool_size: int = Field(default=10, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, alias="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, alias="DB_POOL_TIMEOUT")
    db_echo: bool = Field(default=False, alias="DB_ECHO")

    # ----- Redis -----
    redis_url: SecretStr = Field(
        default=SecretStr("redis://redis:6379/0"),
        alias="REDIS_URL",
    )

    # ----- JWT / Auth -----
    jwt_secret: SecretStr = Field(
        default=SecretStr("change-me-to-a-secure-random-string"),
        alias="JWT_SECRET",
    )
    # RS256 asymmetric keys (PEM format). When both are set, RS256 is used
    # and jwt_secret / jwt_algorithm are ignored. Leave unset to fall back
    # to the legacy HS256 path (dev / test only).
    jwt_private_key: SecretStr | None = Field(default=None, alias="JWT_PRIVATE_KEY")
    jwt_public_key: str | None = Field(default=None, alias="JWT_PUBLIC_KEY")

    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=60, alias="JWT_EXPIRE_MINUTES")
    jwt_issuer: str = Field(
        default="construction-legalops-dx",
        alias="JWT_ISSUER",
    )
    jwt_audience: str = Field(
        default="construction-legalops-dx-api",
        alias="JWT_AUDIENCE",
    )
    session_cookie_max_age: int = Field(default=3600, alias="SESSION_COOKIE_MAX_AGE")

    # ----- CSP enforcement -----
    # True → enforce CSP; False → Content-Security-Policy-Report-Only.
    # Defaults to is_production so existing deploy configs are unaffected.
    # Operators can set CSP_ENFORCE=true on staging to gate before prod.
    csp_enforce: bool | None = Field(default=None, alias="CSP_ENFORCE")

    # ----- Entra ID -----
    entra_tenant_id: str = Field(
        default="00000000-0000-0000-0000-000000000000",
        alias="ENTRA_TENANT_ID",
    )
    entra_client_id: str = Field(
        default="00000000-0000-0000-0000-000000000000",
        alias="ENTRA_CLIENT_ID",
    )
    entra_client_secret: SecretStr = Field(
        default=SecretStr("replace-with-entra-app-secret"),
        alias="ENTRA_CLIENT_SECRET",
    )
    entra_redirect_uri: str = Field(
        default="http://localhost:3000/auth/callback",
        alias="ENTRA_REDIRECT_URI",
    )
    entra_scopes: str = Field(
        default="openid profile email offline_access User.Read",
        alias="ENTRA_SCOPES",
    )

    # ----- Claude API -----
    claude_api_key: SecretStr = Field(
        default=SecretStr("sk-ant-replace-me"),
        alias="CLAUDE_API_KEY",
    )
    claude_model: str = Field(default="claude-opus-4-7", alias="CLAUDE_MODEL")
    claude_max_tokens: int = Field(default=4096, alias="CLAUDE_MAX_TOKENS")
    claude_timeout_seconds: int = Field(default=60, alias="CLAUDE_TIMEOUT_SECONDS")

    # ----- Audit / Hash chain -----
    hash_chain_secret: SecretStr = Field(
        default=SecretStr("change-me-hash-chain-secret"),
        alias="HASH_CHAIN_SECRET",
    )
    audit_retention_years: int = Field(default=10, alias="AUDIT_RETENTION_YEARS")
    audit_log_sink: str = Field(default="stdout", alias="AUDIT_LOG_SINK")

    # ----- Feature flags -----
    feature_ai_review: bool = Field(default=True, alias="FEATURE_AI_REVIEW")
    feature_sharepoint_sync: bool = Field(default=False, alias="FEATURE_SHAREPOINT_SYNC")
    feature_desknet_sync: bool = Field(default=False, alias="FEATURE_DESKNET_SYNC")

    # ----- Validators / computed -----

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> object:
        if isinstance(value, str):
            return value.lower()
        return value

    @field_validator("app_env", mode="before")
    @classmethod
    def _normalize_app_env(cls, value: object) -> object:
        if isinstance(value, str):
            lowered = value.lower()
            # Accept common aliases.
            return {"prod": "production", "dev": "development", "stg": "staging"}.get(
                lowered, lowered
            )
        return value

    @property
    def environment(self) -> Environment:
        """Backwards-compatible alias for ``app_env``."""
        return self.app_env

    @property
    def cors_origins(self) -> list[str]:
        """Parsed CORS origin list (comma-separated env var)."""
        return [o.strip() for o in self.cors_origins_raw.split(",") if o.strip()]

    @property
    def trusted_hosts(self) -> list[str]:
        """Parsed trusted hosts list (comma-separated env var)."""
        return [h.strip() for h in self.trusted_hosts_raw.split(",") if h.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_csp_enforce(self) -> bool:
        """Whether to emit Content-Security-Policy (enforce) vs Report-Only."""
        if self.csp_enforce is not None:
            return self.csp_enforce
        return self.is_production

    @property
    def use_rs256(self) -> bool:
        """True when RS256 asymmetric keys are configured."""
        return bool(self.jwt_private_key and self.jwt_public_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()


settings: Settings = get_settings()
