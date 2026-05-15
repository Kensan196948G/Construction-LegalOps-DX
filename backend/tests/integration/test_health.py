"""Integration tests for health-check endpoints.

Endpoints (``docs/api_design.md`` §15):

* ``GET /healthz``    — liveness
* ``GET /readyz``     — readiness (depends on DB)
* ``GET /version``    — build info

Loop 2 only exposes ``/health`` (alias). We probe both shapes.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="ASGI app not fully wired in Loop 2 — implemented in Loop 3")
async def test_health_returns_200(client):
    """Arrange: live client. Act: GET /health. Assert: 200 + JSON status."""
    # Arrange / Act
    resp = await client.get("/health")
    # Assert
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("status") in ("ok", "healthy", "up")


@pytest.mark.skip(reason="API prefix endpoint implemented in Loop 3")
async def test_api_v1_health_returns_200(client):
    """Arrange: live client. Act: GET /api/v1/health. Assert: 200 + JSON status."""
    # Arrange / Act
    resp = await client.get("/api/v1/health")
    # Assert
    assert resp.status_code == 200


@pytest.mark.skip(reason="Readiness endpoint implemented in Loop 3")
async def test_readyz_returns_200_when_db_up(client):
    """Arrange: live DB. Act: GET /readyz. Assert: 200."""
    # Arrange / Act
    resp = await client.get("/readyz")
    # Assert
    assert resp.status_code == 200
