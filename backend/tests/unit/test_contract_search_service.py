"""契約書全文検索サービスの単体テスト（Issue #100）."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.exceptions import ValidationError
from app.models.clause import Clause
from app.models.contract import Contract
from app.models.contract_document import ContractDocument
from app.models.department import Department
from app.models.user import User
from app.services import contract_search_service


async def _seed(db_session) -> tuple[int, int]:
    """契約・条項・文書を作成し (contract_id, clause_id) を返す."""
    dept = Department(code=f"D-{uuid4().hex[:8]}", name="法務部")
    db_session.add(dept)
    await db_session.flush()
    user = User(
        entra_oid=uuid4(),
        email=f"{uuid4().hex[:10]}@test.example",
        display_name="作成者",
        role="reviewer",
        department_id=dept.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    contract = Contract(
        contract_no=f"C-{uuid4().hex[:10]}",
        title="北幹線道路補修工事請負契約",
        counterparty="みらい県 土木部",
        contract_type="工事請負契約",
        department_id=dept.id,
        drafter_id=user.id,
    )
    db_session.add(contract)
    await db_session.flush()
    clause = Clause(
        contract_id=contract.id,
        seq=1,
        title="損害賠償",
        body="受注者は、履行遅延により損害賠償責任を負う。賠償額は契約金額の範囲とする。",
        risk_level="high",
    )
    db_session.add(clause)
    await db_session.flush()
    doc = ContractDocument(
        contract_id=contract.id,
        doc_type="signed_original",
        title="請負契約書（正本）",
        content="前払金の支払は着手後30日以内とし、損害賠償に関する特約は別紙のとおり。",
        priority=1,
        version=1,
    )
    db_session.add(doc)
    await db_session.flush()
    return int(contract.id), int(clause.id)


async def test_search_clauses_and_documents(db_session) -> None:
    """条項本文・文書本文の全文検索とスニペット・スコア."""
    cid, clause_id = await _seed(db_session)
    hits = await contract_search_service.search(db_session, q="損害賠償", scope="all")
    kinds = {(h["kind"], h["record_id"]) for h in hits}
    assert ("clause", clause_id) in kinds
    assert any(h["kind"] == "document" and h["contract_id"] == cid for h in hits)
    top = hits[0]
    assert top["score"] > 0
    assert "損害賠償" in (top["snippet"] or "")
    assert hits == sorted(hits, key=lambda h: h["score"], reverse=True)


async def test_search_contract_metadata(db_session) -> None:
    """契約メタデータ（相手方・タイトル）の検索."""
    cid, _ = await _seed(db_session)
    hits = await contract_search_service.search(db_session, q="土木部", scope="contracts")
    assert len(hits) == 1 and hits[0]["contract_id"] == cid
    assert "counterparty" in hits[0]["matched_fields"]


async def test_search_scoped_to_contract(db_session) -> None:
    """contract_id 絞り込み."""
    cid, _ = await _seed(db_session)
    hits = await contract_search_service.search(
        db_session, q="損害賠償", scope="all", contract_id=cid
    )
    assert hits and all(h["contract_id"] == cid for h in hits)
    hits_other = await contract_search_service.search(
        db_session, q="損害賠償", scope="all", contract_id=999_999
    )
    assert hits_other == []


async def test_search_validation(db_session) -> None:
    """空クエリ・不正 scope は ValidationError."""
    with pytest.raises(ValidationError):
        await contract_search_service.search(db_session, q="  ")
    with pytest.raises(ValidationError):
        await contract_search_service.search(db_session, q="x", scope="bogus")


async def test_bigram_dice_basics() -> None:
    """類似度計算（0〜1・同一文字列で 1.0）."""
    assert contract_search_service._bigram_dice("あいうえお", "あいうえお") == 1.0
    assert contract_search_service._bigram_dice("あいうえお", "かきくけこ") == 0.0
    d = contract_search_service._bigram_dice("損害賠償条項", "損害賠償")
    assert 0.0 < d < 1.0
