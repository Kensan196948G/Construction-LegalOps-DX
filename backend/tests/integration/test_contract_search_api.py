"""契約書全文検索 API の統合テスト（Issue #100）."""

from __future__ import annotations

from typing import Any

from app.models.clause import Clause
from app.models.contract_document import ContractDocument

CONTRACT_API = "/api/v1/contracts"
SEARCH = "/api/v1/search"


async def _create_contract_with_text(
    client: Any, headers: dict[str, str], db_session: Any
) -> int:
    """API で契約作成し、条項・文書本文を DB 経由で追加する."""
    r = await client.post(
        CONTRACT_API,
        json={
            "title": "みらい北線橋梁補修工事請負契約",
            "contract_type": "工事請負契約",
            "counterparty": "みらい県 道路課",
            "amount": 15_000_000,
            "department_id": 1,
        },
        headers=headers,
    )
    assert r.status_code in (200, 201), r.text
    cid = int(r.json()["id"])
    db_session.add(
        Clause(
            contract_id=cid,
            seq=1,
            title="損害賠償",
            body="相手方に損害が生じた場合は、賠償額は契約金額の10%を上限とする。",
            risk_level="high",
        )
    )
    db_session.add(
        ContractDocument(
            contract_id=cid,
            doc_type="contract",
            title="請負契約書",
            content="損害賠償に関する特約は別紙のとおり。着手金の支払は契約締結後 30 日以内。",
            priority=1,
            version=1,
        )
    )
    await db_session.flush()
    await db_session.commit()
    return cid


async def test_search_all_scopes_and_filters(
    client: Any, auth_headers_legal: dict[str, str], db_session: Any
) -> None:
    """契約・条項・文書に跨る検索・contract_id 絞り込み・スコア降順."""
    cid = await _create_contract_with_text(client, auth_headers_legal, db_session)

    r_all = await client.get(
        SEARCH, params={"q": "損害", "scope": "all"}, headers=auth_headers_legal
    )
    assert r_all.status_code == 200
    hits = r_all.json()
    assert hits and all(h["contract_id"] == cid for h in hits)  # 他契約なし
    kinds = {h["kind"] for h in hits}
    assert "clause" in kinds and "document" in kinds

    r_scoped = await client.get(
        SEARCH,
        params={"q": "支払", "scope": "documents", "contract_id": cid},
        headers=auth_headers_legal,
    )
    assert r_scoped.status_code == 200
    assert all(h["kind"] == "document" for h in r_scoped.json())
    assert any("支払" in (h["snippet"] or "") for h in r_scoped.json())

    r_meta = await client.get(
        SEARCH, params={"q": "道路課", "scope": "contracts"}, headers=auth_headers_legal
    )
    assert r_meta.status_code == 200
    assert any(h["kind"] == "contract" for h in r_meta.json())


async def test_search_empty_query_422(client: Any, auth_headers_legal: dict[str, str]) -> None:
    """空クエリは 422."""
    r = await client.get(SEARCH, params={"q": ""}, headers=auth_headers_legal)
    assert r.status_code == 422
