"""Audit log integration tests.

Validates that:

* every state-changing operation appends an ``audit_logs`` row
* ``hash_chain`` is contiguous (each row's prev_hash == previous row's hash)
* ``POST /api/v1/audit-logs/verify`` confirms the chain
"""

from __future__ import annotations

import itertools


async def test_audit_log_created_on_contract_create(client, auth_headers_legal, auth_headers_admin):
    """Arrange: client. Act: create contract. Assert: an audit row exists."""
    # Arrange
    r = await client.post(
        "/api/v1/contracts",
        json={
            "title": "監査テスト",
            "contract_type": "ukeoi",
            "counterparty": "監査建設",
            "department_id": 1,
        },
        headers=auth_headers_legal,
    )
    assert r.status_code in (200, 201)
    cid = r.json()["id"]

    # Act — requires admin/auditor role
    r_audit = await client.get(
        f"/api/v1/audit-logs?target_type=contracts&target_id={cid}",
        headers=auth_headers_admin,
    )
    # Assert
    assert r_audit.status_code == 200
    items = r_audit.json().get("items", [])
    assert any(it["action"] == "contract.create" for it in items)


async def test_hash_chain_is_continuous(client, auth_headers_admin):
    """Arrange: trigger multiple events. Act: fetch + verify. Assert: continuous."""
    # Arrange — generate some events via several creations
    for i in range(3):
        await client.post(
            "/api/v1/contracts",
            json={
                "title": f"連鎖テスト {i}",
                "contract_type": "ukeoi",
                "counterparty": "Y建設",
                "department_id": 1,
            },
            headers=auth_headers_admin,
        )

    # Act
    r = await client.get("/api/v1/audit-logs?limit=50", headers=auth_headers_admin)
    assert r.status_code == 200
    items = r.json().get("items", [])
    # Order by id ascending
    items = sorted(items, key=lambda x: x["id"])

    # Assert: each row's prev_hash equals previous row's hash_chain
    assert len(items) >= 3
    for prev, cur in itertools.pairwise(items):
        assert cur["prev_hash"] == prev["hash_chain"]


async def test_verify_endpoint_returns_ok(client, auth_headers_admin):
    """Arrange: existing chain. Act: POST verify. Assert: ok=True."""
    # Arrange / Act
    r = await client.post("/api/v1/audit-logs/verify", headers=auth_headers_admin)
    # Assert
    assert r.status_code == 200
    assert r.json().get("ok") is True
