"""Integration tests for the admin "AI設定" panel (Issue #28).

Two layers are exercised here, each with a deliberately different DB-isolation
strategy (see ``tests/integration/conftest.py`` for why the shared engine has no
rollback):

* **Service / DB layer** — runs against a *fresh, function-scoped* SQLite engine
  (each :func:`create_test_engine` call yields its own ``:memory:`` database), so
  encrypt-at-rest persistence, ``upsert`` key semantics, ``get_view`` synthesis,
  the fail-closed ``get_active_provider_key`` gate, and the Claude dormancy probe
  are verified in complete isolation. A fixed Fernet makes encrypt/decrypt
  deterministic, and the Perplexity network path is exercised only via an
  injected ``httpx.MockTransport`` (never a real call).

* **HTTP / RBAC layer** — runs through the full ASGI stack with the shared
  ``client`` fixture. Because that engine persists across tests, every HTTP test
  sets its own precondition (the "no key" probe first PUTs ``api_key=""`` to
  clear). These assert the security boundary end-to-end: admin-only access, the
  decrypted key never crossing the API boundary (masked tail only), Claude
  reported as gracefully "unavailable", and an unknown provider rejected at the
  path-param layer (422) before any DB work.

SECURITY INVARIANTS asserted: plaintext keys never appear in any response; the
Perplexity probe payload carries no confidential text (only a fixed ``ping``);
an inactive/unconfigured provider yields no usable key (fail-closed).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import httpx
import pytest_asyncio
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import select

from app.models.app_settings import AiProviderSetting
from app.schemas.settings import AiSettingsUpdateIn
from app.services.settings_service import SettingsService

# One deterministic Fernet for the whole module run — keeps encrypt/decrypt
# stable across assertions while never persisting a plaintext key.
_TEST_FERNET = Fernet(Fernet.generate_key())

AI_SETTINGS = "/api/v1/admin/ai-settings"


def _update(
    *,
    api_key: str | None = None,
    model: str | None = None,
    is_active: bool = False,
) -> AiSettingsUpdateIn:
    """Build an update payload, wrapping a plaintext key in ``SecretStr``."""
    return AiSettingsUpdateIn(
        api_key=None if api_key is None else SecretStr(api_key),
        model=model,
        is_active=is_active,
    )


# ---------------------------------------------------------------------------
# Fresh, fully isolated engine for DB-direct service tests
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def fresh_session() -> AsyncGenerator[Any, None]:
    """A brand-new in-memory SQLite session, isolated from the shared engine.

    Each ``create_test_engine()`` call produces its own ``:memory:`` database,
    so service-layer tests can mutate ``ai_provider_settings`` freely without
    polluting (or being polluted by) the HTTP-layer tests on ``test_engine``.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.db.test_session import DEFAULT_SQLITE_URL, create_all_for_tests, create_test_engine

    # Always use SQLite :memory: for service-layer isolation, regardless of
    # PYTEST_USE_POSTGRES — PostgreSQL does not support :memory: databases,
    # and this fixture's isolation contract requires a fresh schema per test.
    engine = create_test_engine(DEFAULT_SQLITE_URL)
    await create_all_for_tests(engine)
    Session = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    session = Session()
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


# ===========================================================================
# Service / DB layer
# ===========================================================================


async def test_upsert_encrypts_at_rest_and_masks(fresh_session: Any) -> None:
    """upsert stores ciphertext (never plaintext) and returns a masked tail."""
    # Arrange
    service = SettingsService(fernet=_TEST_FERNET)
    secret = "pplx-live-abcd"

    # Act
    result = await service.upsert(
        fresh_session,
        "perplexity",
        _update(api_key=secret, model="sonar", is_active=True),
    )

    # Assert — masked read schema, no plaintext leaks out
    assert result.has_key is True
    assert result.key_masked == "••••abcd"
    assert result.model == "sonar"
    assert result.is_active is True
    assert result.last_test_status is None

    # Assert — the row holds Fernet ciphertext, not the plaintext key
    row = (
        await fresh_session.execute(
            select(AiProviderSetting).where(AiProviderSetting.provider == "perplexity")
        )
    ).scalar_one()
    assert row.api_key_encrypted is not None
    assert row.api_key_encrypted != secret
    assert service.decrypt(row.api_key_encrypted) == secret


async def test_upsert_key_semantics_none_preserves_empty_clears(
    fresh_session: Any,
) -> None:
    """api_key None leaves the key (and last_test); "" clears both."""
    # Arrange — seed a key, then stamp a prior test outcome onto the row
    service = SettingsService(fernet=_TEST_FERNET)
    await service.upsert(
        fresh_session, "perplexity", _update(api_key="pplx-seed-9999", is_active=True)
    )
    row = (
        await fresh_session.execute(
            select(AiProviderSetting).where(AiProviderSetting.provider == "perplexity")
        )
    ).scalar_one()
    row.last_test_status = "ok"
    row.last_test_message = "previously ok"
    await fresh_session.flush()

    # Act 1 — api_key None: key unchanged, prior test outcome preserved
    unchanged = await service.upsert(
        fresh_session,
        "perplexity",
        _update(api_key=None, model="sonar-pro", is_active=False),
    )

    # Assert 1
    assert unchanged.has_key is True
    assert unchanged.key_masked == "••••9999"
    assert unchanged.model == "sonar-pro"
    assert unchanged.is_active is False
    assert unchanged.last_test_status == "ok"  # not reset when key untouched

    # Act 2 — empty string: explicit clear, which invalidates the test outcome
    cleared = await service.upsert(
        fresh_session, "perplexity", _update(api_key="", is_active=False)
    )

    # Assert 2
    assert cleared.has_key is False
    assert cleared.key_masked is None
    assert cleared.last_test_status is None  # key change clears prior result


async def test_get_view_synthesises_both_providers_when_empty(
    fresh_session: Any,
) -> None:
    """An empty table still renders a stable two-provider panel."""
    # Arrange
    service = SettingsService(fernet=_TEST_FERNET)

    # Act
    view = await service.get_view(fresh_session)

    # Assert — exactly perplexity then claude, both keyless
    assert [p.provider for p in view.providers] == ["perplexity", "claude"]
    assert all(p.has_key is False for p in view.providers)
    assert all(p.key_masked is None for p in view.providers)


async def test_get_active_provider_key_is_fail_closed(fresh_session: Any) -> None:
    """No row / inactive ⇒ None; only an active+configured provider yields a key."""
    # Arrange
    service = SettingsService(fernet=_TEST_FERNET)

    # Assert — unconfigured provider: fail-closed
    assert await service.get_active_provider_key(fresh_session, "perplexity") is None

    # Act/Assert — configured but inactive: still fail-closed
    await service.upsert(
        fresh_session, "perplexity", _update(api_key="pplx-key-7", is_active=False)
    )
    assert await service.get_active_provider_key(fresh_session, "perplexity") is None

    # Act/Assert — active + configured: the plaintext key is released
    await service.upsert(fresh_session, "perplexity", _update(api_key="pplx-key-7", is_active=True))
    assert await service.get_active_provider_key(fresh_session, "perplexity") == "pplx-key-7"


async def test_claude_probe_is_dormant_and_persists(fresh_session: Any) -> None:
    """Before 2026-07-01 the Claude test is 'unavailable' — never an error."""
    # Arrange
    service = SettingsService(fernet=_TEST_FERNET)

    # Act 1 — no key yet: reported unavailable with a clear notice, no row to persist
    no_key = await service.test_connection(fresh_session, "claude")

    # Assert 1
    assert no_key.status == "unavailable"
    assert "2026-07-01" in no_key.message
    assert "キー未設定" in no_key.message

    # Act 2 — key saved, probe again: still unavailable, now persisted on the row
    await service.upsert(fresh_session, "claude", _update(api_key="sk-ant-xxxx", is_active=True))
    saved = await service.test_connection(fresh_session, "claude")

    # Assert 2 — outcome reflects saved key and is written back to last_test_*
    assert saved.status == "unavailable"
    assert "キーは保存済み" in saved.message
    view = await service.get_view(fresh_session)
    claude = next(p for p in view.providers if p.provider == "claude")
    assert claude.last_test_status == "unavailable"


async def test_perplexity_probe_via_injected_transport(fresh_session: Any) -> None:
    """The Perplexity probe sends only a fixed ping (no contract text); 200 ⇒ ok."""
    # Arrange — capture the outgoing request to assert the security boundary
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode("utf-8")
        captured["body"] = body
        captured["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"id": "ok"})

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = SettingsService(fernet=_TEST_FERNET, http_client=mock_client)
    await service.upsert(
        fresh_session, "perplexity", _update(api_key="pplx-probe-1", is_active=True)
    )

    # Act
    try:
        result = await service.test_connection(fresh_session, "perplexity")
    finally:
        await mock_client.aclose()  # injected client is caller-owned

    # Assert — outcome + security boundary (trivial ping, key in header only)
    assert result.status == "ok"
    assert "ping" in captured["body"]
    assert "契約" not in captured["body"]
    assert captured["auth"] == "Bearer pplx-probe-1"


async def test_perplexity_probe_maps_401_to_auth_failure(fresh_session: Any) -> None:
    """A 401 from Perplexity becomes a friendly auth-failure (not an exception)."""

    # Arrange
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = SettingsService(fernet=_TEST_FERNET, http_client=mock_client)
    await service.upsert(fresh_session, "perplexity", _update(api_key="pplx-bad", is_active=True))

    # Act
    try:
        result = await service.test_connection(fresh_session, "perplexity")
    finally:
        await mock_client.aclose()

    # Assert
    assert result.status == "failed"
    assert "認証" in result.message


# ===========================================================================
# HTTP / RBAC layer (full ASGI stack, shared engine)
# ===========================================================================


async def test_admin_get_returns_two_masked_providers(
    client: Any, auth_headers_admin: dict[str, str]
) -> None:
    """Admin GET succeeds and returns the stable two-provider shape."""
    # Act
    resp = await client.get(AI_SETTINGS, headers=auth_headers_admin)

    # Assert
    assert resp.status_code == 200
    providers = resp.json()["providers"]
    assert {p["provider"] for p in providers} == {"perplexity", "claude"}


async def test_admin_put_then_get_shows_masked_never_plaintext(
    client: Any, auth_headers_admin: dict[str, str]
) -> None:
    """Saving a key returns/echoes only the masked tail; plaintext never leaks."""
    # Arrange
    secret = "pplx-http-test-7777"

    # Act — save
    put = await client.put(
        f"{AI_SETTINGS}/perplexity",
        headers=auth_headers_admin,
        json={"api_key": secret, "model": "sonar", "is_active": True},
    )

    # Assert — write echoes masked view, body carries no plaintext
    assert put.status_code == 200
    saved = put.json()
    assert saved["has_key"] is True
    assert saved["key_masked"] == "••••7777"
    assert saved["model"] == "sonar"
    assert secret not in put.text

    # Act — read back
    get = await client.get(AI_SETTINGS, headers=auth_headers_admin)

    # Assert — masked on read too, full plaintext absent from the payload
    assert get.status_code == 200
    perplexity = next(p for p in get.json()["providers"] if p["provider"] == "perplexity")
    assert perplexity["has_key"] is True
    assert perplexity["key_masked"] == "••••7777"
    assert secret not in get.text


async def test_non_admin_get_is_forbidden(client: Any, auth_headers_site: dict[str, str]) -> None:
    """A site/drafter role may not read AI settings (admin-only)."""
    # Act
    resp = await client.get(AI_SETTINGS, headers=auth_headers_site)

    # Assert
    assert resp.status_code == 403


async def test_unauthenticated_get_is_unauthorized(client: Any) -> None:
    """No bearer token ⇒ 401."""
    # Act
    resp = await client.get(AI_SETTINGS)

    # Assert
    assert resp.status_code == 401


async def test_post_test_claude_reports_unavailable(
    client: Any, auth_headers_admin: dict[str, str]
) -> None:
    """The Claude connection test is gracefully 'unavailable' until the gate."""
    # Act
    resp = await client.post(f"{AI_SETTINGS}/claude/test", headers=auth_headers_admin)

    # Assert
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "unavailable"
    assert "2026-07-01" in body["message"]


async def test_post_test_perplexity_without_key_fails_without_network(
    client: Any, auth_headers_admin: dict[str, str]
) -> None:
    """Probing Perplexity with no stored key fails locally (no network call)."""
    # Arrange — clear any key a prior test may have stored (shared engine)
    clear = await client.put(
        f"{AI_SETTINGS}/perplexity",
        headers=auth_headers_admin,
        json={"api_key": "", "is_active": False},
    )
    assert clear.status_code == 200

    # Act
    resp = await client.post(f"{AI_SETTINGS}/perplexity/test", headers=auth_headers_admin)

    # Assert — "failed / 未設定" comes from the service before any HTTP call
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert "未設定" in body["message"]


async def test_unknown_provider_is_rejected_at_path_param(
    client: Any, auth_headers_admin: dict[str, str]
) -> None:
    """An out-of-vocabulary provider is a 422 (Literal path-param) before DB work."""
    # Act — admin headers so the 422 is unambiguously the provider, not auth
    resp = await client.post(f"{AI_SETTINGS}/openai/test", headers=auth_headers_admin)

    # Assert
    assert resp.status_code == 422
