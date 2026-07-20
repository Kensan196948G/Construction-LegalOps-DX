from __future__ import annotations

from typing import Any

import pytest


@pytest.mark.asyncio
async def test_access_only_mode_requires_valid_access_jwt(
    client: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SSO_MODE", "stub")
    monkeypatch.setenv("EDGE_AUTH_BOUNDARY", "cloudflare-access")

    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_access_only_mode_derives_real_email_and_jit_provisions_user(
    client: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import deps

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SSO_MODE", "stub")
    monkeypatch.setenv("EDGE_AUTH_BOUNDARY", "cloudflare-access")

    async def fake_verify_access_jwt(_token: str) -> dict[str, object]:
        return {
            "sub": "cf-access-subject",
            "email": "legal.user@example.com",
            "iss": "https://team.cloudflareaccess.com",
            "aud": "legalops-aud",
        }

    monkeypatch.setattr(deps, "verify_access_jwt", fake_verify_access_jwt)

    response = await client.get(
        "/api/v1/auth/me",
        headers={
            "Cf-Access-Jwt-Assertion": "valid-access-jwt",
            "Cf-Access-Authenticated-User-Email": "legal.user@example.com",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "l********r@example.com"
    assert body["role"] == "drafter"


@pytest.mark.asyncio
async def test_access_only_mode_rejects_header_email_mismatch(
    client: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import deps

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SSO_MODE", "stub")
    monkeypatch.setenv("EDGE_AUTH_BOUNDARY", "cloudflare-access")

    async def fake_verify_access_jwt(_token: str) -> dict[str, object]:
        return {"sub": "cf-access-subject", "email": "real.user@example.com"}

    monkeypatch.setattr(deps, "verify_access_jwt", fake_verify_access_jwt)

    response = await client.get(
        "/api/v1/auth/me",
        headers={
            "Cf-Access-Jwt-Assertion": "valid-access-jwt",
            "Cf-Access-Authenticated-User-Email": "spoofed.user@example.com",
        },
    )

    assert response.status_code == 401
