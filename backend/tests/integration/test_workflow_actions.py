"""Workflow action endpoints (``docs/api_design.md`` §7).

Covers:

* start → approve → completed
* reject path
* send_back path
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Workflow API implemented in Loop 3")


async def _create_contract(client, headers) -> int:
    r = await client.post(
        "/api/v1/contracts",
        json={
            "title": "ワークフロー対象",
            "contract_type": "ukeoi",
            "counterparty_name": "ABC建設",
            "contract_amount": 8_000_000,
        },
        headers=headers,
    )
    return r.json()["id"]


async def test_workflow_approve_path_completes(client, auth_headers_legal, auth_headers_admin):
    """Arrange: contract + workflow. Act: approve each step. Assert: complete."""
    # Arrange
    cid = await _create_contract(client, auth_headers_legal)

    # Act: start
    r_start = await client.post(
        f"/api/v1/contracts/{cid}/workflows", json={}, headers=auth_headers_legal
    )
    # Assert
    assert r_start.status_code in (200, 201)
    steps = r_start.json().get("steps", [])
    assert steps

    # Act: approve all steps
    for step in steps:
        r_step = await client.post(
            f"/api/v1/workflow-steps/{step['id']}/approve",
            json={"comment": "OK"},
            headers=auth_headers_admin,
        )
        assert r_step.status_code == 200

    # Assert: workflow completed
    r_final = await client.get(f"/api/v1/contracts/{cid}/workflow-steps", headers=auth_headers_legal)
    assert r_final.status_code == 200
    assert all(s["status"] == "approved" for s in r_final.json())


async def test_workflow_reject_terminates(client, auth_headers_legal, auth_headers_admin):
    """Arrange: workflow started. Act: reject step. Assert: rejected status."""
    # Arrange
    cid = await _create_contract(client, auth_headers_legal)
    r = await client.post(
        f"/api/v1/contracts/{cid}/workflows", json={}, headers=auth_headers_legal
    )
    step_id = r.json()["steps"][0]["id"]

    # Act
    r_reject = await client.post(
        f"/api/v1/workflow-steps/{step_id}/reject",
        json={"comment": "NG"},
        headers=auth_headers_admin,
    )
    # Assert
    assert r_reject.status_code == 200
    assert r_reject.json().get("status") in ("rejected", "closed")


async def test_workflow_send_back_route(client, auth_headers_legal, auth_headers_admin):
    """Arrange: workflow started. Act: send_back. Assert: state regresses."""
    # Arrange
    cid = await _create_contract(client, auth_headers_legal)
    r = await client.post(
        f"/api/v1/contracts/{cid}/workflows", json={}, headers=auth_headers_legal
    )
    step_id = r.json()["steps"][0]["id"]

    # Act
    r_back = await client.post(
        f"/api/v1/workflow-steps/{step_id}/send-back",
        json={"comment": "差戻し"},
        headers=auth_headers_admin,
    )
    # Assert
    assert r_back.status_code == 200
    assert r_back.json().get("status") in ("sent_back", "in_progress")
