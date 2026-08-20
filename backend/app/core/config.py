"""Application settings loaded from environment variables.

All configuration is typed and validated via ``pydantic-settings``. The
:func:`get_settings` accessor caches the singleton instance so importers
never re-parse the environment on each call.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

type Environment = Literal["development", "staging", "production", "test"]
type LogLevel = Literal["debug", "info", "warning", "error", "critical"]


class Settings(BaseSettings):
    """Typed, immutable application settings."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # pydantic-settings adds "settings_" to the default protected namespaces,
        # which would warn on our intentional ``settings_encryption_key`` field.
        # Keep only the pydantic-core "model_" guard (the documented resolution).
        protected_namespaces=("model_",),
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

    # ----- Application-layer rate limiting -----
    # Edge/nginx limits stay primary; these values protect direct backend
    # access. Per-client, per-60s sliding window.
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    rate_limit_general_per_minute: int = Field(
        default=600, alias="RATE_LIMIT_GENERAL_PER_MINUTE", ge=1
    )
    rate_limit_auth_per_minute: int = Field(
        default=60, alias="RATE_LIMIT_AUTH_PER_MINUTE", ge=1
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
    celery_queue_names_raw: str = Field(
        default="legalops.default",
        alias="CELERY_QUEUE_NAMES",
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
    # Retired/rotated public keys kept active for verification so tokens signed
    # by a previous key remain valid until they expire (zero-downtime rotation).
    # JSON array of PEM strings, e.g.
    #   JWT_PUBLIC_KEYS='["-----BEGIN PUBLIC KEY-----\n...", "..."]'
    jwt_public_keys: str | None = Field(default=None, alias="JWT_PUBLIC_KEYS")
    # Explicit key id (kid) for the active signing key. When unset, the kid is
    # derived deterministically from the active public key's SHA-256 thumbprint.
    jwt_key_id: str | None = Field(default=None, alias="JWT_KEY_ID")
    # When true, RS256 tokens without a kid header are rejected (fail-closed).
    # Leave false during rollout so legacy (pre-rotation) tokens still verify;
    # flip to true once every active token carries a kid.
    jwt_require_kid: bool = Field(default=False, alias="JWT_REQUIRE_KID")

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

    # ----- Cloudflare Access edge authentication -----
    # Required when production runs in Access-only mode:
    #   APP_ENV=production SSO_MODE=stub EDGE_AUTH_BOUNDARY=cloudflare-access
    # The issuer/team domain should include the scheme, e.g.
    #   https://<team-name>.cloudflareaccess.com
    cloudflare_access_issuer: str | None = Field(default=None, alias="CLOUDFLARE_ACCESS_ISSUER")
    cloudflare_access_audience: str | None = Field(default=None, alias="CLOUDFLARE_ACCESS_AUD")
    cloudflare_access_certs_url: str | None = Field(
        default=None,
        alias="CLOUDFLARE_ACCESS_CERTS_URL",
    )

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

    # ----- Claude API (Agents ② contract reading/summary, ③ drafting) -----
    # NOTE: The production Claude API key is UNAVAILABLE until 2026-07-01.
    # Until then the system MUST degrade gracefully: Claude-backed agents stay
    # dormant (no crash) while the Perplexity research agent runs from day one.
    # The default sentinel below is treated as "unconfigured" by the AI layer.
    claude_api_key: SecretStr = Field(
        default=SecretStr("sk-ant-replace-me"),
        alias="CLAUDE_API_KEY",
    )
    claude_model: str = Field(default="claude-opus-4-7", alias="CLAUDE_MODEL")
    claude_max_tokens: int = Field(default=4096, alias="CLAUDE_MAX_TOKENS")
    claude_timeout_seconds: int = Field(default=60, alias="CLAUDE_TIMEOUT_SECONDS")

    # ----- Perplexity API (Agent ①: contract research, web-grounded) -----
    # Sonar API runs Zero Data Retention by default. Confidential contract
    # bodies are NEVER sent here — only abstracted issues/keywords — and the
    # client restricts citations to a public-source allowlist (e-Gov / 国交省 /
    # 裁判所) so that every answer carries an auditable provenance trail.
    perplexity_api_key: SecretStr | None = Field(default=None, alias="PERPLEXITY_API_KEY")
    perplexity_model: str = Field(default="sonar", alias="PERPLEXITY_MODEL")
    perplexity_base_url: str = Field(
        default="https://api.perplexity.ai", alias="PERPLEXITY_BASE_URL"
    )
    perplexity_timeout_seconds: int = Field(default=45, alias="PERPLEXITY_TIMEOUT_SECONDS")
    deepseek_timeout_seconds: int = Field(default=45, alias="DEEPSEEK_TIMEOUT_SECONDS")

    # ----- Settings-at-rest encryption -----
    # Fernet key used to encrypt provider API keys before they touch the DB.
    # If unset, settings_service derives a deterministic key from jwt_secret so
    # stored secrets are ALWAYS encrypted at rest (fail-closed: never plaintext).
    settings_encryption_key: SecretStr | None = Field(default=None, alias="SETTINGS_ENCRYPTION_KEY")

    # ----- Audit / Hash chain -----
    hash_chain_secret: SecretStr = Field(
        default=SecretStr("change-me-hash-chain-secret"),
        alias="HASH_CHAIN_SECRET",
    )
    audit_retention_years: int = Field(default=10, alias="AUDIT_RETENTION_YEARS")
    audit_log_sink: str = Field(default="stdout", alias="AUDIT_LOG_SINK")

    # ----- P0-6: WORM 相当の監査アンカー外部保管 -----
    # 日次アンカーを書き出す外部シンク。未設定ならアンカーは DB 内のみ
    # （改ざん検知は DB 内ハッシュチェーン + 日次署名で担保）。
    worm_sink_url: str = Field(default="", alias="WORM_SINK_URL")
    worm_sink_auth_token: SecretStr = Field(
        default=SecretStr(""), alias="WORM_SINK_AUTH_TOKEN"
    )
    audit_anchor_sink_path: str = Field(
        default="", alias="AUDIT_ANCHOR_SINK_PATH"
    )

    # ----- P0-6: Microsoft Sentinel 転送（未設定時は fail-closed） -----
    sentinel_enabled: bool = Field(default=False, alias="SENTINEL_ENABLED")
    sentinel_workspace_id: str = Field(default="", alias="SENTINEL_WORKSPACE_ID")
    sentinel_primary_key: SecretStr = Field(
        default=SecretStr(""), alias="SENTINEL_PRIMARY_KEY"
    )
    sentinel_dcr_uri: str = Field(
        default="", alias="SENTINEL_DCR_URI"
    )

    # ----- P0-6: AI 入出力の保存期間（Legal Hold で停止） -----
    retention_ai_input_days: int = Field(default=90, alias="RETENTION_AI_INPUT_DAYS")
    retention_ai_output_days: int = Field(default=365, alias="RETENTION_AI_OUTPUT_DAYS")
    retention_attachment_days: int = Field(
        default=3650, alias="RETENTION_ATTACHMENT_DAYS"
    )

    # ----- JPO 特許情報取得API（知財管理・競合ウォッチ・審査書類収集） -----
    # mode=demo の場合は ID/PW 不要で決定的なデモデータを返す（MVP 既定）。
    # mode=live にするには特許庁への利用登録で発行された ID/PW が必要。
    jpo_api_mode: str = Field(default="demo", alias="JPO_API_MODE")
    jpo_api_id: SecretStr = Field(default=SecretStr(""), alias="JPO_API_ID")
    jpo_api_password: SecretStr = Field(default=SecretStr(""), alias="JPO_API_PASSWORD")
    jpo_api_base_url: str = Field(
        default="https://ip-data.jpo.go.jp", alias="JPO_API_BASE_URL"
    )
    # 国内 API の 1 分あたり上限（特許庁の利用条件: 10 回/分）。
    jpo_api_max_calls_per_minute: int = Field(
        default=10, alias="JPO_API_MAX_CALLS_PER_MINUTE", ge=1, le=60
    )
    # 同期 1 回あたりに JPO API を呼ぶ最大回数（日次上限を尊重するための安全弁）。
    jpo_api_max_sync_calls: int = Field(
        default=30, alias="JPO_API_MAX_SYNC_CALLS", ge=1, le=200
    )

    # ----- Feature flags -----
    feature_ai_review: bool = Field(default=True, alias="FEATURE_AI_REVIEW")
    feature_sharepoint_sync: bool = Field(default=False, alias="FEATURE_SHAREPOINT_SYNC")
    feature_desknet_sync: bool = Field(default=False, alias="FEATURE_DESKNET_SYNC")
    feature_ip_management: bool = Field(default=True, alias="FEATURE_IP_MANAGEMENT")

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
    def celery_queue_names(self) -> list[str]:
        """Parsed Celery queue names for operational queue-depth metrics."""
        return [q.strip() for q in self.celery_queue_names_raw.split(",") if q.strip()]

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

    @property
    def jwt_public_keys_list(self) -> list[str]:
        """Parsed retired/rotated public keys (JSON array of PEM strings).

        Returns an empty list when ``JWT_PUBLIC_KEYS`` is unset, blank, or
        malformed. Malformed input is treated fail-closed as "no extra keys":
        an operator misconfiguration must never silently widen the set of
        trusted verification keys, yet it must also not crash application boot.
        Non-string / blank entries are dropped.
        """
        raw = self.jwt_public_keys
        if not raw or not raw.strip():
            return []
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            logger.warning(
                "JWT_PUBLIC_KEYS is not valid JSON; ignoring retired keys "
                "(verification will use the active key only)"
            )
            return []
        if not isinstance(parsed, list):
            logger.warning(
                "JWT_PUBLIC_KEYS must be a JSON array of PEM strings; ignoring retired keys"
            )
            return []
        return [pem for pem in parsed if isinstance(pem, str) and pem.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()


settings: Settings = get_settings()
