"""契約義務（Obligations）API の統合テスト（Issue #99）."""

from __future__ import annotations

from datetime import date
from typing import Any

OBLIGATIONS = "/api/v1/obligations"
CONTRACT_API = "/api/v1/contracts"


async def _create_contract(client: Any, headers: dict[str, str]) -> int:
    r = await client.post(
        CONTRACT_API,
        json={
            "title": "義務APIテスト契約",
            "contract_type": "業務委託契約",
            "counterparty": "みらいテスト商事株式会社",
            "amount": 2_000_000,
            "department_id": 1,
        },
        headers=headers,
    )
    assert r.status_code in (200, 201), r.text
    return int(r.json()["id"])


async def test_obligation_lifecycle_via_api(
    client: Any, auth_headers_legal: dict[str, str]
) -> None:
    """登録 → 一覧（type/bucket 絞り込み）→ 更新 → 完了 → 二重完了 409."""
    cid = await _create_contract(client, auth_headers_legal)
    due = date(2026, 12, 31)

    r_create = await client.post(
        f"{CONTRACT_API}/{cid}/obligations",
        json={
            "obligation_type": "insurance",
            "title": "保険証券の提出",
            "description": "賠償責任保険証券コピー",
            "due_date": due.isoformat(),
        },
        headers=auth_headers_legal,
    )
    assert r_create.status_code == 201, r_create.text
    oid = r_create.json()["id"]

    # 一覧（type・bucket 絞り込み）
    r_list = await client.get(
        f"{OBLIGATIONS}?contract_id={cid}&type=insurance", headers=auth_headers_legal
    )
    assert r_list.status_code == 200
    assert r_list.json()["total"] == 1
    r_bucket = await client.get(
        f"{OBLIGATIONS}?contract_id={cid}&bucket=future", headers=auth_headers_legal
    )
    assert r_bucket.json()["total"] == 1

    # 更新（期限繰り上げ）
    earlier = date(2026, 10, 31)
    r_patch = await client.patch(
        f"{OBLIGATIONS}/{oid}",
        json={"due_date": earlier.isoformat(), "title": "保険証券の提出（更新）"},
        headers=auth_headers_legal,
    )
    assert r_patch.status_code == 200, r_patch.text
    assert r_patch.json()["due_date"] == "2026-10-31"

    # 完了 → 二重完了 409
    r_done = await client.post(f"{OBLIGATIONS}/{oid}/complete", headers=auth_headers_legal)
    assert r_done.status_code == 200
    assert r_done.json()["status"] == "completed"
    assert r_done.json()["completed_at"] is not None
    r_done2 = await client.post(f"{OBLIGATIONS}/{oid}/complete", headers=auth_headers_legal)
    assert r_done2.status_code == 409, r_done2.text

    # 完了後は更新不可（409）
    r_patch2 = await client.patch(
        f"{OBLIGATIONS}/{oid}", json={"title": "変更要望"}, headers=auth_headers_legal
    )
    assert r_patch2.status_code == 409


async def test_renewal_check_endpoint_empty_by_default(
    client: Any, auth_headers_legal: dict[str, str]
) -> None:
    """自動更新フラグなし契約は renewal-check で空（#12）."""
    cid = await _create_contract(client, auth_headers_legal)
    r = await client.get(
        f"{OBLIGATIONS}/renewal-check?contract_id={cid}", headers=auth_headers_legal
    )
    assert r.status_code == 200
    assert r.json() == []


async def test_invalid_create_payload_422(
    client: Any, auth_headers_legal: dict[str, str]
) -> None:
    """不正な種別は 422."""
    cid = await _create_contract(client, auth_headers_legal)
    r = await client.post(
        f"{CONTRACT_API}/{cid}/obligations",
        json={"obligation_type": "unknown", "title": "x"},
        headers=auth_headers_legal,
    )
    assert r.status_code == 422, r.text
