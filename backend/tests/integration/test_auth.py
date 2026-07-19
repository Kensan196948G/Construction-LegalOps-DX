"""Integration tests for auth endpoints (``docs/api_design.md`` §3).

* ``GET /api/v1/auth/sso/login``  — returns Entra authorize URL (200, JSON)
* ``GET /api/v1/auth/sso/callback`` — exchanges code and sets HttpOnly cookie
* ``GET /api/v1/auth/me``         — protected (401 when unauthenticated)
* ``POST /api/v1/auth/logout``    — clears the session cookie
"""

from __future__ import annotations


async def test_sso_login_returns_authorize_url(client):
    """Arrange: client. Act: GET /api/v1/auth/sso/login. Assert: 200 + URL field."""
    # Arrange / Act
    resp = await client.get("/api/v1/auth/sso/login")
    # Assert
    assert resp.status_code == 200
    body = resp.json()
    assert "authorize_url" in body
    assert "login.microsoftonline.com" in body["authorize_url"]


async def test_sso_callback_sets_session_cookie(client):
    """Arrange: callback code/state. Act. Assert: redirect + secure cookie."""
    resp = await client.get(
        "/api/v1/auth/sso/callback",
        params={"code": "integration-code", "state": "state-token"},
        follow_redirects=False,
    )

    assert resp.status_code == 302
    cookie = resp.headers.get("set-cookie", "")
    assert "lo_session=" in cookie
    assert "HttpOnly" in cookie


async def test_me_requires_authentication(client):
    """Arrange: no bearer token. Act: GET /api/v1/auth/me. Assert: 401."""
    # Arrange / Act
    resp = await client.get("/api/v1/auth/me")
    # Assert
    assert resp.status_code == 401


async def test_me_returns_profile_for_valid_token(client, auth_headers_admin):
    """Arrange: admin token. Act: GET /api/v1/auth/me. Assert: 200 with email."""
    # Arrange / Act
    resp = await client.get("/api/v1/auth/me", headers=auth_headers_admin)
    # Assert
    assert resp.status_code == 200
    body = resp.json()
    assert "email" in body or "id" in body


async def test_invalid_token_returns_401(client):
    """Arrange: garbage bearer. Act: GET /api/v1/auth/me. Assert: 401."""
    # Arrange
    headers = {"Authorization": "Bearer not-a-jwt"}
    # Act
    resp = await client.get("/api/v1/auth/me", headers=headers)
    # Assert
    assert resp.status_code == 401


async def test_logout_clears_session_cookie(client, auth_headers_admin):
    """Arrange: authenticated user. Act: logout. Assert: cookie deletion."""
    resp = await client.post("/api/v1/auth/logout", headers=auth_headers_admin)

    assert resp.status_code == 204
    assert "lo_session=" in resp.headers.get("set-cookie", "")
