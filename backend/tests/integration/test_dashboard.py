"""KPI / dashboard endpoint tests.

Covers ``GET /api/v1/dashboard`` (or ``/api/v1/dashboards/summary``) which
aggregates:

* contracts by status / type
* outstanding reviews
* average risk score
* SLA breaches in workflow
"""

from __future__ import annotations


async def test_dashboard_summary_returns_metrics(client, auth_headers_admin):
    """Arrange: client + admin. Act: GET summary. Assert: keys present."""
    # Arrange / Act
    r = await client.get("/api/v1/dashboard/summary", headers=auth_headers_admin)
    # Assert
    assert r.status_code == 200
    body = r.json()
    for key in ("contracts_by_status", "avg_risk_score", "pending_reviews"):
        assert key in body


async def test_dashboard_counts_match_db(client, auth_headers_admin, auth_headers_legal):
    """Arrange: create N contracts. Act: aggregate. Assert: count matches."""
    # Arrange
    for i in range(5):
        await client.post(
            "/api/v1/contracts",
            json={
                "title": f"集計 {i}",
                "contract_type": "工事請負契約",
                "counterparty": "Z建設",
                "department_id": 1,
            },
            headers=auth_headers_legal,
        )

    # Act
    r = await client.get("/api/v1/dashboard/summary", headers=auth_headers_admin)
    body = r.json()
    # Assert
    by_status = body.get("contracts_by_status", {})
    assert sum(by_status.values()) >= 5


async def test_dashboard_requires_authentication(client):
    """Arrange: no auth. Act: GET. Assert: 401."""
    # Arrange / Act
    resp = await client.get("/api/v1/dashboard/summary")
    # Assert
    assert resp.status_code == 401
