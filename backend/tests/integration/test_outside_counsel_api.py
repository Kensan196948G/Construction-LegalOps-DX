"""顧問弁護士管理 API の統合テスト（Issue #102）."""

from __future__ import annotations

from typing import Any

OC = "/api/v1/outside-counsel"


async def _firm(client: Any, headers: dict[str, str], name: str) -> int:
    r = await client.post(f"{OC}/firms", json={"firm_name": name}, headers=headers)
    assert r.status_code == 201, r.text
    return int(r.json()["id"])


async def test_engagement_flow_via_api(client: Any, auth_headers_legal: dict[str, str]) -> None:
    """事務所登録 → 弁護士登録 → 依頼 → 回答 → 確認."""
    firm_id = await _firm(client, auth_headers_legal, "APIテスト法律事務所")

    r_lawyer = await client.post(
        f"{OC}/firms/{firm_id}/lawyers",
        json={"firm_id": firm_id, "lawyer_name": "テスト弁護士", "bar_number": "99-99"},
        headers=auth_headers_legal,
    )
    assert r_lawyer.status_code == 201
    lawyer_id = r_lawyer.json()["id"]

    r_eng = await client.post(
        f"{OC}/engagements",
        json={
            "firm_id": firm_id,
            "lawyer_id": lawyer_id,
            "title": "瑕疵担保期間の解釈",
            "question": "瑕疵担保期間の起算点はいつか。",
            "due_date": "2026-10-31",
            "confidential": True,
        },
        headers=auth_headers_legal,
    )
    assert r_eng.status_code == 201, r_eng.text
    body = r_eng.json()
    assert body["engagement_no"].startswith("LEG-")
    assert body["status"] == "open"
    eid = body["id"]

    # 回答待ち一覧フィルタ
    r_list = await client.get(
        f"{OC}/engagements?status=open&firm_id={firm_id}", headers=auth_headers_legal
    )
    assert r_list.status_code == 200
    assert any(i["id"] == eid for i in r_list.json()["items"])

    r_answer = await client.post(
        f"{OC}/engagements/{eid}/answer",
        json={"answer": "工事目的物引渡時を起算点とします。"},
        headers=auth_headers_legal,
    )
    assert r_answer.status_code == 200
    assert r_answer.json()["status"] == "answered"

    r_confirm = await client.post(f"{OC}/engagements/{eid}/confirm", headers=auth_headers_legal)
    assert r_confirm.status_code == 200
    assert r_confirm.json()["status"] == "confirmed"


async def test_engagement_cancel_and_errors(
    client: Any, auth_headers_legal: dict[str, str]
) -> None:
    """取消・不明 firm 404."""
    firm_id = await _firm(client, auth_headers_legal, "APIテスト法律事務所2")
    r = await client.post(
        f"{OC}/engagements",
        json={"firm_id": firm_id, "title": "取消用", "question": "q"},
        headers=auth_headers_legal,
    )
    eid = r.json()["id"]
    r_cancel = await client.post(
        f"{OC}/engagements/{eid}/cancel",
        json={"reason": "方針変更"},
        headers=auth_headers_legal,
    )
    assert r_cancel.status_code == 200
    assert r_cancel.json()["status"] == "cancelled"

    r_bad = await client.post(
        f"{OC}/engagements",
        json={"firm_id": 999_999, "title": "x", "question": "y"},
        headers=auth_headers_legal,
    )
    assert r_bad.status_code == 404
