"""価格協議・ダンピング警告 API の統合テスト（#21/#23/#24）."""

from __future__ import annotations

from typing import Any

PC = "/api/v1/price-consultations"
LW = "/api/v1/labor-wage"


async def _seed_standard(client: Any, headers: dict[str, str], amount: int = 20_000) -> None:
    await client.post(
        f"{LW}/standards",
        json={
            "work_type": "土木",
            "amount_jpy": amount,
            "prefecture": "東京都",
            "effective_from": "2026-01-01",
            "source_ref": "2026年1月基準",
        },
        headers=headers,
    )


async def test_dumping_check_returns_severity(
    client: Any, auth_headers_admin: dict[str, str]
) -> None:
    """#21: /labor-wage/discrepancy が severity / dumping を含む."""
    await _seed_standard(client, auth_headers_admin, amount=20_000)
    r = await client.get(
        f"{LW}/discrepancy",
        params={"work_type": "土木", "prefecture": "東京都", "quote_day_jpy": 15_000},
        headers=auth_headers_admin,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "below"
    assert body["severity"] == "critical"
    assert body["dumping"] is True


async def test_consultation_crud_and_monitor(
    client: Any, auth_headers_admin: dict[str, str]
) -> None:
    """#24 協議申出 → 一覧 → 回答 → #23 監視（未回答のみ）."""
    await _seed_standard(client, auth_headers_admin, amount=20_000)

    r1 = await client.post(
        f"{PC}",
        json={
            "direction": "from_subcontractor",
            "work_type": "土木",
            "prefecture": "東京都",
            "quote_day_jpy": 15_000,
            "summary": "単価引上げ協議の申出（デモ）",
            "request_detail": "労務費上昇に伴う単価見直し（架空）",
            "requested_at": "2026-02-01",
        },
        headers=auth_headers_admin,
    )
    assert r1.status_code == 201, r1.text
    body = r1.json()
    assert body["log_no"].startswith("LC-")
    assert body["status"] == "open"
    assert body["severity"] == "critical"
    assert body["standard_day_jpy"] == 20_000
    log_id = body["id"]

    # 一覧（契約なし・全件）
    r_list = await client.get(f"{PC}", headers=auth_headers_admin)
    assert r_list.status_code == 200
    assert r_list.json()["total"] >= 1

    # 詳細
    r_get = await client.get(f"{PC}/{log_id}", headers=auth_headers_admin)
    assert r_get.status_code == 200
    assert r_get.json()["id"] == log_id

    # #23 監視: 未回答の深刻な協議がヒット
    r_mon = await client.get(
        f"{PC}/monitor/quote-changes",
        params={"severity": "critical"},
        headers=auth_headers_admin,
    )
    assert r_mon.status_code == 200
    assert r_mon.json()["total"] >= 1

    # 回答（open → responded）
    r_resp = await client.post(
        f"{PC}/{log_id}/respond",
        json={"response_summary": "協議内容を確認し、社内で検討します（デモ回答）。"},
        headers=auth_headers_admin,
    )
    assert r_resp.status_code == 200
    assert r_resp.json()["status"] == "responded"
    assert r_resp.json()["responded_at"] is not None

    # responded への再回答は 409
    r_resp2 = await client.post(
        f"{PC}/{log_id}/respond",
        json={"response_summary": "2回目の回答（デモ）"},
        headers=auth_headers_admin,
    )
    assert r_resp2.status_code == 409

    # #23 監視: 回答済みは open でないためヒットしない
    r_mon2 = await client.get(f"{PC}/monitor/quote-changes", headers=auth_headers_admin)
    assert r_mon2.status_code == 200
    assert all(i["status"] == "open" for i in r_mon2.json()["items"])


async def test_consultation_cancel(
    client: Any, auth_headers_legal: dict[str, str]
) -> None:
    """#24 取下げ（open → cancelled）と、取下げ後の回答 409."""
    r = await client.post(
        f"{PC}",
        json={
            "direction": "to_subcontractor",
            "work_type": "舗装",
            "summary": "価格確認（デモ・取下げ用）",
        },
        headers=auth_headers_legal,
    )
    assert r.status_code == 201
    log_id = r.json()["id"]

    r_cancel = await client.post(
        f"{PC}/{log_id}/cancel",
        json={"reason": "協議取下げ（デモ）"},
        headers=auth_headers_legal,
    )
    assert r_cancel.status_code == 200
    assert r_cancel.json()["status"] == "cancelled"

    r_resp = await client.post(
        f"{PC}/{log_id}/respond",
        json={"response_summary": "取消後の回答（デモ）"},
        headers=auth_headers_legal,
    )
    assert r_resp.status_code == 409


async def test_consultation_validation(
    client: Any, auth_headers_admin: dict[str, str]
) -> None:
    """不正 direction / 負単価は 422."""
    r_bad_dir = await client.post(
        f"{PC}",
        json={"direction": "bogus", "work_type": "土木", "summary": "不正"},
        headers=auth_headers_admin,
    )
    assert r_bad_dir.status_code == 422

    r_neg = await client.post(
        f"{PC}",
        json={
            "direction": "from_subcontractor",
            "work_type": "土木",
            "quote_day_jpy": -5,
            "summary": "不正",
        },
        headers=auth_headers_admin,
    )
    assert r_neg.status_code == 422
