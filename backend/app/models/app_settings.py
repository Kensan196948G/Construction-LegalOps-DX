"""``ai_provider_settings`` table model.

Persists per-provider AI integration settings (API key ciphertext, model id,
activation flag, last connection-test result) for the hybrid AI review stack:

* ``perplexity`` — Agent ① contract research (web-grounded, public sources only)
* ``claude``     — Agents ②/③ contract reading-summary + drafting

SECURITY: ``api_key_encrypted`` stores **Fernet ciphertext only** — the plaintext
API key never touches the database. Encryption/decryption is owned by
``app.services.settings_service`` (key from ``SETTINGS_ENCRYPTION_KEY`` or derived
from ``jwt_secret`` — fail-closed, never plaintext at rest).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

from ._mixins import IntPKMixin, TimestampMixin

# Allowed provider identifiers. Mirrors the hybrid AI architecture; enforced both
# in the API/schema layer and at the DB layer (defence in depth / fail-closed).
_ALLOWED_PROVIDER = ",".join(f"'{p}'" for p in ("perplexity", "claude"))


class AiProviderSetting(IntPKMixin, TimestampMixin, Base):
    """A single AI provider's stored configuration and last test outcome."""

    __tablename__ = "ai_provider_settings"

    # Provider discriminator — one row per provider (unique).
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    # Fernet ciphertext of the API key. NULL = key not yet configured.
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Optional model override (e.g. "sonar", "claude-opus-4-7"). NULL = use default.
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Operator toggle: whether this provider participates in AI orchestration.
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # Result of the most recent "設定テスト" (connection probe).
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_test_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            f"provider IN ({_ALLOWED_PROVIDER})",
            name="ck_ai_provider_settings_provider",
        ),
        CheckConstraint(
            "last_test_status IS NULL OR last_test_status IN ('ok','failed','unavailable')",
            name="ck_ai_provider_settings_test_status",
        ),
        Index(
            "ux_ai_provider_settings_provider",
            "provider",
            unique=True,
            postgresql_where="deleted_at IS NULL",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<AiProviderSetting id={self.id} provider={self.provider!r} "
            f"active={self.is_active} test={self.last_test_status!r}>"
        )
