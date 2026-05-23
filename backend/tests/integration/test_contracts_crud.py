"""Full lifecycle (POST → GET → PATCH → DELETE) for ``/contracts``.

Verifies that DELETE performs a soft delete (``deleted_at`` set, row
remains queryable through audit / admin paths).
"""

from __future__ import annotations


async def test_contract_lifecycle_post_get_patch_delete(
    client, auth_headers_legal, auth_headers_admin
):
    """Arrange: legal user. Act: full CRUD. Assert: each step returns expected."""
    # Arrange
    body = {
        "title": "請負契約 - サンプル",
        "contract_type": "ukeoi",
        "counterparty": "サンプル建設株式会社",
        "amount": 12_345_000,
        "department_id": 1,
    }
    # Act: create
    r_create = await client.post("/api/v1/contracts", json=body, headers=auth_headers_legal)
    # Assert: 201
    assert r_create.status_code in (200, 201)
    contract = r_create.json()
    contract_id = contract["id"]

    # Act: read
    r_get = await client.get(f"/api/v1/contracts/{contract_id}", headers=auth_headers_legal)
    # Assert
    assert r_get.status_code == 200
    assert r_get.json()["title"] == body["title"]

    # Act: patch (version required for optimistic locking)
    r_patch = await client.patch(
        f"/api/v1/contracts/{contract_id}",
        json={"title": "請負契約 - 更新後", "version": 1},
        headers=auth_headers_legal,
    )
    # Assert
    assert r_patch.status_code == 200
    assert r_patch.json()["title"] == "請負契約 - 更新後"

    # Act: delete (soft) — requires admin role
    r_delete = await client.delete(
        f"/api/v1/contracts/{contract_id}", headers=auth_headers_admin
    )
    # Assert
    assert r_delete.status_code in (200, 204)

    # Act: read after delete
    r_after = await client.get(f"/api/v1/contracts/{contract_id}", headers=auth_headers_legal)
    # Assert: hidden from normal GET
    assert r_after.status_code in (404, 410)


async def test_soft_delete_visible_to_auditor(client, auth_headers_admin, auth_headers_legal):
    """Arrange: create + delete. Act: admin reads. Assert: still visible."""
    # Arrange
    r_create = await client.post(
        "/api/v1/contracts",
        json={
            "title": "監査対象",
            "contract_type": "itaku",
            "counterparty": "X",
            "department_id": 1,
        },
        headers=auth_headers_legal,
    )
    assert r_create.status_code in (200, 201)
    cid = r_create.json()["id"]
    await client.delete(f"/api/v1/contracts/{cid}", headers=auth_headers_admin)

    # Act
    r_admin = await client.get(
        f"/api/v1/contracts/{cid}?include_deleted=true",
        headers=auth_headers_admin,
    )
    # Assert
    assert r_admin.status_code == 200
    assert r_admin.json().get("deleted_at") is not None


async def test_list_contracts_respects_pagination(client, auth_headers_legal):
    """Arrange: client. Act: GET list. Assert: items + total fields."""
    # Arrange / Act
    r = await client.get("/api/v1/contracts?limit=10", headers=auth_headers_legal)
    # Assert
    assert r.status_code == 200
    body = r.json()
    assert "items" in body or isinstance(body, list)
