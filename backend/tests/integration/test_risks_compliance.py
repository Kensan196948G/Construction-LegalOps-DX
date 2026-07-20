"""Integration tests for risks and compliance endpoints.

Covers:
    - GET /risks                → list (auth required, role scoped)
    - GET /risks/aggregate      → aggregate KPI
    - GET /compliance/checklists → static checklist registry
    - GET /compliance/checks/{id} → per-contract result
    - POST /compliance/checks/{id}/run → async job handle
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CONTRACT_BODY = {
    "title": "リスク・コンプライアンス テスト契約",
    "contract_type": "ukeoi",
    "counterparty": "テスト建設株式会社",
    "department_id": 1,
}


async def _create_contract(client, headers) -> int:
    r = await client.post("/api/v1/contracts", json=_CONTRACT_BODY, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
# Risks
# ---------------------------------------------------------------------------


async def test_list_risks_returns_200(client, auth_headers_admin):
    """GET /risks returns 200 with page schema."""
    r = await client.get("/api/v1/risks", headers=auth_headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body


async def test_list_risks_requires_authentication(client):
    """GET /risks without auth → 401."""
    r = await client.get("/api/v1/risks")
    assert r.status_code == 401


async def test_aggregate_risks_returns_200(client, auth_headers_admin):
    """GET /risks/aggregate returns correct aggregate structure."""
    r = await client.get("/api/v1/risks/aggregate", headers=auth_headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert "by_severity" in body
    assert "by_status" in body
    assert "open_count" in body
    assert "disclaimer" in body


async def test_list_risks_severity_filter(client, auth_headers_admin):
    """GET /risks?severity=high returns only high-severity items (or empty)."""
    r = await client.get("/api/v1/risks?severity=high", headers=auth_headers_admin)
    assert r.status_code == 200
    body = r.json()
    for item in body.get("items", []):
        assert item["severity"] == "high"


async def test_update_risk_not_found(client, auth_headers_admin):
    """PATCH /risks/999999 returns 404 for non-existent risk."""
    r = await client.patch(
        "/api/v1/risks/999999",
        json={"status": "mitigated"},
        headers=auth_headers_admin,
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Compliance
# ---------------------------------------------------------------------------


async def test_list_checklists_returns_200(client, auth_headers_admin):
    """GET /compliance/checklists returns at least 4 static items."""
    r = await client.get("/api/v1/compliance/checklists", headers=auth_headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) >= 4


async def test_list_checklists_category_filter(client, auth_headers_admin):
    """GET /compliance/checklists?category=construction_law filters correctly."""
    r = await client.get(
        "/api/v1/compliance/checklists?category=construction_law",
        headers=auth_headers_admin,
    )
    assert r.status_code == 200
    body = r.json()
    for item in body:
        assert item["category"] == "construction_law"


async def test_list_checklists_requires_auth(client):
    """GET /compliance/checklists without auth → 401."""
    r = await client.get("/api/v1/compliance/checklists")
    assert r.status_code == 401


async def test_get_compliance_result_for_contract(client, auth_headers_legal):
    """GET /compliance/checks/{id} returns a ComplianceCheckResult."""
    contract_id = await _create_contract(client, auth_headers_legal)
    r = await client.get(
        f"/api/v1/compliance/checks/{contract_id}",
        headers=auth_headers_legal,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["contract_id"] == contract_id
    assert "findings" in body
    assert "overall_status" in body
    assert "disclaimer" in body


async def test_get_compliance_result_not_found(client, auth_headers_admin):
    """GET /compliance/checks/999999 → 404 for missing contract."""
    r = await client.get("/api/v1/compliance/checks/999999", headers=auth_headers_admin)
    assert r.status_code == 404


async def test_run_compliance_check_accepted(client, auth_headers_admin, auth_headers_legal):
    """POST /compliance/checks/{id}/run → 202 with a completed job handle."""
    contract_id = await _create_contract(client, auth_headers_legal)
    r = await client.post(
        f"/api/v1/compliance/checks/{contract_id}/run",
        headers=auth_headers_admin,
    )
    assert r.status_code == 202
    body = r.json()
    assert "job_id" in body
    assert body["contract_id"] == contract_id
    assert body["status"] == "done"
    assert "disclaimer" in body


async def test_run_compliance_check_not_found(client, auth_headers_admin):
    """POST /compliance/checks/999999/run → 404."""
    r = await client.post(
        "/api/v1/compliance/checks/999999/run",
        headers=auth_headers_admin,
    )
    assert r.status_code == 404
