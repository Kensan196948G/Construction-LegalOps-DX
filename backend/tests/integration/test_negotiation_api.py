"""契約交渉・Redline API の統合テスト（Issue #98）."""

from __future__ import annotations

from typing import Any

from app.models.clause import Clause

CONTRACT_API = "/api/v1/contracts"


async def _create_contract(client: Any, headers: dict[str, str]) -> int:
    r = await client.post(
        CONTRACT_API,
        json={
            "title": "交渉APIテスト契約",
            "contract_type": "業務委託契約",
            "counterparty": "みらいテスト商事株式会社",
            "amount": 1_000_000,
            "department_id": 1,
        },
        headers=headers,
    )
    assert r.status_code in (200, 201), r.text
    return int(r.json()["id"])


async def _seed_clause(api_db_session: Any, contract_id: int) -> int:
    """``api_db_session`` は ``client`` と同じ ``test_engine`` に直接 bind
    されたセッション（``db_session`` はロールバックされるため、別コネクション
    の ``client`` からは見えない）。
    """
    clause = Clause(
        contract_id=contract_id,
        seq=1,
        title="秘密保持",
        body="（原案）秘密情報は 5 年間保持する。",
        risk_level="medium",
    )
    api_db_session.add(clause)
    await api_db_session.flush()
    await api_db_session.commit()
    return int(clause.id)


async def test_negotiation_timeline_and_add(
    client: Any, auth_headers_legal: dict[str, str]
) -> None:
    """契約レベルのコメント記録とタイムライン（新しい順）."""
    cid = await _create_contract(client, auth_headers_legal)
    url = f"{CONTRACT_API}/{cid}/negotiations"

    r1 = await client.post(
        url, json={"action": "comment", "note": "1回目の協議"}, headers=auth_headers_legal
    )
    assert r1.status_code == 201, r1.text
    assert r1.json()["action"] == "comment"

    r2 = await client.post(
        url,
        json={"action": "concession", "note": "支払条件を 60 日に譲歩"},
        headers=auth_headers_legal,
    )
    assert r2.status_code == 201

    r_list = await client.get(url, headers=auth_headers_legal)
    assert r_list.status_code == 200
    body = r_list.json()
    assert body["total"] == 2
    assert [e["action"] for e in body["items"]] == ["concession", "comment"]


async def test_redline_and_clause_status_owner_endpoints(
    client: Any, auth_headers_legal: dict[str, str], api_db_session: Any
) -> None:
    """redline 記録 → ステータス → オーナー割当の一連フロー."""
    cid = await _create_contract(client, auth_headers_legal)
    clause_id = await _seed_clause(api_db_session, cid)

    # redline（修正提案）
    r_redline = await client.post(
        f"{CONTRACT_API}/{cid}/negotiations",
        json={
            "action": "redline",
            "clause_id": clause_id,
            "note": "相手方提案",
            "proposed_text": "（修正案）秘密情報は 10 年間保持する。",
        },
        headers=auth_headers_legal,
    )
    assert r_redline.status_code == 201, r_redline.text

    # ステータス: negotiating → accepted
    r_status = await client.post(
        f"{CONTRACT_API}/{cid}/clauses/{clause_id}/status",
        json={"status": "negotiating", "note": "要検討"},
        headers=auth_headers_legal,
    )
    assert r_status.status_code == 200, r_status.text
    assert r_status.json()["negotiation_status"] == "negotiating"
    assert r_status.json()["negotiated_text"] == "（修正案）秘密情報は 10 年間保持する。"

    r_accept = await client.post(
        f"{CONTRACT_API}/{cid}/clauses/{clause_id}/status",
        json={"status": "accepted"},
        headers=auth_headers_legal,
    )
    assert r_accept.status_code == 200
    assert r_accept.json()["negotiation_status"] == "accepted"

    # 同ステータスは 409
    r_same = await client.post(
        f"{CONTRACT_API}/{cid}/clauses/{clause_id}/status",
        json={"status": "accepted"},
        headers=auth_headers_legal,
    )
    assert r_same.status_code == 409, r_same.text

    # オーナー割当
    r_owner = await client.post(
        f"{CONTRACT_API}/{cid}/clauses/{clause_id}/owner",
        json={"owner": "法務", "note": "法務担当"},
        headers=auth_headers_legal,
    )
    assert r_owner.status_code == 200, r_owner.text
    assert r_owner.json()["clause_owner"] == "法務"

    # タイムライン（clause 絞り込み）に redline / status_change x2 / owner_change が残る
    r_events = await client.get(
        f"{CONTRACT_API}/{cid}/negotiations?clause_id={clause_id}",
        headers=auth_headers_legal,
    )
    assert r_events.status_code == 200
    events = r_events.json()["items"]
    actions = [e["action"] for e in events]
    assert actions == ["owner_change", "status_change", "status_change", "redline"]
    assert events[1]["status_to"] == "accepted"
    assert events[2]["status_to"] == "negotiating"


async def test_foreign_clause_returns_404(
    client: Any, auth_headers_legal: dict[str, str]
) -> None:
    """存在しない/他契約の条項は 404."""
    cid = await _create_contract(client, auth_headers_legal)
    r = await client.post(
        f"{CONTRACT_API}/{cid}/clauses/999999/status",
        json={"status": "accepted"},
        headers=auth_headers_legal,
    )
    assert r.status_code == 404, r.text


async def test_invalid_status_payload_returns_422(
    client: Any, auth_headers_legal: dict[str, str], api_db_session: Any
) -> None:
    """不正なステータス値は 422（pydantic enum 検証）."""
    cid = await _create_contract(client, auth_headers_legal)
    clause_id = await _seed_clause(api_db_session, cid)
    r = await client.post(
        f"{CONTRACT_API}/{cid}/clauses/{clause_id}/status",
        json={"status": "done"},
        headers=auth_headers_legal,
    )
    assert r.status_code == 422, r.text
