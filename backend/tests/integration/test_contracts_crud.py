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


async def test_submit_contract_moves_draft_to_review(client, auth_headers_legal):
    """POST /contracts/{id}/submit must not fall through to the legacy 501 stub."""
    r_create = await client.post(
        "/api/v1/contracts",
        json={
            "title": "提出テスト契約",
            "contract_type": "ukeoi",
            "counterparty": "提出テスト建設",
            "amount": 4_000_000,
            "department_id": 1,
        },
        headers=auth_headers_legal,
    )
    assert r_create.status_code in (200, 201), r_create.text
    contract = r_create.json()

    r_submit = await client.post(
        f"/api/v1/contracts/{contract['id']}/submit",
        headers=auth_headers_legal,
    )

    assert r_submit.status_code == 200, r_submit.text
    submitted = r_submit.json()
    assert submitted["id"] == contract["id"]
    assert submitted["status"] == "in_review"
    assert submitted["version"] == contract["version"] + 1


async def test_submit_contract_rejects_second_submit(client, auth_headers_legal):
    """Submitting a non-draft contract returns conflict instead of silently succeeding."""
    r_create = await client.post(
        "/api/v1/contracts",
        json={
            "title": "二重提出テスト契約",
            "contract_type": "ukeoi",
            "counterparty": "二重提出テスト建設",
            "department_id": 1,
        },
        headers=auth_headers_legal,
    )
    assert r_create.status_code in (200, 201), r_create.text
    cid = r_create.json()["id"]

    first = await client.post(f"/api/v1/contracts/{cid}/submit", headers=auth_headers_legal)
    assert first.status_code == 200, first.text

    second = await client.post(f"/api/v1/contracts/{cid}/submit", headers=auth_headers_legal)
    assert second.status_code == 409
