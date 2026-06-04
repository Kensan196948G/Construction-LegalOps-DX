"""AI provider settings Pydantic schemas (hybrid AI review stack, Issue #28).

API contract for the admin "AI設定" panel. Two provider rows are managed:

* ``perplexity`` — Agent ① contract research (web-grounded, public sources only)
* ``claude``     — Agents ②/③ contract reading-summary + drafting

SECURITY INVARIANTS (enforced here at the API boundary):

* **Read never returns plaintext.** :class:`AiProviderConfigOut` exposes only a
  ``has_key`` flag and a short ``key_masked`` tail — the decrypted key never
  crosses the API boundary.
* **Provider / status are ``Literal``-validated** so a malformed value is
  rejected with HTTP 422 *before* it reaches the DB ``CheckConstraint``
  (defence in depth / fail-closed).
* **``api_key=None`` on update means "leave the stored key unchanged"**, so the
  frontend can toggle ``is_active`` / ``model`` without re-transmitting the
  secret.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, SecretStr

from .common import ORMModel

# Provider discriminator — mirrors the DB CheckConstraint and the ORM model.
AiProvider = Literal["perplexity", "claude"]
# Connection-probe ("設定テスト") outcome vocabulary.
#   ok          — provider reachable and the key authenticated
#   failed      — provider reachable but auth/other error
#   unavailable — provider intentionally dormant (e.g. Claude until 2026-07-01)
ConnectionTestStatus = Literal["ok", "failed", "unavailable"]


class AiSettingsUpdateIn(BaseModel):
    """Body of ``PUT /admin/ai-settings/{provider}`` ("保存・設定")."""

    # ``None`` => keep the currently stored key (do not overwrite / clear).
    api_key: SecretStr | None = None
    # Optional model override (e.g. "sonar", "claude-opus-4-7"). ``None`` => default.
    model: Annotated[str, Field(max_length=64)] | None = None
    is_active: bool = False


class AiProviderConfigOut(ORMModel):
    """Masked read schema for ``GET /admin/ai-settings`` rows.

    Loads from an :class:`~app.models.app_settings.AiProviderSetting` row but
    **omits the ciphertext entirely** — only the presence flag and a masked
    tail are surfaced.
    """

    provider: AiProvider
    # True when a (ciphertext) key is stored for this provider.
    has_key: bool = False
    # Last few characters of the key for operator recognition, e.g. "••••abcd".
    # ``None`` when no key is stored.
    key_masked: str | None = None
    model: str | None = None
    is_active: bool = False
    last_test_status: ConnectionTestStatus | None = None
    last_test_message: str | None = None
    last_tested_at: datetime | None = None
    updated_at: datetime | None = None


class AiSettingsOut(BaseModel):
    """Envelope for ``GET /admin/ai-settings`` — one entry per provider.

    The router always returns *both* providers (synthesising an empty,
    unconfigured row when a provider has never been saved) so the frontend can
    render a stable two-row panel without null-handling per provider.
    """

    providers: list[AiProviderConfigOut] = Field(default_factory=list)


class ConnectionTestOut(BaseModel):
    """Result of ``POST /admin/ai-settings/{provider}/test`` ("設定テスト")."""

    provider: AiProvider
    status: ConnectionTestStatus
    message: str
    tested_at: datetime | None = None


__all__ = [
    "AiProvider",
    "AiProviderConfigOut",
    "AiSettingsOut",
    "AiSettingsUpdateIn",
    "ConnectionTestOut",
    "ConnectionTestStatus",
]
