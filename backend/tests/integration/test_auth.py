"""Integration tests for auth endpoints (``docs/api_design.md`` §3).

* ``GET /auth/sso/login``  — returns Entra authorize URL (200, JSON)
* ``GET /auth/me``         — protected (401 when unauthenticated)
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="ASGI app wiring lands in Loop 3")
async def test_sso_login_returns_authorize_url(client):
    """Arrange: client. Act: GET /auth/sso/login. Assert: 200 + URL field."""
    # Arrange / Act
    resp = await client.get("/auth/sso/login")
    # Assert
    assert resp.status_code == 200
    body = resp.json()
    assert "authorize_url" in body
    assert "login.microsoftonline.com" in body["authorize_url"]


@pytest.mark.skip(reason="ASGI app wiring lands in Loop 3")
async def test_me_requires_authentication(client):
    """Arrange: no bearer token. Act: GET /auth/me. Assert: 401."""
    # Arrange / Act
    resp = await client.get("/auth/me")
    # Assert
    assert resp.status_code == 401


@pytest.mark.skip(reason="ASGI app wiring lands in Loop 3")
async def test_me_returns_profile_for_valid_token(client, auth_headers_admin):
    """Arrange: admin token. Act: GET /auth/me. Assert: 200 with email."""
    # Arrange / Act
    resp = await client.get("/auth/me", headers=auth_headers_admin)
    # Assert
    assert resp.status_code == 200
    body = resp.json()
    assert "email" in body or "id" in body


@pytest.mark.skip(reason="ASGI app wiring lands in Loop 3")
async def test_invalid_token_returns_401(client):
    """Arrange: garbage bearer. Act: GET /auth/me. Assert: 401."""
    # Arrange
    headers = {"Authorization": "Bearer not-a-jwt"}
    # Act
    resp = await client.get("/auth/me", headers=headers)
    # Assert
    assert resp.status_code == 401
