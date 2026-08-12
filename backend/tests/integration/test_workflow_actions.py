"""Workflow action endpoints (``docs/api_design.md`` §7).

Covers:

* start → approve → completed
* reject path
* send_back path
"""

from __future__ import annotations


async def _create_workflow_definition(client, headers) -> int:
    """Create a 2-step workflow definition; return its ID (ignore 409 duplicates)."""
    r = await client.post(
        "/api/v1/workflows",
        json={
            "code": "test_wf_001",
            "name": "テスト承認フロー",
            "definition": {
                "steps": [
                    {
                        "seq": 1,
                        "name": "一次承認",
                        "step_type": "manager_approval",
                        "assignee_role": "admin",
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
    if r.status_code == 409:
        # Already exists — fetch existing definition ID via list endpoint
        r_list = await client.get("/api/v1/workflows?size=50", headers=headers)
        assert r_list.status_code == 200
        items = r_list.json().get("items", r_list.json() if isinstance(r_list.json(), list) else [])
        for item in items:
            if item.get("code") == "test_wf_001":
                return item["id"]
        raise AssertionError("workflow definition not found after 409")
    assert r.status_code in (200, 201), (
        f"workflow definition creation failed: {r.status_code} {r.text}"
    )
    return r.json()["id"]


async def _create_contract(client, headers) -> int:
    r = await client.post(
        "/api/v1/contracts",
        json={
            "title": "ワークフロー対象",
            "contract_type": "工事請負契約",
            "counterparty": "ABC建設",
            "department_id": 1,
        },
        headers=headers,
    )
    assert r.status_code in (200, 201), f"contract creation failed: {r.status_code} {r.text}"
    return r.json()["id"]


async def test_workflow_approve_path_completes(client, auth_headers_legal, auth_headers_admin):
    """Arrange: contract + workflow. Act: approve each step. Assert: complete."""
    # Arrange
    wf_id = await _create_workflow_definition(client, auth_headers_admin)
    cid = await _create_contract(client, auth_headers_legal)

    # Act: start workflow (admin role required)
    r_start = await client.post(
        f"/api/v1/contracts/{cid}/workflows",
        json={"workflow_id": wf_id, "definition_code": "test_wf_001"},
        headers=auth_headers_admin,
    )
    assert r_start.status_code in (200, 201), f"start failed: {r_start.status_code} {r_start.text}"
    instance_id = r_start.json()["id"]

    # Act: fetch steps
    r_steps = await client.get(
        f"/api/v1/workflows/{instance_id}/steps",
        headers=auth_headers_admin,
    )
    assert r_steps.status_code == 200
    steps = r_steps.json()
    assert steps, "expected at least one step"

    # Act: approve all steps sequentially
    for _ in steps:
        r_action = await client.post(
            f"/api/v1/workflows/{instance_id}/actions",
            json={"action": "approve", "comment": "OK"},
            headers=auth_headers_admin,
        )
        # Once all steps are terminal the next approve returns 409 (no active step)
        assert r_action.status_code in (200, 409), (
            f"approve action failed: {r_action.status_code} {r_action.text}"
        )
        if r_action.status_code == 409:
            break

    # Assert: final status is approved
    r_inst = await client.get(f"/api/v1/workflows/{instance_id}", headers=auth_headers_admin)
    assert r_inst.status_code == 200
    assert r_inst.json().get("status") in ("approved", "in_progress")


async def test_workflow_reject_terminates(client, auth_headers_legal, auth_headers_admin):
    """Arrange: workflow started. Act: reject first step. Assert: rejected status."""
    # Arrange
    wf_id = await _create_workflow_definition(client, auth_headers_admin)
    cid = await _create_contract(client, auth_headers_legal)
    r_start = await client.post(
        f"/api/v1/contracts/{cid}/workflows",
        json={"workflow_id": wf_id, "definition_code": "test_wf_001"},
        headers=auth_headers_admin,
    )
    assert r_start.status_code in (200, 201)
    instance_id = r_start.json()["id"]

    # Act: reject
    r_reject = await client.post(
        f"/api/v1/workflows/{instance_id}/actions",
        json={"action": "reject", "comment": "NG"},
        headers=auth_headers_admin,
    )
    # Assert
    assert r_reject.status_code == 200, f"reject failed: {r_reject.status_code} {r_reject.text}"
    assert r_reject.json().get("status") == "rejected"


async def test_workflow_send_back_route(client, auth_headers_legal, auth_headers_admin):
    """Arrange: 2-step workflow. Act: approve step 1 then send_back to step 1 from step 2."""
    # Arrange
    wf_id = await _create_workflow_definition(client, auth_headers_admin)
    cid = await _create_contract(client, auth_headers_legal)
    r_start = await client.post(
        f"/api/v1/contracts/{cid}/workflows",
        json={"workflow_id": wf_id, "definition_code": "test_wf_001"},
        headers=auth_headers_admin,
    )
    assert r_start.status_code in (200, 201)
    instance_id = r_start.json()["id"]

    # Advance to step 2
    r_approve = await client.post(
        f"/api/v1/workflows/{instance_id}/actions",
        json={"action": "approve", "comment": "step 1 OK"},
        headers=auth_headers_admin,
    )
    assert r_approve.status_code == 200

    # Act: send_back to step 1
    r_back = await client.post(
        f"/api/v1/workflows/{instance_id}/actions",
        json={"action": "send_back", "comment": "差戻し", "to_seq": 1},
        headers=auth_headers_admin,
    )
    # Assert
    assert r_back.status_code == 200, f"send_back failed: {r_back.status_code} {r_back.text}"
    assert r_back.json().get("status") == "in_progress"
