"""Legal Matter Management API の統合テスト（Issue #101）."""

from __future__ import annotations

from typing import Any

MATTERS = "/api/v1/matters"
CONTRACTS = "/api/v1/contracts"


async def _create_contract(client: Any, headers: dict[str, str]) -> int:
    r = await client.post(
        CONTRACTS,
        json={
            "title": "Matter API テスト契約",
            "contract_type": "業務委託契約",
            "counterparty": "みらいテスト商事株式会社",
            "amount": 3_000_000,
            "department_id": 1,
        },
        headers=headers,
    )
    assert r.status_code in (200, 201), r.text
    return int(r.json()["id"])


async def test_matter_lifecycle_via_api(client: Any, auth_headers_legal: dict[str, str]) -> None:
    """作成（契約リンク・採番）→ 状態遷移 → タイムライン → リンク解除."""
    cid = await _create_contract(client, auth_headers_legal)

    r_create = await client.post(
        MATTERS,
        json={
            "title": "取引先からの請求紛争（Matter API）",
            "matter_type": "dispute",
            "priority": "high",
            "description": "請求金額の一部について争いがある。",
            "contract_ids": [cid],
        },
        headers=auth_headers_legal,
    )
    assert r_create.status_code == 201, r_create.text
    body = r_create.json()
    assert body["matter_no"].startswith("MT-")
    assert body["status"] == "open"
    mid = body["id"]

    r_status = await client.post(
        f"{MATTERS}/{mid}/status",
        json={"status": "in_progress", "note": "着手"},
        headers=auth_headers_legal,
    )
    assert r_status.status_code == 200
    assert r_status.json()["status"] == "in_progress"

    r_note = await client.post(
        f"{MATTERS}/{mid}/notes", json={"note": "相手方代理人と面談"}, headers=auth_headers_legal
    )
    assert r_note.status_code == 201

    r_events = await client.get(f"{MATTERS}/{mid}/events", headers=auth_headers_legal)
    assert r_events.status_code == 200
    types = [e["event_type"] for e in r_events.json()]
    assert "created" in types and "status_changed" in types and "note" in types

    r_contracts = await client.get(f"{MATTERS}/{mid}/contracts", headers=auth_headers_legal)
    assert r_contracts.status_code == 200
    assert any(item["contract_id"] == cid for item in r_contracts.json())

    r_unlink = await client.delete(f"{MATTERS}/{mid}/contracts/{cid}", headers=auth_headers_legal)
    assert r_unlink.status_code == 200

    r_close = await client.post(
        f"{MATTERS}/{mid}/status",
        json={"status": "closed", "note": "和解成立"},
        headers=auth_headers_legal,
    )
    assert r_close.status_code == 200
    assert r_close.json()["closed_at"] is not None


async def test_matter_list_filters(client: Any, auth_headers_legal: dict[str, str]) -> None:
    """一覧（status/type 絞り込み）."""
    r = await client.post(
        MATTERS, json={"title": "リスト用", "matter_type": "compliance"}, headers=auth_headers_legal
    )
    assert r.status_code == 201
    r_list = await client.get(f"{MATTERS}?status=open&type=compliance", headers=auth_headers_legal)
    assert r_list.status_code == 200
    assert any(i["title"] == "リスト用" for i in r_list.json()["items"])


async def test_matter_unknown_legal_hold_404(
    client: Any, auth_headers_legal: dict[str, str]
) -> None:
    """不明な Legal Hold 連動は 404."""
    r = await client.post(
        MATTERS,
        json={"title": "ホールドテスト", "matter_type": "dispute"},
        headers=auth_headers_legal,
    )
    mid = r.json()["id"]
    r_hold = await client.post(
        f"{MATTERS}/{mid}/legal-hold",
        json={"legal_hold_case_id": 999_999},
        headers=auth_headers_legal,
    )
    assert r_hold.status_code == 404
