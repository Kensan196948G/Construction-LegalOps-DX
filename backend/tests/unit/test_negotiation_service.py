"""契約交渉・Redline 管理サービスの単体テスト（#5〜#8 / Issue #98）."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.clause import Clause
from app.models.contract import Contract
from app.models.department import Department
from app.models.user import User
from app.services import negotiation_service


async def _seed_contract_with_clause(db_session) -> tuple[int, int, int]:
    """契約と条項を 1 つ作成し (contract_id, clause_id, user_id) を返す.

    PG では sequence が進むため actor_id は固定せず、作成した user.id を使う。
    """
    dept = Department(code=f"D-{uuid4().hex[:8]}", name="法務部")
    db_session.add(dept)
    await db_session.flush()
    user = User(
        entra_oid=uuid4(),
        email=f"{uuid4().hex[:10]}@test.example",
        display_name="作成者",
        role="drafter",
        department_id=dept.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    contract = Contract(
        contract_no=f"C-{uuid4().hex[:10]}",
        title="交渉テスト契約",
        counterparty="株式会社テスト",
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
        body="（原案）損害賠償は実損害に限る。",
        risk_level="high",
    )
    db_session.add(clause)
    await db_session.flush()
    return int(contract.id), int(clause.id), int(user.id)


async def test_redline_event_updates_negotiated_text(db_session) -> None:
    """#5: redline の修正案が条項の negotiated_text へ反映される."""
    contract_id, clause_id, uid = await _seed_contract_with_clause(db_session)
    event = await negotiation_service.add_event(
        db_session,
        contract_id=contract_id,
        actor_id=uid,
        action="redline",
        clause_id=clause_id,
        note="相手方からの修正提案",
        proposed_text="（修正案）損害賠償は契約金額の 10% を上限とする。",
    )
    assert event.proposed_text is not None
    clause = await db_session.get(Clause, clause_id)
    assert clause is not None
    assert clause.negotiated_text == event.proposed_text


async def test_comment_event_without_clause(db_session) -> None:
    """#6: 条項を指定しない契約レベルのコメントも記録できる."""
    contract_id, _, uid = await _seed_contract_with_clause(db_session)
    event = await negotiation_service.add_event(
        db_session,
        contract_id=contract_id,
        actor_id=uid,
        action="comment",
        note="全体方針を協議",
    )
    assert event.clause_id is None
    assert event.action == "comment"


async def test_clause_status_lifecycle_and_same_status_conflict(db_session) -> None:
    """#7: negotiating → accepted 遷移と同状態遷移の 409."""
    contract_id, clause_id, uid = await _seed_contract_with_clause(db_session)
    c1 = await negotiation_service.set_clause_status(
        db_session, contract_id=contract_id, clause_id=clause_id, actor_id=uid, status="negotiating"
    )
    assert c1.negotiation_status == "negotiating"
    c2 = await negotiation_service.set_clause_status(
        db_session, contract_id=contract_id, clause_id=clause_id, actor_id=uid, status="accepted"
    )
    assert c2.negotiation_status == "accepted"
    with pytest.raises(ConflictError):
        await negotiation_service.set_clause_status(
            db_session,
            contract_id=contract_id,
            clause_id=clause_id,
            actor_id=uid,
            status="accepted",
        )


async def test_assign_owner_and_same_owner_conflict(db_session) -> None:
    """#8: オーナー割当と同オーナー再割当の 409."""
    contract_id, clause_id, uid = await _seed_contract_with_clause(db_session)
    c1 = await negotiation_service.assign_owner(
        db_session, contract_id=contract_id, clause_id=clause_id, actor_id=uid, owner="法務"
    )
    assert c1.clause_owner == "法務"
    c2 = await negotiation_service.assign_owner(
        db_session, contract_id=contract_id, clause_id=clause_id, actor_id=uid, owner="工事"
    )
    assert c2.clause_owner == "工事"
    with pytest.raises(ConflictError):
        await negotiation_service.assign_owner(
            db_session, contract_id=contract_id, clause_id=clause_id, actor_id=uid, owner="工事"
        )


async def test_list_events_clause_filter_and_order(db_session) -> None:
    """#6: タイムラインは新しい順・clause 絞り込み可."""
    contract_id, clause_id, uid = await _seed_contract_with_clause(db_session)
    await negotiation_service.add_event(
        db_session, contract_id=contract_id, actor_id=uid, action="comment", note="1件目"
    )
    await negotiation_service.set_clause_status(
        db_session, contract_id=contract_id, clause_id=clause_id, actor_id=uid, status="negotiating"
    )
    items, total = await negotiation_service.list_events(
        db_session, contract_id=contract_id
    )
    assert total == 2
    assert items[0].action == "status_change"
    clause_items, clause_total = await negotiation_service.list_events(
        db_session, contract_id=contract_id, clause_id=clause_id
    )
    assert clause_total == 1
    assert clause_items[0].status_to == "negotiating"


async def test_unknown_clause_raises_not_found(db_session) -> None:
    """他契約の条項指定は NotFound."""
    contract_id, _, uid = await _seed_contract_with_clause(db_session)
    with pytest.raises(NotFoundError):
        await negotiation_service.set_clause_status(
            db_session, contract_id=contract_id, clause_id=999_999, actor_id=uid, status="accepted"
        )


async def test_invalid_action_or_status_raises_validation_error(db_session) -> None:
    """不正 action / status は ValidationError."""
    contract_id, clause_id, uid = await _seed_contract_with_clause(db_session)
    with pytest.raises(ValidationError):
        await negotiation_service.add_event(
            db_session, contract_id=contract_id, actor_id=uid, action="status_change"
        )
    with pytest.raises(ValidationError):
        await negotiation_service.set_clause_status(
            db_session, contract_id=contract_id, clause_id=clause_id, actor_id=uid, status="done"
        )
    with pytest.raises(ValidationError):
        await negotiation_service.assign_owner(
            db_session, contract_id=contract_id, clause_id=clause_id, actor_id=uid, owner="経理"
        )
