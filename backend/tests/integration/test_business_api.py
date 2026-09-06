"""高優先業務機能（紛争・変更契約・協力会社・文書パッケージ・支払）の API 統合テスト."""

from __future__ import annotations

import uuid

_SUFFIX = uuid.uuid4().hex[:8]


async def _create_contract(client, headers) -> int:
    r = await client.post(
        "/api/v1/contracts",
        json={
            "title": f"業務機能統合テスト契約-{_SUFFIX}",
            "contract_type": "請負",
            "counterparty": "テスト発注者株式会社",
            "amount": 10000000,
            "department_id": 1,
            "order_date": "2026-02-01",
            "receipt_date": "2026-03-01",
            "inspection_date": "2026-03-15",
        },
        headers=headers,
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


async def test_dispute_lifecycle(client, auth_headers_admin):
    contract_id = await _create_contract(client, auth_headers_admin)
    r = await client.post(
        "/api/v1/disputes",
        json={
            "contract_id": contract_id,
            "dispute_type": "claim",
            "title": f"追加工事費の請求紛争-{_SUFFIX}",
            "counterparty": f"テスト発注者株式会社-{_SUFFIX}",
            "amount_claimed_jpy": 5000000,
            "reserve_amount_jpy": 3000000,
            "status": "open",
            "priority": "高",
        },
        headers=auth_headers_admin,
    )
    assert r.status_code == 201, r.text
    dispute_id = r.json()["id"]
    assert r.json()["dispute_no"].startswith("D-")

    r_list = await client.get("/api/v1/disputes", headers=auth_headers_admin)
    assert r_list.status_code == 200
    assert r_list.json()["total"] >= 1

    r_patch = await client.patch(
        f"/api/v1/disputes/{dispute_id}",
        json={"status": "resolved"},
        headers=auth_headers_admin,
    )
    assert r_patch.status_code == 200
    assert r_patch.json()["status"] == "resolved"

    r_event = await client.post(
        f"/api/v1/disputes/{dispute_id}/timeline",
        json={"event_type": "fact", "description": "和解案を受領"},
        headers=auth_headers_admin,
    )
    assert r_event.status_code == 201

    r_evidence = await client.post(
        f"/api/v1/disputes/{dispute_id}/evidence",
        json={
            "evidence_type": "minutes",
            "description": "協議議事録",
            "preserved": True,
        },
        headers=auth_headers_admin,
    )
    assert r_evidence.status_code == 201
    assert r_evidence.json()["preserved"] is True

    r_exp = await client.get("/api/v1/disputes/exposure", headers=auth_headers_admin)
    assert r_exp.status_code == 200
    assert r_exp.json()["total_claimed_jpy"] == 5000000


async def test_dispute_access_scoped_to_contract_acl(
    client, auth_headers_admin, auth_headers_site, auth_headers_legal
):
    """Issue #127/#129: 紛争案件の取得・一覧・更新は案件（契約）ACLでスコープされる。

    ACL の付与がない別ロールのユーザーは、一覧に他部門の紛争案件が表示されず、
    直接の更新も403で拒否される。契約の drafter 本人と admin は引き続き見える。
    """
    contract_id = await _create_contract(client, auth_headers_site)
    r = await client.post(
        "/api/v1/disputes",
        json={
            "contract_id": contract_id,
            "dispute_type": "claim",
            "title": f"ACLスコープテスト紛争-{_SUFFIX}",
        },
        headers=auth_headers_site,
    )
    assert r.status_code == 201, r.text
    dispute_id = r.json()["id"]

    r_list_outsider = await client.get("/api/v1/disputes", headers=auth_headers_legal)
    assert r_list_outsider.status_code == 200
    assert dispute_id not in [item["id"] for item in r_list_outsider.json()["items"]]

    r_patch_outsider = await client.patch(
        f"/api/v1/disputes/{dispute_id}",
        json={"status": "resolved"},
        headers=auth_headers_legal,
    )
    assert r_patch_outsider.status_code == 403

    r_list_owner = await client.get("/api/v1/disputes", headers=auth_headers_site)
    assert r_list_owner.status_code == 200
    assert dispute_id in [item["id"] for item in r_list_owner.json()["items"]]

    r_list_admin = await client.get("/api/v1/disputes", headers=auth_headers_admin)
    assert r_list_admin.status_code == 200
    assert dispute_id in [item["id"] for item in r_list_admin.json()["items"]]


async def test_change_order_lifecycle_and_impact(client, auth_headers_admin):
    contract_id = await _create_contract(client, auth_headers_admin)
    r = await client.post(
        "/api/v1/change-orders",
        params={"contract_id": contract_id},
        json={
            "change_type": "additional_work",
            "title": "追加工事（土量増）",
            "requested_at": "2026-08-01",
            "amount_jpy": 2000000,
            "status": "registered",
        },
        headers=auth_headers_admin,
    )
    assert r.status_code == 201, r.text
    order_id = r.json()["id"]
    assert r.json()["response_deadline"] == "2026-08-15"

    r_patch = await client.patch(
        f"/api/v1/change-orders/{order_id}",
        json={"status": "approved"},
        headers=auth_headers_admin,
    )
    assert r_patch.status_code == 200
    assert r_patch.json()["cumulative_after_jpy"] == 12000000

    r_impact = await client.get(
        "/api/v1/change-orders/impact/" + str(contract_id),
        headers=auth_headers_admin,
    )
    assert r_impact.status_code == 200
    assert r_impact.json()["cumulative_after_jpy"] == 12000000


async def test_partner_lifecycle_and_summary(client, auth_headers_admin):
    r = await client.post(
        "/api/v1/partners",
        json={
            "name": f"統合テスト土木株式会社-{_SUFFIX}",
            "partner_type": "下請",
            "permit_number": "(般) 99-9999",
            "anti_social_check": "unconfirmed",
        },
        headers=auth_headers_admin,
    )
    assert r.status_code == 201, r.text
    assert r.json()["risk_level"] == "high"
    assert any(x["code"] == "antisocial_unconfirmed" for x in r.json()["risk_reasons"])

    r_list = await client.get("/api/v1/partners?q=統合テスト", headers=auth_headers_admin)
    assert r_list.status_code == 200
    assert r_list.json()["total"] >= 1

    r_summary = await client.get("/api/v1/partners/summary", headers=auth_headers_admin)
    assert r_summary.status_code == 200
    assert r_summary.json()["total"] >= 1
    assert r_summary.json()["antisocial_unconfirmed"] >= 1


async def test_document_package_and_consistency(client, auth_headers_admin):
    contract_id = await _create_contract(client, auth_headers_admin)
    r1 = await client.post(
        f"/api/v1/contracts/{contract_id}/documents",
        json={
            "doc_type": "contract",
            "title": "工事請負契約書",
            "priority": 1,
            "amount_jpy": 10000000,
            "start_date": "2026-08-01",
            "end_date": "2026-12-31",
            "content": "請負代金 10,000,000 円。別紙仕様書による。",
        },
        headers=auth_headers_admin,
    )
    assert r1.status_code == 201, r1.text

    r2 = await client.post(
        f"/api/v1/contracts/{contract_id}/documents",
        json={
            "doc_type": "quotation",
            "title": "見積書",
            "priority": 5,
            "amount_jpy": 13000000,
            "content": "見積金額 13,000,000 円",
        },
        headers=auth_headers_admin,
    )
    assert r2.status_code == 201, r2.text

    r_check = await client.get(
        f"/api/v1/contracts/{contract_id}/documents/consistency",
        headers=auth_headers_admin,
    )
    assert r_check.status_code == 200
    body = r_check.json()
    assert body["overall_status"] in {"pass", "warning", "fail"}
    assert any(f["code"] == "document_amount_mismatch" for f in body["findings"])


async def test_payment_compliance_endpoint(client, auth_headers_admin):
    contract_id = await _create_contract(client, auth_headers_admin)
    r = await client.get(
        f"/api/v1/contracts/{contract_id}/payment-compliance",
        headers=auth_headers_admin,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["contract_id"] == contract_id
    assert body["law_version"] == "toritekihou"
    assert body["applicable_threshold_days"] == 60


async def test_business_endpoints_require_auth(client):
    for method, url in (
        ("GET", "/api/v1/disputes"),
        ("GET", "/api/v1/partners"),
        ("GET", "/api/v1/change-orders"),
    ):
        r = await client.request(method, url)
        assert r.status_code == 401
