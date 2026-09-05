"""公共工事特化 API の統合テスト（#41-#43・#54-#57・#60）."""

from __future__ import annotations

from typing import Any

PW = "/api/v1/public-works"


async def test_agency_and_dashboard(
    client: Any, auth_headers_admin: dict[str, str]
) -> None:
    """#41/#42 機関登録 → 一覧 → #60 ダッシュボード集計."""
    r1 = await client.post(
        f"{PW}/contracting-agencies",
        json={
            "code": "AG-INT-001",
            "name": "統合テスト発注機関（デモ）",
            "agency_type": "prefectural",
            "prefecture": "東京都",
            "payment_deadline_days": 50,
            "advance_payment_ratio": 0.4,
            "requires_slide_clause": True,
        },
        headers=auth_headers_admin,
    )
    assert r1.status_code == 201, r1.text
    body = r1.json()
    assert body["agency_type"] == "prefectural"
    assert body["requires_slide_clause"] is True

    r_list = await client.get(
        f"{PW}/contracting-agencies",
        params={"agency_type": "prefectural"},
        headers=auth_headers_admin,
    )
    assert r_list.status_code == 200
    assert r_list.json()["total"] >= 1

    # 重複コードは 409
    r_dup = await client.post(
        f"{PW}/contracting-agencies",
        json={"code": "AG-INT-001", "name": "重複（デモ）", "agency_type": "national"},
        headers=auth_headers_admin,
    )
    assert r_dup.status_code == 409

    r_dash = await client.get(f"{PW}/dashboard", headers=auth_headers_admin)
    assert r_dash.status_code == 200
    assert r_dash.json()["agencies_active"] >= 1


async def test_notification_and_consultation_flow(
    client: Any, auth_headers_admin: dict[str, str], auth_headers_legal: dict[str, str]
) -> None:
    """#54 通知（登録→notify）と #55 協議（申出→回答）のライフサイクル."""
    # 通知
    r_n = await client.post(
        f"{PW}/notifications",
        json={
            "notification_type": "delay",
            "title": "工期遅延通知（統合テスト・デモ）",
            "due_date": "2026-12-31",
        },
        headers=auth_headers_legal,
    )
    assert r_n.status_code == 201, r_n.text
    notif = r_n.json()
    assert notif["notification_no"].startswith("ON-")
    assert notif["status"] == "open"

    r_notify = await client.post(
        f"{PW}/notifications/{notif['id']}/notify", headers=auth_headers_legal
    )
    assert r_notify.status_code == 200
    assert r_notify.json()["status"] == "notified"

    r_notify2 = await client.post(
        f"{PW}/notifications/{notif['id']}/notify", headers=auth_headers_legal
    )
    assert r_notify2.status_code == 409

    # 協議
    r_c = await client.post(
        f"{PW}/consultations",
        json={
            "consultation_type": "extension_of_time",
            "title": "工期延伸協議（統合テスト・デモ）",
            "claimed_days": 30,
            "due_date": "2026-11-30",
        },
        headers=auth_headers_legal,
    )
    assert r_c.status_code == 201, r_c.text
    consult = r_c.json()
    assert consult["consultation_no"].startswith("PW-")
    assert consult["status"] == "open"

    r_resp = await client.post(
        f"{PW}/consultations/{consult['id']}/respond",
        json={"response_note": "20 日の延伸を承認（デモ回答）", "resolved_days": 20},
        headers=auth_headers_admin,
    )
    assert r_resp.status_code == 200
    assert r_resp.json()["status"] == "responded"
    assert r_resp.json()["resolved_days"] == 20

    r_resp2 = await client.post(
        f"{PW}/consultations/{consult['id']}/respond",
        json={"response_note": "2 回目（デモ）"},
        headers=auth_headers_admin,
    )
    assert r_resp2.status_code == 409

    # 一覧
    r_lc = await client.get(
        f"{PW}/consultations",
        params={"type": "extension_of_time"},
        headers=auth_headers_admin,
    )
    assert r_lc.status_code == 200
    assert r_lc.json()["total"] >= 1

    # 不正種別 422
    r_bad = await client.post(
        f"{PW}/consultations",
        json={"consultation_type": "bogus", "title": "不正（デモ）"},
        headers=auth_headers_admin,
    )
    assert r_bad.status_code == 422


async def test_standard_clause_check_endpoint(
    client: Any, auth_headers_admin: dict[str, str]
) -> None:
    """#43 約款差分チェック（契約未指定・存在しない契約は 404）."""
    r = await client.get(
        f"{PW}/standard-clause-check",
        params={"contract_id": 999_999},
        headers=auth_headers_admin,
    )
    assert r.status_code == 404
