"""フロント↔バックエンド契約整合の 2026-09-28 修正に対する統合テスト.

対象:
- ``GET /risks/heatmap``                     … 405 だった（frontend ``risksApi.heatmap``）
- ``GET /disputes/{id}``                     … 405 だった（frontend ``disputesApi.get``）
- ``GET /change-orders/{id}/evidence``       … 405 だった（frontend ``changeOrdersApi.evidence``）

いずれも frontend が呼んでいるのに backend に GET が無く、画面がデータを
表示できなかった（MVP backend 実測で 405）。
"""

from __future__ import annotations

import uuid

_SUFFIX = uuid.uuid4().hex[:8]


async def _create_contract(client, headers, *, title: str) -> int:
    r = await client.post(
        "/api/v1/contracts",
        json={
            "title": title,
            "contract_type": "工事請負契約",
            "counterparty": "契約整合テスト株式会社",
            "department_id": 1,
        },
        headers=headers,
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
# GET /risks/heatmap
# ---------------------------------------------------------------------------


async def test_heatmap_requires_authentication(client):
    r = await client.get("/api/v1/risks/heatmap")
    assert r.status_code == 401


async def test_heatmap_returns_matrix_in_frontend_shape(client, auth_headers_admin):
    """frontend ``riskHeatmapSchema`` = ``{matrix: [{probability, impact, count}]}``."""
    r = await client.get("/api/v1/risks/heatmap", headers=auth_headers_admin)
    assert r.status_code == 200, r.text

    body = r.json()
    assert set(body.keys()) == {"matrix"}
    assert isinstance(body["matrix"], list)

    # DB の CHECK 制約（ck_risk_probability / ck_risk_impact）の値域に収まること。
    # frontend の riskLevelEnum は low/medium/high/critical の上位集合なので
    # この 3 値はそのまま通り、frontend スキーマを緩める必要はない。
    for cell in body["matrix"]:
        assert set(cell.keys()) == {"probability", "impact", "count"}
        assert cell["probability"] in {"low", "medium", "high"}
        assert cell["impact"] in {"low", "medium", "high"}
        assert isinstance(cell["count"], int)
        assert cell["count"] > 0  # 0 件のセルは返さない


async def test_heatmap_matrix_total_matches_risks_list_total(
    client, api_db_session, auth_headers_admin, auth_headers_site
):
    """heatmap の合計件数が一覧 API の ``total`` と一致する（可視性スコープの固定）.

    ``GET /risks`` は ``risk_service.list_risks`` の可視性ルール
    （admin/legal/auditor/reviewer/approver は全件、それ以外は自分が起案した
    契約のみ）でスコープされる。heatmap は api 層で同じ条件を再実装しているため、
    非特権ビューアでも両者が一致することをここで固定する（drift 検出）。
    """
    from app.models.risk_item import RiskItem

    site_contract_id = await _create_contract(
        client, auth_headers_site, title=f"heatmap スコープ契約(site)-{_SUFFIX}"
    )
    admin_contract_id = await _create_contract(
        client, auth_headers_admin, title=f"heatmap スコープ契約(admin)-{_SUFFIX}"
    )

    api_db_session.add_all(
        [
            RiskItem(
                contract_id=site_contract_id,
                category="payment",
                severity="high",
                probability="high",
                impact="medium",
                description="site 起案契約のリスク",
                status="open",
            ),
            RiskItem(
                contract_id=admin_contract_id,
                category="legal",
                severity="medium",
                probability="low",
                impact="high",
                description="admin 起案契約のリスク",
                status="open",
            ),
        ]
    )
    await api_db_session.commit()

    async def _totals(headers) -> tuple[int, int]:
        list_res = await client.get("/api/v1/risks?page=1&size=1", headers=headers)
        assert list_res.status_code == 200, list_res.text
        heat_res = await client.get("/api/v1/risks/heatmap", headers=headers)
        assert heat_res.status_code == 200, heat_res.text
        matrix_total = sum(c["count"] for c in heat_res.json()["matrix"])
        return list_res.json()["total"], matrix_total

    admin_list_total, admin_matrix_total = await _totals(auth_headers_admin)
    site_list_total, site_matrix_total = await _totals(auth_headers_site)

    assert admin_matrix_total == admin_list_total
    assert site_matrix_total == site_list_total
    # 非特権ビューアは自分が起案した契約の分だけが見える（スコープが効いている）
    assert site_matrix_total >= 1
    assert admin_matrix_total > site_matrix_total


# ---------------------------------------------------------------------------
# GET /disputes/{id}
# ---------------------------------------------------------------------------


async def _create_dispute(client, headers, *, contract_id: int, title: str) -> int:
    r = await client.post(
        "/api/v1/disputes",
        json={
            "contract_id": contract_id,
            "dispute_type": "claim",
            "title": title,
            "counterparty": "契約整合テスト株式会社",
            "amount_claimed_jpy": 1000000,
            "status": "open",
            "priority": "中",
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_dispute_detail_returns_frontend_shape(client, auth_headers_admin):
    """frontend ``disputeDetailSchema`` = dispute + timeline[] + evidence[]."""
    contract_id = await _create_contract(
        client, auth_headers_admin, title=f"紛争詳細契約-{_SUFFIX}"
    )
    dispute_id = await _create_dispute(
        client, auth_headers_admin, contract_id=contract_id, title=f"紛争詳細-{_SUFFIX}"
    )

    r_timeline = await client.post(
        f"/api/v1/disputes/{dispute_id}/timeline",
        json={"event_type": "fact", "description": "事実経過"},
        headers=auth_headers_admin,
    )
    assert r_timeline.status_code == 201, r_timeline.text

    r_evidence = await client.post(
        f"/api/v1/disputes/{dispute_id}/evidence",
        json={"evidence_type": "minutes", "description": "議事録", "preserved": True},
        headers=auth_headers_admin,
    )
    assert r_evidence.status_code == 201, r_evidence.text

    r = await client.get(f"/api/v1/disputes/{dispute_id}", headers=auth_headers_admin)
    assert r.status_code == 200, r.text

    body = r.json()
    assert body["id"] == dispute_id
    assert body["dispute_no"].startswith("D-")
    assert isinstance(body["timeline"], list)
    assert isinstance(body["evidence"], list)
    assert [e["description"] for e in body["timeline"]] == ["事実経過"]
    assert body["timeline"][0]["event_type"] == "fact"
    assert body["evidence"][0]["preserved"] is True


async def test_dispute_detail_not_found(client, auth_headers_admin):
    r = await client.get("/api/v1/disputes/999999999", headers=auth_headers_admin)
    assert r.status_code == 404


async def test_dispute_detail_is_contract_acl_scoped(
    client, auth_headers_admin, auth_headers_site, auth_headers_legal
):
    """一覧と同じく、契約 ACL 外のビューアには 403（admin と drafter 本人は 200）."""
    contract_id = await _create_contract(
        client, auth_headers_site, title=f"紛争詳細ACL契約-{_SUFFIX}"
    )
    dispute_id = await _create_dispute(
        client, auth_headers_site, contract_id=contract_id, title=f"紛争詳細ACL-{_SUFFIX}"
    )

    r_owner = await client.get(f"/api/v1/disputes/{dispute_id}", headers=auth_headers_site)
    assert r_owner.status_code == 200, r_owner.text

    r_admin = await client.get(f"/api/v1/disputes/{dispute_id}", headers=auth_headers_admin)
    assert r_admin.status_code == 200, r_admin.text

    r_outsider = await client.get(f"/api/v1/disputes/{dispute_id}", headers=auth_headers_legal)
    assert r_outsider.status_code == 403, r_outsider.text


# ---------------------------------------------------------------------------
# GET /change-orders/{id}/evidence
# ---------------------------------------------------------------------------


async def test_change_order_evidence_list(client, auth_headers_admin):
    contract_id = await _create_contract(
        client, auth_headers_admin, title=f"変更契約証拠契約-{_SUFFIX}"
    )
    r_order = await client.post(
        "/api/v1/change-orders",
        params={"contract_id": contract_id},
        json={
            "change_type": "additional_work",
            "title": f"追加工事-{_SUFFIX}",
            "requested_at": "2026-08-01",
            "amount_jpy": 1000000,
            "status": "registered",
        },
        headers=auth_headers_admin,
    )
    assert r_order.status_code == 201, r_order.text
    order_id = r_order.json()["id"]

    # 空でも 200 + [] （405 ではない）
    r_empty = await client.get(
        f"/api/v1/change-orders/{order_id}/evidence", headers=auth_headers_admin
    )
    assert r_empty.status_code == 200, r_empty.text
    assert r_empty.json() == []

    r_add = await client.post(
        f"/api/v1/change-orders/{order_id}/evidence",
        json={"evidence_type": "daily_report", "description": "作業日報"},
        headers=auth_headers_admin,
    )
    assert r_add.status_code == 201, r_add.text

    r_list = await client.get(
        f"/api/v1/change-orders/{order_id}/evidence", headers=auth_headers_admin
    )
    assert r_list.status_code == 200, r_list.text
    items = r_list.json()
    assert len(items) == 1
    # frontend ``changeOrderEvidenceSchema`` が要求する形
    assert items[0]["change_order_id"] == order_id
    assert items[0]["evidence_type"] == "daily_report"
    assert items[0]["description"] == "作業日報"
    assert "created_at" in items[0]
    assert "updated_at" in items[0]


async def test_change_order_evidence_list_not_found(client, auth_headers_admin):
    r = await client.get(
        "/api/v1/change-orders/999999999/evidence", headers=auth_headers_admin
    )
    assert r.status_code == 404


async def test_change_order_evidence_list_requires_authentication(client):
    r = await client.get("/api/v1/change-orders/1/evidence")
    assert r.status_code == 401
