"""Audit log integration tests.

Validates that:

* every state-changing operation appends an ``audit_logs`` row
* ``hash_chain`` is contiguous (each row's prev_hash == previous row's hash)
* ``POST /api/v1/audit-logs/verify`` confirms the chain
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Audit logs API implemented in Loop 3")


async def test_audit_log_created_on_contract_create(client, auth_headers_legal):
    """Arrange: client. Act: create contract. Assert: an audit row exists."""
    # Arrange
    r = await client.post(
        "/api/v1/contracts",
        json={
            "title": "監査テスト",
            "contract_type": "ukeoi",
            "counterparty_name": "監査",
        },
        headers=auth_headers_legal,
    )
    cid = r.json()["id"]

    # Act
    r_audit = await client.get(
        f"/api/v1/audit-logs?target_type=contracts&target_id={cid}",
        headers=auth_headers_legal,
    )
    # Assert
    assert r_audit.status_code == 200
    items = r_audit.json().get("items") or r_audit.json()
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
                "counterparty_name": "Y",
            },
            headers=auth_headers_admin,
        )

    # Act
    r = await client.get("/api/v1/audit-logs?limit=50", headers=auth_headers_admin)
    items = r.json().get("items") or r.json()
    # Order by id ascending
    items = sorted(items, key=lambda x: x["id"])

    # Assert: each row's prev_hash equals previous row's hash_chain
    for prev, cur in zip(items, items[1:]):  # noqa: B905, RUF007
        assert cur["prev_hash"] == prev["hash_chain"]


async def test_verify_endpoint_returns_ok(client, auth_headers_admin):
    """Arrange: existing chain. Act: POST verify. Assert: ok=True."""
    # Arrange / Act
    r = await client.post("/api/v1/audit-logs/verify", headers=auth_headers_admin)
    # Assert
    assert r.status_code == 200
    assert r.json().get("ok") is True
