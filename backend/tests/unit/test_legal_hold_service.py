"""リーガルホールド管理サービスのテスト."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.models.contract import Contract
from app.models.department import Department
from app.models.user import User
from app.services import legal_hold_service


async def _seed_contract(db_session) -> tuple[int, int]:
    """Return ``(contract_id, user_id)`` — both persisted so FK constraints hold."""
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
        title="テスト契約",
        counterparty="株式会社テスト",
        contract_type="工事請負契約",
        department_id=dept.id,
        drafter_id=user.id,
    )
    db_session.add(contract)
    await db_session.flush()
    return int(contract.id), int(user.id)


async def test_start_end_list_hold(db_session) -> None:
    contract_id, user_id = await _seed_contract(db_session)
    hold = await legal_hold_service.start_legal_hold(
        db_session,
        contract_id=contract_id,
        reason="訴訟準備のため",
        requested_by=user_id,
    )
    assert hold.id is not None
    assert await legal_hold_service.is_under_legal_hold(db_session, contract_id=contract_id) is True

    active = await legal_hold_service.list_legal_holds(db_session, active_only=True)
    assert len(active) == 1

    ok = await legal_hold_service.end_legal_hold(db_session, hold_id=int(hold.id), actor_id=user_id)
    assert ok is True
    assert (
        await legal_hold_service.is_under_legal_hold(db_session, contract_id=contract_id) is False
    )


async def test_duplicate_active_hold_raises(db_session) -> None:
    contract_id, user_id = await _seed_contract(db_session)
    await legal_hold_service.start_legal_hold(
        db_session, contract_id=contract_id, reason="1件目", requested_by=user_id
    )
    with pytest.raises(legal_hold_service.LegalHoldError):
        await legal_hold_service.start_legal_hold(
            db_session, contract_id=contract_id, reason="2件目", requested_by=user_id
        )


async def test_end_hold_returns_false_when_missing(db_session) -> None:
    # hold_id が存在しないため actor_id は参照されず、FK 制約にも触れない。
    assert await legal_hold_service.end_legal_hold(db_session, hold_id=999999, actor_id=1) is False
