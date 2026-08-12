"""Integration tests for workflow definition CRUD and instance listing.

Covers endpoints not exercised by test_workflow_actions.py:
    - GET /workflows                  → list definitions
    - POST /workflows                 → create definition
    - GET /workflows/{id}             → get instance
    - GET /workflows/{id}/steps       → list steps
    - Auth guards (401)
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WF_DEF = {
    "code": "crud_test_wf",
    "name": "CRUD テスト承認フロー",
    "definition": {
        "steps": [
            {
                "seq": 1,
                "name": "承認",
                "step_type": "manager_approval",
                "assignee_role": "admin",
            }
        ]
    },
}

_CONTRACT_BODY = {
    "title": "ワークフロー CRUD テスト契約",
    "contract_type": "工事請負契約",
    "counterparty": "CRUD テスト建設",
    "department_id": 1,
}


async def _create_wf_definition(client, headers) -> int:
    r = await client.post("/api/v1/workflows", json=_WF_DEF, headers=headers)
    if r.status_code == 409:
        r_list = await client.get("/api/v1/workflows?size=100", headers=headers)
        for item in r_list.json().get("items", []):
            if item.get("code") == _WF_DEF["code"]:
                return item["id"]
        raise AssertionError("workflow definition not found after 409")
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


async def _create_contract(client, headers) -> int:
    r = await client.post("/api/v1/contracts", json=_CONTRACT_BODY, headers=headers)
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


async def _start_instance(client, contract_id, wf_id, headers) -> int:
    r = await client.post(
        f"/api/v1/contracts/{contract_id}/workflows",
        json={"workflow_id": wf_id, "definition_code": _WF_DEF["code"]},
        headers=headers,
    )
    assert r.status_code in (200, 201), r.text
    return r.json().get("id") or contract_id  # instance id == contract_id by design


# ---------------------------------------------------------------------------
# GET /workflows — list definitions
# ---------------------------------------------------------------------------


async def test_list_workflow_definitions_returns_page(client, auth_headers_admin):
    """GET /workflows returns pagination schema."""
    r = await client.get("/api/v1/workflows", headers=auth_headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body


async def test_list_workflow_definitions_requires_auth(client):
    """GET /workflows without auth → 401."""
    r = await client.get("/api/v1/workflows")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /workflows/applications — 稟議一覧（workflow_step × contract 結合ビュー）
# ---------------------------------------------------------------------------


async def test_list_applications_returns_workflow_steps(
    client, auth_headers_admin, auth_headers_legal
):
    """GET /workflows/applications returns started workflows as 稟議 rows."""
    wf_id = await _create_wf_definition(client, auth_headers_admin)
    cid = await _create_contract(client, auth_headers_legal)
    await _start_instance(client, cid, wf_id, auth_headers_admin)

    r = await client.get("/api/v1/workflows/applications", headers=auth_headers_admin)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "items" in body
    assert body["total"] >= 1
    row = next((i for i in body["items"] if i["contract_id"] == cid), None)
    assert row is not None
    assert row["contract_id"] == cid
    assert row["title"] == _CONTRACT_BODY["title"]
    assert row["step_name"] == "承認"
    assert row["status"] == "in_progress"


async def test_list_applications_requires_auth(client):
    """GET /workflows/applications without auth → 401."""
    r = await client.get("/api/v1/workflows/applications")
    assert r.status_code == 401


async def test_list_applications_status_filter(client, auth_headers_admin, auth_headers_legal):
    """status フィルタで step 状態を絞り込める."""
    wf_id = await _create_wf_definition(client, auth_headers_admin)
    cid = await _create_contract(client, auth_headers_legal)
    await _start_instance(client, cid, wf_id, auth_headers_admin)

    r = await client.get(
        "/api/v1/workflows/applications?status=approved",
        headers=auth_headers_admin,
    )
    assert r.status_code == 200
    assert all(item["status"] == "approved" for item in r.json()["items"])


# ---------------------------------------------------------------------------
# POST /workflows — create definition
# ---------------------------------------------------------------------------


async def test_create_workflow_definition(client, auth_headers_admin):
    """POST /workflows creates a definition and returns it (or 409 if already exists)."""
    r = await client.post("/api/v1/workflows", json=_WF_DEF, headers=auth_headers_admin)
    assert r.status_code in (200, 201, 409)
    if r.status_code in (200, 201):
        body = r.json()
        assert body["code"] == _WF_DEF["code"]
        assert "steps" in body.get("definition", {})


async def test_create_workflow_definition_requires_auth(client):
    """POST /workflows without auth → 401."""
    r = await client.post("/api/v1/workflows", json=_WF_DEF)
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /workflows/{instance_id} — get instance
# ---------------------------------------------------------------------------


async def test_get_workflow_instance(client, auth_headers_admin, auth_headers_legal):
    """GET /workflows/{id} returns a workflow instance."""
    wf_id = await _create_wf_definition(client, auth_headers_admin)
    cid = await _create_contract(client, auth_headers_legal)
    instance_id = await _start_instance(client, cid, wf_id, auth_headers_admin)

    r = await client.get(f"/api/v1/workflows/{instance_id}", headers=auth_headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert "contract_id" in body


async def test_get_workflow_instance_not_found(client, auth_headers_admin):
    """GET /workflows/999999 → 404."""
    r = await client.get("/api/v1/workflows/999999", headers=auth_headers_admin)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /workflows/{instance_id}/steps
# ---------------------------------------------------------------------------


async def test_list_workflow_steps(client, auth_headers_admin, auth_headers_legal):
    """GET /workflows/{id}/steps returns a list of steps."""
    wf_id = await _create_wf_definition(client, auth_headers_admin)
    cid = await _create_contract(client, auth_headers_legal)
    instance_id = await _start_instance(client, cid, wf_id, auth_headers_admin)

    r = await client.get(f"/api/v1/workflows/{instance_id}/steps", headers=auth_headers_admin)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_list_workflow_steps_unknown_instance(client, auth_headers_admin):
    """GET /workflows/999999/steps → 200 with empty list (no steps for unknown id)."""
    r = await client.get("/api/v1/workflows/999999/steps", headers=auth_headers_admin)
    # Service returns empty list for unknown instance (no 404 by design)
    assert r.status_code == 200
    assert r.json() == []
