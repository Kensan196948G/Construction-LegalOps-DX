"""AI provider settings service — encrypt-at-rest + connection probe (Issue #28).

This service owns the **security boundary** for the admin "AI設定" panel. It is
the *only* place that turns a plaintext API key into ciphertext (and back), and
the *only* place that talks to a provider during a "設定テスト".

Design invariants
-----------------
* **Never plaintext at rest.** Provider keys are encrypted with Fernet before
  they touch the DB. The Fernet key comes from ``SETTINGS_ENCRYPTION_KEY`` when
  set; otherwise it is *derived deterministically* from ``jwt_secret`` (SHA-256
  → urlsafe-base64 of 32 bytes). There is no code path that writes a plaintext
  key, so a missing env var degrades to "still encrypted" rather than "leaked"
  (fail-closed). See :meth:`SettingsService._build_fernet`.
* **Read never returns plaintext.** :meth:`get_view` surfaces only a presence
  flag and a masked tail (``••••abcd``); the decrypted key never crosses the
  API boundary.
* **One live row per provider.** Writes go through ``upsert`` which respects the
  partial-unique index (``deleted_at IS NULL``); changing a key clears the
  previous ``last_test_*`` outcome so a stale "ok" can't mask a new bad key.
* **Claude is dormant until 2026-07-01.** A connection test for Claude returns
  ``status="unavailable"`` (never an error) until that date — graceful
  degradation while the production key is unavailable.
* **Testability without respx.** The HTTP client used for the Perplexity probe
  is injectable via the constructor (``http_client=``), mirroring the DI
  pattern in ``ai_review.py``. Tests pass an ``httpx.AsyncClient`` backed by a
  ``MockTransport`` instead of hitting the network.

NOTE: Confidential contract text is **never** sent during a connection test —
the Perplexity probe sends a trivial fixed ping payload only.
"""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import logging
from datetime import UTC, date, datetime
from typing import Final
from urllib.parse import urlsplit

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as app_settings
from app.models.app_settings import AiProviderSetting
from app.schemas.settings import (
    AiProvider,
    AiProviderConfigOut,
    AiSettingsOut,
    AiSettingsUpdateIn,
    ConnectionTestOut,
)

logger = logging.getLogger(__name__)

# Providers the panel always renders (a stable two-row UI), in display order.
_PROVIDERS: Final[tuple[AiProvider, ...]] = ("perplexity", "claude")

# Claude API key is unavailable until this date; tests return "unavailable".
_CLAUDE_AVAILABLE_FROM: Final[date] = date(2026, 7, 1)

# Number of trailing key characters revealed in the masked tail.
_MASK_VISIBLE: Final[int] = 4

# SSRF guard: the Perplexity probe carries a Bearer key, so it may only ever be
# sent to an explicitly trusted host over TLS. ``perplexity_base_url`` is an
# operator-configurable setting, so we pin the destination here rather than
# trusting config blindly — an attacker who could flip the base URL must not be
# able to exfiltrate the key to an arbitrary / internal endpoint.
_PERPLEXITY_ALLOWED_HOSTS: Final[frozenset[str]] = frozenset({"api.perplexity.ai"})


def _utcnow() -> datetime:
    """Timezone-aware UTC now (kept tiny so tests can monkeypatch it)."""
    return datetime.now(UTC)


def _today() -> date:
    """Current date (separated so the Claude gate is monkeypatchable in tests)."""
    return _utcnow().date()


class SettingsService:
    """Encrypt/decrypt provider keys and run connection probes.

    Construct once per request (cheap) or reuse a module-level singleton. The
    optional injected ``http_client`` is **not** closed by this service when the
    caller owns it; the service only closes clients it creates itself.
    """

    def __init__(
        self,
        *,
        fernet: Fernet | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._fernet = fernet or self._build_fernet()
        # Caller-owned client (e.g. a test MockTransport client). When None, the
        # Perplexity probe creates and closes a short-lived client per call.
        self._http_client = http_client

    # ------------------------------------------------------------------ #
    # Fernet key management (fail-closed: never plaintext at rest)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _derive_fernet_key(material: str) -> bytes:
        """Derive a valid Fernet key (urlsafe-base64 of 32 bytes) from a secret.

        Fernet requires a 32-byte urlsafe-base64 key. We hash the input material
        with SHA-256 (always 32 bytes) and base64-encode it, so any secret of
        any length yields a *valid, deterministic* key.
        """
        digest = hashlib.sha256(material.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)

    @classmethod
    def _build_fernet(cls) -> Fernet:
        """Build the Fernet engine, preferring an explicit key, else derived.

        Order of precedence:
        1. ``SETTINGS_ENCRYPTION_KEY`` used *as-is* if it is already a valid
           Fernet key (operator supplied a real key).
        2. ``SETTINGS_ENCRYPTION_KEY`` *derived* if it is set but not a valid
           Fernet key (operator supplied an arbitrary passphrase).
        3. Derived from ``jwt_secret`` when no encryption key is configured.

        In every branch the result is a usable Fernet, so secrets are always
        encrypted at rest — there is no plaintext fallback.
        """
        explicit = app_settings.settings_encryption_key
        if explicit is not None:
            raw = explicit.get_secret_value().strip()
            if raw:
                try:
                    # Accept a ready-made Fernet key verbatim.
                    return Fernet(raw.encode("utf-8"))
                except (ValueError, TypeError):
                    # Arbitrary passphrase → derive a valid key from it.
                    return Fernet(cls._derive_fernet_key(raw))

        # Fail-closed default: derive from the JWT secret so data is still
        # encrypted even when no dedicated encryption key is provisioned.
        material = app_settings.jwt_secret.get_secret_value()
        return Fernet(cls._derive_fernet_key(material))

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext API key into a storable ciphertext string."""
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a stored ciphertext back to the plaintext API key.

        Raises :class:`cryptography.fernet.InvalidToken` on tamper / wrong key;
        callers that surface masked views catch this and degrade gracefully.
        """
        return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")

    # ------------------------------------------------------------------ #
    # Masking helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _mask_tail(plaintext: str, *, visible: int = _MASK_VISIBLE) -> str:
        """Return a masked representation revealing only the trailing chars.

        ``"pplx-1234abcd"`` → ``"••••abcd"``. Short keys reveal nothing.
        """
        tail = plaintext[-visible:] if len(plaintext) > visible else ""
        return f"••••{tail}"

    # ------------------------------------------------------------------ #
    # Read path
    # ------------------------------------------------------------------ #
    async def _get_row(
        self, session: AsyncSession, provider: AiProvider
    ) -> AiProviderSetting | None:
        """Fetch the single live (non-deleted) row for a provider, if any."""
        stmt = select(AiProviderSetting).where(
            AiProviderSetting.provider == provider,
            AiProviderSetting.deleted_at.is_(None),
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    def _to_config_out(
        self, row: AiProviderSetting | None, provider: AiProvider
    ) -> AiProviderConfigOut:
        """Map a row (or absence) to the masked read schema.

        Decryption failures (tampered ciphertext / rotated key) are treated as
        "no usable key" rather than raising — the panel still renders and the
        operator can re-enter the key.
        """
        if row is None:
            return AiProviderConfigOut(provider=provider)

        has_key = False
        key_masked: str | None = None
        if row.api_key_encrypted:
            try:
                plaintext = self.decrypt(row.api_key_encrypted)
                has_key = True
                key_masked = self._mask_tail(plaintext)
            except InvalidToken:
                logger.warning(
                    "ai-settings: undecryptable key for provider=%s (key rotated?)",
                    provider,
                )
                has_key = False
                key_masked = None

        return AiProviderConfigOut(
            provider=provider,
            has_key=has_key,
            key_masked=key_masked,
            model=row.model,
            is_active=row.is_active,
            last_test_status=row.last_test_status,  # type: ignore[arg-type]
            last_test_message=row.last_test_message,
            last_tested_at=row.last_tested_at,
            updated_at=row.updated_at,
        )

    async def get_view(self, session: AsyncSession) -> AiSettingsOut:
        """Return both providers as masked config rows (synthesising empties)."""
        providers: list[AiProviderConfigOut] = []
        for provider in _PROVIDERS:
            row = await self._get_row(session, provider)
            providers.append(self._to_config_out(row, provider))
        return AiSettingsOut(providers=providers)

    # ------------------------------------------------------------------ #
    # Write path
    # ------------------------------------------------------------------ #
    async def upsert(
        self,
        session: AsyncSession,
        provider: AiProvider,
        data: AiSettingsUpdateIn,
    ) -> AiProviderConfigOut:
        """Create or update the live row for ``provider`` ("保存・設定").

        Field/key semantics are applied by :meth:`_apply_update`. A concurrent
        first-create (two requests racing to insert the provider's first row) is
        resolved by catching :class:`IntegrityError`, re-fetching the winner's
        row, and re-applying this request on top — last writer wins, never a 500.
        """
        row = await self._get_row(session, provider)
        created = row is None
        if row is None:
            row = AiProviderSetting(provider=provider)
            session.add(row)

        self._apply_update(row, data)

        try:
            await session.flush()
        except IntegrityError:
            # Concurrent first-create: another request inserted the live row for
            # this provider between our SELECT and INSERT. The partial-unique
            # index (``deleted_at IS NULL``) rejects the duplicate. Roll back the
            # failed INSERT, re-fetch the row the winner created, and re-apply our
            # update on top of it — last writer wins instead of a 500.
            if not created:
                raise
            await session.rollback()
            row = await self._get_row(session, provider)
            if row is None:
                # The winning row vanished (deleted) before we could read it back.
                # Fall back to a fresh insert of our own values.
                row = AiProviderSetting(provider=provider)
                session.add(row)
            self._apply_update(row, data)
            await session.flush()

        await session.refresh(row)
        return self._to_config_out(row, provider)

    def _apply_update(self, row: AiProviderSetting, data: AiSettingsUpdateIn) -> None:
        """Apply request fields onto a row (shared by create / retry paths).

        Key semantics (``data.api_key``):
        * ``None``        → leave the stored key unchanged.
        * empty string    → clear the stored key.
        * any other value → encrypt and store; clears ``last_test_*`` because a
          new key invalidates the previous probe outcome.
        """
        # Model + activation are always applied from the request.
        row.model = data.model
        row.is_active = data.is_active

        if data.api_key is not None:
            new_plain = data.api_key.get_secret_value()
            if new_plain == "":
                # Explicit clear.
                row.api_key_encrypted = None
            else:
                row.api_key_encrypted = self.encrypt(new_plain)
            # A key change (set or clear) invalidates any prior test result.
            row.last_test_status = None
            row.last_test_message = None
            row.last_tested_at = None

    # ------------------------------------------------------------------ #
    # Connection probe ("設定テスト")
    # ------------------------------------------------------------------ #
    async def test_connection(
        self, session: AsyncSession, provider: AiProvider
    ) -> ConnectionTestOut:
        """Probe the provider with the stored key and persist the outcome.

        Returns a structured result (never raises for an expected provider
        condition). The probe sends **no confidential text** — only a trivial
        fixed ping. The outcome is written back to ``last_test_*`` so the panel
        reflects the most recent check.
        """
        row = await self._get_row(session, provider)
        tested_at = _utcnow()

        status: str
        message: str

        if provider == "claude":
            status, message = self._probe_claude(row)
        else:
            api_key = self._row_plaintext_key(row)
            if api_key is None:
                status, message = "failed", "APIキーが未設定です。先に保存してください。"
            else:
                status, message = await self._probe_perplexity(api_key)

        # Persist outcome (best-effort — a missing row means nothing to update,
        # but we still return the live result to the caller).
        if row is not None:
            row.last_test_status = status
            row.last_test_message = message
            row.last_tested_at = tested_at
            await session.flush()

        return ConnectionTestOut(
            provider=provider,
            status=status,  # type: ignore[arg-type]
            message=message,
            tested_at=tested_at,
        )

    def _row_plaintext_key(self, row: AiProviderSetting | None) -> str | None:
        """Decrypt a row's stored key, or None when absent/undecryptable."""
        if row is None or not row.api_key_encrypted:
            return None
        try:
            return self.decrypt(row.api_key_encrypted)
        except InvalidToken:
            logger.warning("ai-settings: cannot decrypt key during probe")
            return None

    def _probe_claude(self, row: AiProviderSetting | None) -> tuple[str, str]:
        """Claude probe — dormant until 2026-07-01 (graceful 'unavailable').

        Before the gate we never call the network: we report the key as saved
        (if present) but the provider as intentionally unavailable, so the panel
        can show a clear "7月1日まで利用不可" notice without an error state.
        """
        if _today() < _CLAUDE_AVAILABLE_FROM:
            saved = row is not None and bool(row.api_key_encrypted)
            note = "キーは保存済み。" if saved else "キー未設定。"
            return (
                "unavailable",
                f"{note}Claude API は 2026-07-01 まで利用できません（設定のみ保存可能）。",
            )
        # Post-gate: a real validation would go here. Until the key is available
        # we cannot exercise this path, so it is excluded from coverage.
        api_key = self._row_plaintext_key(row)  # pragma: no cover
        if api_key is None:  # pragma: no cover
            return "failed", "APIキーが未設定です。先に保存してください。"
        if not api_key.startswith("sk-ant-"):  # pragma: no cover
            return "failed", "APIキーの形式が不正です（'sk-ant-' で始まる必要があります）。"
        return "ok", "Claude API キー形式を確認しました。"  # pragma: no cover

    @staticmethod
    def _validate_probe_url(url: str) -> str | None:
        """Return None if ``url`` is a safe probe target, else a reason string.

        SSRF guard for the Bearer-carrying probe. Rejects anything that is not
        HTTPS to an allowlisted host. A literal-IP host is additionally refused
        if it resolves to a private / loopback / link-local / reserved range, so
        a hostile config can't redirect the key to an internal address.
        """
        parts = urlsplit(url)
        if parts.scheme != "https":
            return f"scheme not allowed: {parts.scheme!r}"
        host = parts.hostname
        if not host:
            return "missing host"
        host = host.lower()
        if host not in _PERPLEXITY_ALLOWED_HOSTS:
            return f"host not in allowlist: {host!r}"
        # Defense in depth: if the allowlisted name were ever an IP literal,
        # make sure it is not an internal address.
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            ip = None
        if ip is not None and (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return f"host resolves to non-routable address: {host!r}"
        return None

    async def _probe_perplexity(self, api_key: str) -> tuple[str, str]:
        """Live Perplexity auth probe (no confidential text sent).

        Sends a minimal fixed chat-completion request. Interprets the HTTP
        status into our vocabulary:
        * 200            → ok
        * 401 / 403      → failed (auth)
        * 429            → failed (rate limited; key likely valid)
        * other status   → failed (with code)
        * transport err  → failed (network)

        Before sending, the destination URL is validated against an allowlist
        (HTTPS + trusted host, no private/loopback target) so a misconfigured or
        attacker-controlled ``perplexity_base_url`` cannot exfiltrate the Bearer
        key to an arbitrary endpoint (SSRF defense).
        """
        url = f"{app_settings.perplexity_base_url.rstrip('/')}/chat/completions"
        guard_error = self._validate_probe_url(url)
        if guard_error is not None:
            logger.warning("perplexity probe blocked: %s (url=%s)", guard_error, url)
            return "failed", "接続先設定が不正です（許可されたエンドポイントではありません）。"
        payload = {
            "model": app_settings.perplexity_model,
            # Trivial ping — intentionally carries NO contract content.
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Reuse an injected client (tests) or create+own a short-lived one.
        owns_client = self._http_client is None
        client = self._http_client or httpx.AsyncClient(
            timeout=app_settings.perplexity_timeout_seconds
        )
        try:
            response = await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            logger.info("perplexity probe transport error: %s", exc)
            return "failed", f"接続エラー: {type(exc).__name__}"
        finally:
            if owns_client:
                await client.aclose()

        code = response.status_code
        if code == 200:
            return "ok", "Perplexity API へ正常に接続できました。"
        if code in (401, 403):
            return "failed", "認証に失敗しました（APIキーを確認してください）。"
        if code == 429:
            return "failed", "レート制限に達しました（キーは有効な可能性があります）。"
        return "failed", f"接続に失敗しました（HTTP {code}）。"

    # ------------------------------------------------------------------ #
    # Orchestrator hook
    # ------------------------------------------------------------------ #
    async def get_active_provider_key(
        self, session: AsyncSession, provider: AiProvider
    ) -> str | None:
        """Return the plaintext key for an *active* provider, else None.

        Used by the AI orchestrator to decide whether a provider's agent can
        run. Returns None when the provider is inactive, unconfigured, or its
        stored key cannot be decrypted (fail-closed: no key ⇒ agent stays off).

        The Claude dormancy gate is enforced **here too**, not only in the probe:
        even if an operator saves and activates a Claude key early, no execution
        path may release that key before 2026-07-01. Applying the gate at the key
        handoff keeps the "no Claude network call before the gate" invariant true
        regardless of which caller reaches for the key.
        """
        if provider == "claude" and _today() < _CLAUDE_AVAILABLE_FROM:
            return None
        row = await self._get_row(session, provider)
        if row is None or not row.is_active:
            return None
        return self._row_plaintext_key(row)


# Module-level singleton for the common case (router dependency).
settings_service = SettingsService()


__all__ = ["SettingsService", "settings_service"]
