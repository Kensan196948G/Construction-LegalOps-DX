"""Unit tests for ``app.services.settings_service`` — pure-logic / no real DB.

This file is the **security-boundary** test suite for the admin "AI設定" panel
(Issue #28). It deliberately exercises only the methods that need no live
``AsyncSession`` (crypto, masking, Fernet-key derivation, the Claude dormancy
gate, the Perplexity probe via an injected ``MockTransport`` client, and the
``_to_config_out`` mapping over *transient* ORM rows). DB-session behaviour
(``upsert`` / ``get_view`` / ``get_active_provider_key`` / persistence) lives in
``tests/integration/test_ai_settings.py`` where the table is actually created.

Why no respx? ``SettingsService`` accepts an ``http_client=`` constructor seam,
so we inject ``httpx.AsyncClient(transport=httpx.MockTransport(handler))`` and
never touch the network. The Fernet engine is likewise injectable, keeping these
tests independent of ``app.core.config``.

Coverage focus
--------------
* ``_derive_fernet_key`` — determinism, validity, input-sensitivity.
* ``encrypt`` / ``decrypt`` — roundtrip, non-deterministic ciphertext,
  ``InvalidToken`` on tamper / wrong key.
* ``_mask_tail`` — tail reveal + short-key masking.
* ``_build_fernet`` — precedence (explicit valid key / passphrase derive /
  jwt derive / blank → jwt).
* ``_probe_claude`` — "unavailable" before the 2026-07-01 gate (saved + unsaved).
* ``_to_config_out`` — None row / valid masked key / undecryptable degrade.
* ``_row_plaintext_key`` — None / no-ciphertext / valid / bad.
* ``_probe_perplexity`` — 200/401/403/429/other/transport-error mapping
  **and the security guard** (only a fixed "ping" + Bearer header is sent).
"""

from __future__ import annotations

import json
from datetime import date

import httpx
import pytest
from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr

from app.models.app_settings import AiProviderSetting
from app.schemas.settings import AiSettingsUpdateIn  # noqa: F401  (kept for parity/docs)
from app.services import settings_service as settings_service_module
from app.services.settings_service import SettingsService

# A fixed, deterministic Fernet engine for tests — built from a pure staticmethod
# so it touches no config. Reused everywhere a real DB row would be encrypted.
_FIXED_FERNET = Fernet(SettingsService._derive_fernet_key("unit-test-fixed-material"))


def _svc(
    *,
    fernet: Fernet | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> SettingsService:
    """Build a service with the fixed Fernet by default (no config access)."""
    return SettingsService(fernet=fernet or _FIXED_FERNET, http_client=http_client)


# ===========================================================================
# _derive_fernet_key — determinism / validity / input-sensitivity
# ===========================================================================


def test_derive_fernet_key_is_deterministic() -> None:
    """Same material → byte-identical key (so encrypt/decrypt survive restarts)."""
    a = SettingsService._derive_fernet_key("same-secret")
    b = SettingsService._derive_fernet_key("same-secret")
    assert a == b


def test_derive_fernet_key_is_a_valid_fernet_key() -> None:
    """Any input yields a key Fernet accepts (urlsafe-base64 of 32 bytes)."""
    key = SettingsService._derive_fernet_key("anything-at-all")
    # Constructing Fernet validates length/encoding; no exception == valid.
    engine = Fernet(key)
    token = engine.encrypt(b"x")
    assert engine.decrypt(token) == b"x"


def test_derive_fernet_key_is_input_sensitive() -> None:
    """Different material → different key (no accidental collision)."""
    a = SettingsService._derive_fernet_key("secret-one")
    b = SettingsService._derive_fernet_key("secret-two")
    assert a != b


# ===========================================================================
# encrypt / decrypt — roundtrip, non-determinism, tamper rejection
# ===========================================================================


def test_encrypt_decrypt_roundtrip() -> None:
    """decrypt(encrypt(x)) == x for a realistic API-key string."""
    svc = _svc()
    plaintext = "pplx-1234567890abcdef"
    assert svc.decrypt(svc.encrypt(plaintext)) == plaintext


def test_encrypt_is_non_deterministic_but_roundtrips() -> None:
    """Fernet embeds an IV+timestamp, so two ciphertexts differ yet both decrypt."""
    svc = _svc()
    plaintext = "pplx-same-input"
    c1 = svc.encrypt(plaintext)
    c2 = svc.encrypt(plaintext)
    assert c1 != c2  # non-deterministic ciphertext
    assert svc.decrypt(c1) == plaintext
    assert svc.decrypt(c2) == plaintext


def test_decrypt_rejects_garbage() -> None:
    """A non-token string raises InvalidToken (callers degrade, never crash)."""
    svc = _svc()
    with pytest.raises(InvalidToken):
        svc.decrypt("not-a-valid-fernet-token")


def test_decrypt_rejects_wrong_key() -> None:
    """Ciphertext from a different key fails — proves key isolation / fail-closed."""
    svc = _svc()
    foreign = Fernet(Fernet.generate_key())
    foreign_token = foreign.encrypt(b"secret").decode("ascii")
    with pytest.raises(InvalidToken):
        svc.decrypt(foreign_token)


# ===========================================================================
# _mask_tail — reveal trailing chars only
# ===========================================================================


@pytest.mark.parametrize(
    ("plaintext", "expected"),
    [
        ("pplx-1234abcd", "••••abcd"),  # long key → last 4 revealed
        ("abcde", "••••bcde"),  # len 5 (>4) → last 4
        ("abcd", "••••"),  # len 4 (not >4) → nothing revealed
        ("abc", "••••"),  # short key → nothing revealed
        ("", "••••"),  # empty → nothing revealed
    ],
)
def test_mask_tail(plaintext: str, expected: str) -> None:
    """Only the trailing _MASK_VISIBLE chars of a *long* key are ever shown."""
    assert SettingsService._mask_tail(plaintext) == expected


# ===========================================================================
# _build_fernet — precedence (fail-closed: always encrypts)
# ===========================================================================


def _set_config(monkeypatch: pytest.MonkeyPatch, *, enc_key, jwt_secret) -> None:
    """Monkeypatch the two config fields _build_fernet reads."""
    monkeypatch.setattr(settings_service_module.app_settings, "settings_encryption_key", enc_key)
    monkeypatch.setattr(settings_service_module.app_settings, "jwt_secret", jwt_secret)


def _decrypts_for(fernet: Fernet, expected: Fernet) -> bool:
    """True iff a token from `expected` decrypts under `fernet` (same key)."""
    token = expected.encrypt(b"probe")
    try:
        return fernet.decrypt(token) == b"probe"
    except InvalidToken:
        return False


def test_build_fernet_uses_explicit_valid_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ready-made Fernet key is used verbatim (operator supplied a real key)."""
    raw_key = Fernet.generate_key()  # bytes, a valid Fernet key
    _set_config(
        monkeypatch,
        enc_key=SecretStr(raw_key.decode("ascii")),
        jwt_secret=SecretStr("unused-jwt"),
    )
    fernet = SettingsService._build_fernet()
    assert _decrypts_for(fernet, Fernet(raw_key))


def test_build_fernet_derives_from_passphrase(monkeypatch: pytest.MonkeyPatch) -> None:
    """An arbitrary (non-Fernet) passphrase is derived into a valid key."""
    _set_config(
        monkeypatch,
        enc_key=SecretStr("just-a-human-passphrase"),
        jwt_secret=SecretStr("unused-jwt"),
    )
    fernet = SettingsService._build_fernet()
    expected = Fernet(SettingsService._derive_fernet_key("just-a-human-passphrase"))
    assert _decrypts_for(fernet, expected)


def test_build_fernet_derives_from_jwt_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No encryption key configured → derive from jwt_secret (still encrypted)."""
    _set_config(monkeypatch, enc_key=None, jwt_secret=SecretStr("jwt-material-A"))
    fernet = SettingsService._build_fernet()
    expected = Fernet(SettingsService._derive_fernet_key("jwt-material-A"))
    assert _decrypts_for(fernet, expected)


def test_build_fernet_blank_key_falls_back_to_jwt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A whitespace-only key is treated as unset → jwt derivation (fail-closed)."""
    _set_config(monkeypatch, enc_key=SecretStr("   "), jwt_secret=SecretStr("jwt-material-B"))
    fernet = SettingsService._build_fernet()
    expected = Fernet(SettingsService._derive_fernet_key("jwt-material-B"))
    assert _decrypts_for(fernet, expected)


# ===========================================================================
# _probe_claude — dormant until 2026-07-01 (graceful "unavailable")
# ===========================================================================


def test_probe_claude_unavailable_before_gate_with_saved_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Before the gate: status 'unavailable', note acknowledges the saved key."""
    monkeypatch.setattr(settings_service_module, "_today", lambda: date(2026, 6, 4))
    svc = _svc()
    row = AiProviderSetting(
        provider="claude",
        api_key_encrypted=svc.encrypt("sk-ant-saved"),
        is_active=False,
    )
    status, message = svc._probe_claude(row)
    assert status == "unavailable"
    assert "キーは保存済み。" in message
    assert "2026-07-01" in message


def test_probe_claude_unavailable_before_gate_without_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Before the gate with no row: 'unavailable' + 'キー未設定。' note (no network)."""
    monkeypatch.setattr(settings_service_module, "_today", lambda: date(2026, 6, 4))
    svc = _svc()
    status, message = svc._probe_claude(None)
    assert status == "unavailable"
    assert "キー未設定。" in message
    assert "2026-07-01" in message


# ===========================================================================
# _to_config_out — masked read mapping over transient rows
# ===========================================================================


def test_to_config_out_none_row_is_empty_config() -> None:
    """Absent row → has_key False, no mask, all optionals None (stable UI row)."""
    svc = _svc()
    out = svc._to_config_out(None, "perplexity")
    assert out.provider == "perplexity"
    assert out.has_key is False
    assert out.key_masked is None
    assert out.is_active is False
    assert out.model is None


def test_to_config_out_valid_key_is_masked() -> None:
    """A decryptable key surfaces has_key=True + masked tail, never plaintext."""
    svc = _svc()
    row = AiProviderSetting(
        provider="perplexity",
        api_key_encrypted=svc.encrypt("pplx-secret-wxyz"),
        model="sonar",
        is_active=True,
    )
    out = svc._to_config_out(row, "perplexity")
    assert out.has_key is True
    assert out.key_masked == "••••wxyz"
    assert out.is_active is True
    assert out.model == "sonar"
    # Plaintext must never leak into the read schema.
    assert "pplx-secret-wxyz" not in (out.key_masked or "")


def test_to_config_out_undecryptable_key_degrades() -> None:
    """Tampered / wrong-key ciphertext degrades to 'no usable key' (no raise)."""
    svc = _svc()
    row = AiProviderSetting(
        provider="perplexity",
        api_key_encrypted="totally-not-a-fernet-token",
        is_active=False,
    )
    out = svc._to_config_out(row, "perplexity")
    assert out.has_key is False
    assert out.key_masked is None


# ===========================================================================
# _row_plaintext_key — internal decrypt helper (fail-closed)
# ===========================================================================


def test_row_plaintext_key_none_row() -> None:
    svc = _svc()
    assert svc._row_plaintext_key(None) is None


def test_row_plaintext_key_no_ciphertext() -> None:
    svc = _svc()
    row = AiProviderSetting(provider="perplexity", api_key_encrypted=None, is_active=False)
    assert svc._row_plaintext_key(row) is None


def test_row_plaintext_key_valid() -> None:
    svc = _svc()
    row = AiProviderSetting(
        provider="perplexity",
        api_key_encrypted=svc.encrypt("pplx-roundtrip"),
        is_active=True,
    )
    assert svc._row_plaintext_key(row) == "pplx-roundtrip"


def test_row_plaintext_key_bad_ciphertext() -> None:
    svc = _svc()
    row = AiProviderSetting(provider="perplexity", api_key_encrypted="garbage", is_active=True)
    assert svc._row_plaintext_key(row) is None


# ===========================================================================
# _probe_perplexity — HTTP mapping + security guard (no confidential text)
# ===========================================================================

_PROBE_KEY = "pplx-probe-secret-key"


async def _run_probe(
    handler, *, api_key: str = _PROBE_KEY, model: str | None = None
) -> tuple[str, str]:
    """Run the Perplexity probe against a MockTransport handler (no network)."""
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        svc = _svc(http_client=client)
        return await svc._probe_perplexity(api_key, model)


@pytest.mark.asyncio
async def test_probe_perplexity_200_ok() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    status, message = await _run_probe(handler)
    assert status == "ok"
    assert "正常に接続" in message


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [401, 403])
async def test_probe_perplexity_auth_failure(code: int) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(code, json={"error": "unauthorized"})

    status, message = await _run_probe(handler)
    assert status == "failed"
    assert "認証に失敗" in message


@pytest.mark.asyncio
async def test_probe_perplexity_rate_limited() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate"})

    status, message = await _run_probe(handler)
    assert status == "failed"
    assert "レート制限" in message


@pytest.mark.asyncio
async def test_probe_perplexity_other_status_includes_code() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    status, message = await _run_probe(handler)
    assert status == "failed"
    assert "HTTP 500" in message


@pytest.mark.asyncio
async def test_probe_perplexity_transport_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    status, message = await _run_probe(handler)
    assert status == "failed"
    # Surfaces the transport exception type, not a stack trace.
    assert "接続エラー" in message
    assert "ConnectError" in message


@pytest.mark.asyncio
async def test_probe_perplexity_sends_only_ping_and_bearer() -> None:
    """SECURITY: the probe must send a trivial ping + Bearer auth — nothing else.

    Guards the invariant that **no confidential contract text** is ever sent to
    Perplexity during a connection test. We capture the outgoing request and
    assert its exact shape outside the handler.
    """
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        captured["content_type"] = request.headers.get("Content-Type")
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"choices": []})

    status, _message = await _run_probe(handler)

    assert status == "ok"
    # Auth uses the supplied key as a Bearer token.
    assert captured["auth"] == f"Bearer {_PROBE_KEY}"
    assert captured["content_type"] == "application/json"
    # Endpoint is the chat-completions path.
    assert str(captured["url"]).endswith("/chat/completions")
    # Body is the fixed trivial ping — exactly one user message saying "ping".
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["messages"] == [{"role": "user", "content": "ping"}]
    assert body["max_tokens"] == 1
    # Defence-in-depth: the serialized body must not carry anything but "ping".
    serialized = json.dumps(body, ensure_ascii=False)
    assert "ping" in serialized
    assert "契約" not in serialized


@pytest.mark.asyncio
async def test_probe_perplexity_uses_saved_model() -> None:
    """REGRESSION (Codex P2 #1): the probe must send the row's saved model.

    When an operator saves a non-default model, the connection test has to
    validate *that* configuration — not the global default. Otherwise the UI
    could report a successful '設定テスト' for a model the saved key was never
    checked against.
    """
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"choices": []})

    status, _message = await _run_probe(handler, model="sonar-pro")

    assert status == "ok"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["model"] == "sonar-pro"


@pytest.mark.asyncio
async def test_probe_perplexity_falls_back_to_default_model() -> None:
    """When no per-row model is saved, the probe falls back to the global default."""
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"choices": []})

    status, _message = await _run_probe(handler, model=None)

    assert status == "ok"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["model"] == settings_service_module.app_settings.perplexity_model


# ===========================================================================
# _validate_probe_url — SSRF allowlist (static / pure, no network)
# ===========================================================================
#
# Regression tests for Codex adversarial-review finding [P2 SSRF]. The probe
# carries a Bearer key, so its destination must be pinned to an HTTPS
# allowlisted host. These assert the pure decision function directly: it is the
# single chokepoint _probe_perplexity consults before sending anything.


def test_validate_probe_url_allows_pinned_https_host() -> None:
    """The canonical Perplexity endpoint is accepted (returns None = no reason)."""
    assert SettingsService._validate_probe_url("https://api.perplexity.ai/chat/completions") is None


def test_validate_probe_url_rejects_non_https_scheme() -> None:
    """Plain HTTP would expose the Bearer key in cleartext — must be refused."""
    reason = SettingsService._validate_probe_url("http://api.perplexity.ai/chat/completions")
    assert reason is not None
    assert "scheme not allowed" in reason


def test_validate_probe_url_rejects_off_allowlist_host() -> None:
    """An attacker-flipped base URL pointing elsewhere must not receive the key."""
    reason = SettingsService._validate_probe_url("https://evil.example.com/chat/completions")
    assert reason is not None
    assert "host not in allowlist" in reason


def test_validate_probe_url_rejects_missing_host() -> None:
    """A schemeful but hostless URL (empty netloc) is rejected, not crashed on."""
    reason = SettingsService._validate_probe_url("https:///chat/completions")
    assert reason is not None
    assert "missing host" in reason


# ===========================================================================
# _probe_perplexity — SSRF guard short-circuits BEFORE any network send
# ===========================================================================


@pytest.mark.asyncio
async def test_probe_perplexity_blocks_off_allowlist_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SECURITY: a hostile ``perplexity_base_url`` must never see the Bearer key.

    We point the configured base URL at an attacker-controlled host and assert
    the probe fails *without invoking the transport at all* — the handler would
    record any outgoing request, and we require it stays empty. This proves the
    guard runs before the POST, so the key cannot be exfiltrated (SSRF defense).
    """
    monkeypatch.setattr(
        settings_service_module.app_settings,
        "perplexity_base_url",
        "https://evil.example.com",
    )

    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - must not run
        calls.append(str(request.url))
        return httpx.Response(200, json={"choices": []})

    status, message = await _run_probe(handler)

    assert status == "failed"
    assert "許可されたエンドポイント" in message
    # The key never left the process: the transport handler was not reached.
    assert calls == []


# ===========================================================================
# get_active_provider_key — Claude dormancy gate on the *execution* path
# ===========================================================================


@pytest.mark.asyncio
async def test_get_active_provider_key_claude_gated_before_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression for Codex [P1]: the dormancy gate guards key handoff too.

    Before 2026-07-01 the orchestrator key path must return None for Claude
    *without touching the session*. We pass ``session=None`` deliberately: if the
    gate failed to short-circuit, ``_get_row`` would call ``None.execute(...)`` and
    raise — so a clean None return proves both the gate AND the no-DB-access
    invariant in one shot.
    """
    monkeypatch.setattr(settings_service_module, "_today", lambda: date(2026, 6, 4))

    key = await _svc().get_active_provider_key(None, "claude")  # type: ignore[arg-type]

    assert key is None


@pytest.mark.asyncio
async def test_get_active_provider_key_perplexity_not_gated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The dormancy gate is Claude-only: Perplexity must reach the DB lookup.

    With ``session=None`` the Perplexity path is expected to proceed past the
    gate and hit ``_get_row``, which then fails on the None session. Catching that
    proves the gate did NOT swallow Perplexity (a too-broad gate would wrongly
    return None here instead of attempting the lookup).
    """
    monkeypatch.setattr(settings_service_module, "_today", lambda: date(2026, 6, 4))

    with pytest.raises(AttributeError):
        await _svc().get_active_provider_key(None, "perplexity")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_probe_deepseek_without_key_is_failed_not_error() -> None:
    """DeepSeek probe without a stored key reports 'failed' (never raises)."""
    row = AiProviderSetting(provider="deepseek", api_key_encrypted=None, is_active=True)
    status, message = await _svc()._probe_deepseek(row)
    assert status == "failed"
    assert "未設定" in message


@pytest.mark.asyncio
async def test_probe_deepseek_auth_failure_maps_to_failed() -> None:
    """DeepSeek probe maps 401 to 'failed' without leaking the request body."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert "Authorization" in request.headers
        assert request.url.host == "api.deepseek.com"
        return httpx.Response(401, json={"error": "unauthorized"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        svc = _svc(http_client=client)
        row = AiProviderSetting(
            provider="deepseek",
            api_key_encrypted=svc.encrypt(_PROBE_KEY),
            is_active=True,
            model="deepseek-chat",
        )
        status, message = await svc._probe_deepseek(row)
    assert status == "failed"
    assert "認証に失敗" in message
