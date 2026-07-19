"""Integration tests for health-check endpoints.

Endpoints (``docs/api_design.md`` §15):

* ``GET /healthz``    — liveness
* ``GET /readyz``     — readiness (depends on DB)
* ``GET /version``    — build info

Loop 2 only exposes ``/health`` (alias). We probe both shapes.
"""

from __future__ import annotations


async def test_health_returns_200(client):
    """Arrange: live client. Act: GET /health. Assert: 200 + JSON status."""
    # Arrange / Act
    resp = await client.get("/health")
    # Assert
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("status") in ("ok", "healthy", "up")


async def test_api_v1_health_returns_200(client):
    """Arrange: live client. Act: GET /api/v1/health. Assert: 200 + JSON status."""
    # Arrange / Act
    resp = await client.get("/api/v1/health")
    # Assert
    assert resp.status_code == 200


async def test_readyz_returns_200_when_db_up(client):
    """Arrange: live DB. Act: GET /readyz. Assert: 200."""
    # Arrange / Act
    resp = await client.get("/readyz")
    # Assert
    assert resp.status_code == 200


async def test_metrics_exposes_request_db_business_and_queue_metrics(client):
    """Metrics endpoint includes release-ops gauges without requiring Redis."""
    await client.get("/health")

    resp = await client.get("/metrics")

    assert resp.status_code == 200
    text = resp.text
    assert "http_requests_total" in text
    assert "db_commit_failures_total" in text
    assert "legalops_contracts_by_status" in text
    assert "legalops_legal_reviews_by_status" in text
    assert "legalops_workflow_steps_by_status" in text
    assert "legalops_notifications_by_status" in text
    assert 'celery_queue_length{queue="legalops.default"}' in text
