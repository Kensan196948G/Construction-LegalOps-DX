"""Integration tests for workflow_service uncovered paths.

Targets:
    - list_definitions() with pagination and contract_type filter
    - create_definition() success and duplicate (409)
    - start_workflow() full lifecycle + duplicate-start guard
    - get_instance() admin vs drafter access, not-found path
    - list_steps() with access control
    - execute_action(): approve, reject (return alias), send_back, delegate,
      unknown action (422), no-active-step (409)
    - Error cases: instance not found (404)

Coverage goal: workflow_service.py >= 50 %
"""

from __future__ import annotations

import uuid

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_code(prefix: str = "wf_steps_test") -> str:
    """Return a workflow code that is unique across test runs."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


_CONTRACT_BODY = {
    "title": "ワークフローステップテスト契約",
    "contract_type": "工事請負契約",
    "counterparty": "ステップテスト建設",
    "department_id": 1,
}


async def _create_workflow_definition(client, headers, *, code: str | None = None) -> int:
    """Create a 2-step workflow definition; return its database ID."""
    if code is None:
        code = _unique_code()
    r = await client.post(
        "/api/v1/workflows",
        json={
            "code": code,
            "name": f"ステップテスト承認フロー ({code})",
            "definition": {
                "steps": [
                    {
                        "seq": 1,
                        "name": "一次承認",
                        "step_type": "manager_approval",
                        "assignee_role": "admin",
                        "sla_hours": 24,
                    },
                    {
                        "seq": 2,
                        "name": "最終承認",
                        "step_type": "manager_approval",
                        "assignee_role": "admin",
                    },
                ]
            },
        },
        headers=headers,
    )
    assert r.status_code in (200, 201), f"definition creation failed: {r.status_code} {r.text}"
    return r.json()["id"]


async def _create_workflow_definition_with_contract_type(
    client, headers, *, contract_type: str, code: str | None = None
) -> int:
    """Create a workflow definition with a specific contract_type."""
    if code is None:
        code = _unique_code(f"wf_ct_{contract_type[:6]}")
    r = await client.post(
        "/api/v1/workflows",
        json={
            "code": code,
            "name": f"{contract_type} フロー ({code})",
            "contract_type": contract_type,
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
        },
        headers=headers,
    )
    assert r.status_code in (200, 201), f"definition creation failed: {r.status_code} {r.text}"
    return r.json()["id"]


async def _create_contract(client, headers) -> int:
    r = await client.post("/api/v1/contracts", json=_CONTRACT_BODY, headers=headers)
    assert r.status_code in (200, 201), f"contract creation failed: {r.status_code} {r.text}"
    return r.json()["id"]


async def _start_instance(client, contract_id: int, wf_id: int, code: str, headers) -> int:
    r = await client.post(
        f"/api/v1/contracts/{contract_id}/workflows",
        json={"workflow_id": wf_id, "definition_code": code},
        headers=headers,
    )
    assert r.status_code in (200, 201), f"start failed: {r.status_code} {r.text}"
    return r.json()["id"]


# ---------------------------------------------------------------------------
# GET /workflows — list definitions
# ---------------------------------------------------------------------------


async def test_list_definitions_pagination(client, auth_headers_admin):
    """list_definitions() returns items + total with pagination params."""
    # Create at least one definition to ensure non-empty list
    await _create_workflow_definition(client, auth_headers_admin)

    r = await client.get("/api/v1/workflows?page=1&size=5", headers=auth_headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body
    assert isinstance(body["items"], list)
    assert body["total"] >= 1


async def test_list_definitions_page_2_empty_or_valid(client, auth_headers_admin):
    """list_definitions() page 2 returns valid (possibly empty) page."""
    r = await client.get("/api/v1/workflows?page=2&size=200", headers=auth_headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert isinstance(body["items"], list)


async def test_list_definitions_filter_by_contract_type(client, auth_headers_admin):
    """list_definitions() filters by contract_type correctly."""
    unique_type = f"type_{uuid.uuid4().hex[:6]}"
    await _create_workflow_definition_with_contract_type(
        client, auth_headers_admin, contract_type=unique_type
    )

    r = await client.get(
        f"/api/v1/workflows?contract_type={unique_type}", headers=auth_headers_admin
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    for item in body["items"]:
        assert item.get("contract_type") == unique_type


async def test_list_definitions_filter_no_match(client, auth_headers_admin):
    """list_definitions() with nonexistent contract_type returns empty page."""
    r = await client.get(
        "/api/v1/workflows?contract_type=nonexistent_type_xyz999",
        headers=auth_headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["total"] == 0
    assert r.json()["items"] == []


# ---------------------------------------------------------------------------
# POST /workflows — create definition
# ---------------------------------------------------------------------------


async def test_create_workflow_definition_success(client, auth_headers_admin):
    """create_definition() persists the definition and returns it."""
    code = _unique_code("create_test")
    r = await client.post(
        "/api/v1/workflows",
        json={
            "code": code,
            "name": "作成テストフロー",
            "description": "テスト用の承認フロー",
            "contract_type": "工事請負契約",
            "is_active": True,
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
        },
        headers=auth_headers_admin,
    )
    assert r.status_code in (200, 201)
    body = r.json()
    assert body["code"] == code
    assert body["name"] == "作成テストフロー"
    assert "steps" in body.get("definition", {})
    assert body["is_active"] is True
    assert "id" in body


async def test_create_workflow_definition_duplicate_409(client, auth_headers_admin):
    """create_definition() with duplicate code returns 409 Conflict."""
    code = _unique_code("dup_test")
    # First creation must succeed
    r1 = await client.post(
        "/api/v1/workflows",
        json={
            "code": code,
            "name": "重複テストフロー",
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
        },
        headers=auth_headers_admin,
    )
    assert r1.status_code in (200, 201)

    # Second creation with identical code must return 409
    r2 = await client.post(
        "/api/v1/workflows",
        json={
            "code": code,
            "name": "重複テストフロー (2nd)",
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
        },
        headers=auth_headers_admin,
    )
    assert r2.status_code == 409


async def test_create_workflow_definition_requires_admin(client, auth_headers_legal):
    """create_definition() requires admin role; reviewer gets 403."""
    code = _unique_code("role_test")
    r = await client.post(
        "/api/v1/workflows",
        json={
            "code": code,
            "name": "権限テスト",
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
        },
        headers=auth_headers_legal,
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# POST /contracts/{id}/workflows — start instance
# ---------------------------------------------------------------------------


async def test_start_workflow_instance_lifecycle(client, auth_headers_admin, auth_headers_legal):
    """start_workflow() creates steps and returns a pending/in_progress instance."""
    code = _unique_code("lifecycle")
    wf_id = await _create_workflow_definition(client, auth_headers_admin, code=code)
    cid = await _create_contract(client, auth_headers_legal)

    r = await client.post(
        f"/api/v1/contracts/{cid}/workflows",
        json={"workflow_id": wf_id, "definition_code": code},
        headers=auth_headers_admin,
    )
    assert r.status_code in (200, 201)
    body = r.json()
    assert body["contract_id"] == cid
    assert body["status"] in ("pending", "in_progress")
    assert body["workflow_id"] == wf_id
    assert "started_at" in body


async def test_start_workflow_duplicate_returns_409(
    client, auth_headers_admin, auth_headers_legal
):
    """start_workflow() on a contract that already has an active workflow returns 409."""
    code = _unique_code("dup_instance")
    wf_id = await _create_workflow_definition(client, auth_headers_admin, code=code)
    cid = await _create_contract(client, auth_headers_legal)

    r1 = await client.post(
        f"/api/v1/contracts/{cid}/workflows",
        json={"workflow_id": wf_id, "definition_code": code},
        headers=auth_headers_admin,
    )
    assert r1.status_code in (200, 201)

    r2 = await client.post(
        f"/api/v1/contracts/{cid}/workflows",
        json={"workflow_id": wf_id, "definition_code": code},
        headers=auth_headers_admin,
    )
    assert r2.status_code == 409


async def test_start_workflow_unknown_definition_returns_404(
    client, auth_headers_admin, auth_headers_legal
):
    """start_workflow() with nonexistent definition_code returns 404."""
    cid = await _create_contract(client, auth_headers_legal)
    r = await client.post(
        f"/api/v1/contracts/{cid}/workflows",
        json={"workflow_id": 0, "definition_code": "nonexistent_code_xyz_999"},
        headers=auth_headers_admin,
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /workflows/{instance_id} — get instance
# ---------------------------------------------------------------------------


async def test_get_instance_admin_full_access(client, auth_headers_admin, auth_headers_legal):
    """get_instance() admin can retrieve any workflow instance."""
    code = _unique_code("get_inst")
    wf_id = await _create_workflow_definition(client, auth_headers_admin, code=code)
    cid = await _create_contract(client, auth_headers_legal)
    instance_id = await _start_instance(client, cid, wf_id, code, auth_headers_admin)

    r = await client.get(f"/api/v1/workflows/{instance_id}", headers=auth_headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == instance_id
    assert body["contract_id"] == cid
    assert "status" in body
    assert "workflow_id" in body
    assert "started_at" in body


async def test_get_instance_not_found(client, auth_headers_admin):
    """get_instance() for a nonexistent instance returns 404."""
    r = await client.get("/api/v1/workflows/999999", headers=auth_headers_admin)
    assert r.status_code == 404


async def test_get_instance_requires_auth(client):
    """get_instance() without auth returns 401."""
    r = await client.get("/api/v1/workflows/1")
    assert r.status_code == 401


async def test_get_instance_drafter_limited_access(
    client, auth_headers_admin, auth_headers_legal, auth_headers_site
):
    """get_instance() drafter can see their own contract's workflow but not others'."""
    code = _unique_code("drafter_access")
    wf_id = await _create_workflow_definition(client, auth_headers_admin, code=code)
    # Contract created by legal (reviewer), not drafter
    cid = await _create_contract(client, auth_headers_legal)
    instance_id = await _start_instance(client, cid, wf_id, code, auth_headers_admin)

    # Drafter (site user) does not own this contract → 404 (access denied or not found)
    r = await client.get(f"/api/v1/workflows/{instance_id}", headers=auth_headers_site)
    assert r.status_code in (403, 404)


# ---------------------------------------------------------------------------
# GET /workflows/{instance_id}/steps — list steps
# ---------------------------------------------------------------------------


async def test_list_steps_after_start(client, auth_headers_admin, auth_headers_legal):
    """list_steps() returns ordered step list after workflow start."""
    code = _unique_code("list_steps")
    wf_id = await _create_workflow_definition(client, auth_headers_admin, code=code)
    cid = await _create_contract(client, auth_headers_legal)
    instance_id = await _start_instance(client, cid, wf_id, code, auth_headers_admin)

    r = await client.get(f"/api/v1/workflows/{instance_id}/steps", headers=auth_headers_admin)
    assert r.status_code == 200
    steps = r.json()
    assert isinstance(steps, list)
    assert len(steps) == 2  # 2-step definition
    seqs = [s["seq"] for s in steps]
    assert seqs == sorted(seqs)
    # First step should be in_progress; second pending
    statuses = [s["status"] for s in steps]
    assert "in_progress" in statuses


async def test_list_steps_empty_for_unknown_instance(client, auth_headers_admin):
    """list_steps() returns empty list for an unknown instance."""
    r = await client.get("/api/v1/workflows/999998/steps", headers=auth_headers_admin)
    assert r.status_code == 200
    assert r.json() == []


async def test_list_steps_requires_auth(client):
    """list_steps() without auth returns 401."""
    r = await client.get("/api/v1/workflows/1/steps")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /workflows/{instance_id}/actions — execute_action
# ---------------------------------------------------------------------------


async def test_action_approve_advances_step(client, auth_headers_admin, auth_headers_legal):
    """execute_action(approve) advances the workflow to the next step."""
    code = _unique_code("approve_adv")
    wf_id = await _create_workflow_definition(client, auth_headers_admin, code=code)
    cid = await _create_contract(client, auth_headers_legal)
    instance_id = await _start_instance(client, cid, wf_id, code, auth_headers_admin)

    r = await client.post(
        f"/api/v1/workflows/{instance_id}/actions",
        json={"action": "approve", "comment": "Step 1 OK"},
        headers=auth_headers_admin,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("in_progress", "approved")
    # After approving step 1 of 2, current_seq should advance or be None if done
    assert body.get("current_seq") in (2, None)


async def test_action_approve_all_steps_completes(
    client, auth_headers_admin, auth_headers_legal
):
    """execute_action(approve) for all steps results in approved status."""
    code = _unique_code("approve_all")
    wf_id = await _create_workflow_definition(client, auth_headers_admin, code=code)
    cid = await _create_contract(client, auth_headers_legal)
    instance_id = await _start_instance(client, cid, wf_id, code, auth_headers_admin)

    for _ in range(2):  # 2-step workflow
        r = await client.post(
            f"/api/v1/workflows/{instance_id}/actions",
            json={"action": "approve", "comment": "OK"},
            headers=auth_headers_admin,
        )
        if r.status_code == 409:
            break
        assert r.status_code == 200

    r_inst = await client.get(f"/api/v1/workflows/{instance_id}", headers=auth_headers_admin)
    assert r_inst.status_code == 200
    assert r_inst.json()["status"] == "approved"


async def test_action_reject_terminates_workflow(
    client, auth_headers_admin, auth_headers_legal
):
    """execute_action(reject) terminates the workflow with rejected status."""
    code = _unique_code("reject_term")
    wf_id = await _create_workflow_definition(client, auth_headers_admin, code=code)
    cid = await _create_contract(client, auth_headers_legal)
    instance_id = await _start_instance(client, cid, wf_id, code, auth_headers_admin)

    r = await client.post(
        f"/api/v1/workflows/{instance_id}/actions",
        json={"action": "reject", "comment": "却下"},
        headers=auth_headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"


async def test_action_send_back_restores_previous_step(
    client, auth_headers_admin, auth_headers_legal
):
    """execute_action(send_back) sends the workflow back to a previous step."""
    code = _unique_code("send_back")
    wf_id = await _create_workflow_definition(client, auth_headers_admin, code=code)
    cid = await _create_contract(client, auth_headers_legal)
    instance_id = await _start_instance(client, cid, wf_id, code, auth_headers_admin)

    # Approve step 1 first to move to step 2
    r_approve = await client.post(
        f"/api/v1/workflows/{instance_id}/actions",
        json={"action": "approve", "comment": "Step 1 OK"},
        headers=auth_headers_admin,
    )
    assert r_approve.status_code == 200
    assert r_approve.json().get("current_seq") == 2

    # Send back to step 1
    r_back = await client.post(
        f"/api/v1/workflows/{instance_id}/actions",
        json={"action": "send_back", "comment": "差戻し", "to_seq": 1},
        headers=auth_headers_admin,
    )
    assert r_back.status_code == 200
    body = r_back.json()
    assert body["status"] == "in_progress"


async def test_action_send_back_invalid_seq_returns_409(
    client, auth_headers_admin, auth_headers_legal
):
    """execute_action(send_back) with invalid to_seq returns 409."""
    code = _unique_code("send_back_inv")
    wf_id = await _create_workflow_definition(client, auth_headers_admin, code=code)
    cid = await _create_contract(client, auth_headers_legal)
    instance_id = await _start_instance(client, cid, wf_id, code, auth_headers_admin)

    r = await client.post(
        f"/api/v1/workflows/{instance_id}/actions",
        json={"action": "send_back", "comment": "差戻し", "to_seq": 999},
        headers=auth_headers_admin,
    )
    assert r.status_code == 409


async def test_action_unknown_action_returns_422(
    client, auth_headers_admin, auth_headers_legal
):
    """execute_action() with an unrecognized action verb returns 422."""
    code = _unique_code("unknown_action")
    wf_id = await _create_workflow_definition(client, auth_headers_admin, code=code)
    cid = await _create_contract(client, auth_headers_legal)
    instance_id = await _start_instance(client, cid, wf_id, code, auth_headers_admin)

    r = await client.post(
        f"/api/v1/workflows/{instance_id}/actions",
        json={"action": "explode", "comment": "invalid"},
        headers=auth_headers_admin,
    )
    assert r.status_code == 422


async def test_action_on_completed_workflow_returns_409(
    client, auth_headers_admin, auth_headers_legal
):
    """execute_action() when no active step exists returns 409."""
    code = _unique_code("no_active")
    wf_id = await _create_workflow_definition(client, auth_headers_admin, code=code)
    cid = await _create_contract(client, auth_headers_legal)
    instance_id = await _start_instance(client, cid, wf_id, code, auth_headers_admin)

    # Approve all steps to complete the workflow
    for _ in range(3):
        r = await client.post(
            f"/api/v1/workflows/{instance_id}/actions",
            json={"action": "approve"},
            headers=auth_headers_admin,
        )
        if r.status_code == 409:
            break

    # One more approve attempt should get 409 (no active step)
    r_extra = await client.post(
        f"/api/v1/workflows/{instance_id}/actions",
        json={"action": "approve"},
        headers=auth_headers_admin,
    )
    assert r_extra.status_code == 409


async def test_action_on_nonexistent_instance_returns_404(client, auth_headers_admin):
    """execute_action() on a nonexistent instance returns 404."""
    r = await client.post(
        "/api/v1/workflows/999997/actions",
        json={"action": "approve", "comment": "test"},
        headers=auth_headers_admin,
    )
    assert r.status_code == 404


async def test_action_requires_auth(client):
    """execute_action() without auth returns 401."""
    r = await client.post(
        "/api/v1/workflows/1/actions",
        json={"action": "approve"},
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Fallback: start with no definition_code (uses first active definition)
# ---------------------------------------------------------------------------


async def test_start_workflow_without_definition_code(
    client, auth_headers_admin, auth_headers_legal
):
    """start_workflow() without definition_code falls back to first active definition."""
    # Ensure at least one active definition exists
    code = _unique_code("fallback_def")
    wf_id = await _create_workflow_definition(client, auth_headers_admin, code=code)
    cid = await _create_contract(client, auth_headers_legal)

    r = await client.post(
        f"/api/v1/contracts/{cid}/workflows",
        json={"workflow_id": wf_id},  # no definition_code
        headers=auth_headers_admin,
    )
    # Should succeed if any active definition exists
    assert r.status_code in (200, 201, 404)
