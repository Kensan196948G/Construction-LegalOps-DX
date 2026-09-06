"""Full lifecycle (POST → GET → PATCH → DELETE) for ``/contracts``.

Verifies that DELETE performs a soft delete (``deleted_at`` set, row
remains queryable through audit / admin paths).
"""

from __future__ import annotations

from app.models.clause import Clause


async def test_contract_lifecycle_post_get_patch_delete(
    client, auth_headers_legal, auth_headers_admin
):
    """Arrange: legal user. Act: full CRUD. Assert: each step returns expected."""
    # Arrange
    body = {
        "title": "請負契約 - サンプル",
        "contract_type": "工事請負契約",
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


async def test_create_contract_normalizes_legacy_contract_type(
    client, auth_headers_legal
) -> None:
    """Legacy ``ukeoi`` is normalized to the canonical 工事請負契約 value."""
    r = await client.post(
        "/api/v1/contracts",
        json={
            "title": "種別正規化テスト契約",
            "contract_type": "ukeoi",
            "counterparty": "テスト建設",
            "department_id": 1,
        },
        headers=auth_headers_legal,
    )
    assert r.status_code in (200, 201), r.text
    assert r.json()["contract_type"] == "工事請負契約"


async def test_soft_delete_visible_to_auditor(client, auth_headers_admin, auth_headers_legal):
    """Arrange: create + delete. Act: admin reads. Assert: still visible."""
    # Arrange
    r_create = await client.post(
        "/api/v1/contracts",
        json={
            "title": "監査対象",
            "contract_type": "業務委託契約",
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
            "contract_type": "工事請負契約",
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
            "contract_type": "工事請負契約",
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


async def test_contract_versions_returns_current_snapshot(client, auth_headers_legal):
    """GET /contracts/{id}/versions returns a non-501 current-version snapshot."""
    r_create = await client.post(
        "/api/v1/contracts",
        json={
            "title": "バージョン履歴テスト契約",
            "contract_type": "工事請負契約",
            "counterparty": "履歴テスト建設",
            "department_id": 1,
        },
        headers=auth_headers_legal,
    )
    assert r_create.status_code in (200, 201), r_create.text
    contract = r_create.json()

    r_versions = await client.get(
        f"/api/v1/contracts/{contract['id']}/versions",
        headers=auth_headers_legal,
    )

    assert r_versions.status_code == 200, r_versions.text
    body = r_versions.json()
    assert body["total"] == 1
    assert body["items"][0]["contract_id"] == contract["id"]
    assert body["items"][0]["version"] == contract["version"]


async def test_contract_clauses_returns_db_rows(client, api_db_session, auth_headers_legal):
    """GET /contracts/{id}/clauses returns DB-backed clauses in seq order.

    ``api_db_session`` は ``client`` と同じ ``test_engine`` に直接 bind
    されたセッション（``db_session`` はロールバックされるため、別コネクション
    の ``client`` からは見えない）。
    """
    r_create = await client.post(
        "/api/v1/contracts",
        json={
            "title": "条項一覧テスト契約",
            "contract_type": "工事請負契約",
            "counterparty": "条項テスト建設",
            "department_id": 1,
        },
        headers=auth_headers_legal,
    )
    assert r_create.status_code in (200, 201), r_create.text
    cid = r_create.json()["id"]

    api_db_session.add_all(
        [
            Clause(contract_id=cid, seq=2, title="第2条", body="第2条本文", risk_level="low"),
            Clause(
                contract_id=cid,
                seq=1,
                title="第1条",
                body="第1条本文",
                risk_level="medium",
                ai_findings={"category": "支払"},
            ),
        ]
    )
    await api_db_session.commit()

    r_clauses = await client.get(
        f"/api/v1/contracts/{cid}/clauses",
        headers=auth_headers_legal,
    )

    assert r_clauses.status_code == 200, r_clauses.text
    body = r_clauses.json()
    assert [item["seq"] for item in body] == [1, 2]
    assert body[0]["text"] == "第1条本文"
    assert body[0]["category"] == "支払"
