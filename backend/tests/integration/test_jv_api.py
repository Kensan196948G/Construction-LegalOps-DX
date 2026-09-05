"""JV 管理 API の統合テスト（#61〜#70）."""

from __future__ import annotations

from typing import Any

JV = "/api/v1/joint-ventures"


async def test_jv_full_lifecycle(
    client: Any, auth_headers_admin: dict[str, str], auth_headers_legal: dict[str, str]
) -> None:
    """登録 → 構成員 → 協定書 → 紛争 → 完了 → 清算."""
    r1 = await client.post(
        f"{JV}",
        json={"name": "統合テスト JV（デモ）", "representative_name": "デモ建設（代表）"},
        headers=auth_headers_admin,
    )
    assert r1.status_code == 201, r1.text
    jv = r1.json()
    assert jv["jv_no"].startswith("JV-")
    assert jv["status"] == "prospecting"
    jv_id = jv["id"]

    # 構成員（代表 60% + 構成員 40%）
    r_m1 = await client.post(
        f"{JV}/{jv_id}/members",
        json={"company_name": "デモ建設（代表）", "role": "representative", "equity_ratio": 60.0},
        headers=auth_headers_admin,
    )
    assert r_m1.status_code == 201, r_m1.text
    r_m2 = await client.post(
        f"{JV}/{jv_id}/members",
        json={"company_name": "デモ土木（構成員）", "equity_ratio": 40.0},
        headers=auth_headers_admin,
    )
    assert r_m2.status_code == 201

    # 代表重複は 409
    r_m3 = await client.post(
        f"{JV}/{jv_id}/members",
        json={"company_name": "重複代表（デモ）", "role": "representative"},
        headers=auth_headers_admin,
    )
    assert r_m3.status_code == 409

    # 出資比率超過は 422
    r_m4 = await client.post(
        f"{JV}/{jv_id}/members",
        json={"company_name": "超過（デモ）", "equity_ratio": 10.0},
        headers=auth_headers_admin,
    )
    assert r_m4.status_code == 422

    # 協定書（signed）
    r_a = await client.post(
        f"{JV}/{jv_id}/agreements",
        json={"title": "JV 協定書（デモ）", "signed_at": "2026-09-05"},
        headers=auth_headers_admin,
    )
    assert r_a.status_code == 201
    assert r_a.json()["status"] == "signed"

    # 紛争
    r_d = await client.post(
        f"{JV}/{jv_id}/disputes",
        json={
            "title": "精算金額の協議（デモ）",
            "claimant_name": "デモ土木",
            "amount_claimed_jpy": 500_000,
        },
        headers=auth_headers_legal,
    )
    assert r_d.status_code == 201
    assert r_d.json()["dispute_no"].startswith("JVD-")

    # 完了前の清算は 409
    r_s_early = await client.post(
        f"{JV}/{jv_id}/settlements",
        json={"title": "早期清算（デモ）", "settlement_amount_jpy": 100},
        headers=auth_headers_admin,
    )
    assert r_s_early.status_code == 409

    # active → completed
    r_st = await client.post(
        f"{JV}/{jv_id}/status", json={"status": "active"}, headers=auth_headers_admin
    )
    assert r_st.status_code == 200
    r_st2 = await client.post(
        f"{JV}/{jv_id}/status", json={"status": "completed"}, headers=auth_headers_admin
    )
    assert r_st2.status_code == 200

    # 清算
    r_s = await client.post(
        f"{JV}/{jv_id}/settlements",
        json={"title": "JV 清算（デモ）", "settlement_amount_jpy": 3_000_000},
        headers=auth_headers_admin,
    )
    assert r_s.status_code == 201
    settlement_id = r_s.json()["id"]
    r_settle = await client.post(
        f"{JV}/settlements/{settlement_id}/settle", headers=auth_headers_admin
    )
    assert r_settle.status_code == 200
    assert r_settle.json()["status"] == "settled"

    # 一覧・ダッシュボード
    r_list = await client.get(f"{JV}", headers=auth_headers_admin)
    assert r_list.status_code == 200
    assert r_list.json()["total"] >= 1
    r_dash = await client.get(f"{JV}/dashboard/summary", headers=auth_headers_admin)
    assert r_dash.status_code == 200
    assert r_dash.json()["agreements_signed"] >= 1
