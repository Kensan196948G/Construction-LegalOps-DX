"""契約義務（Obligations）サービスの単体テスト（#9〜#13 / Issue #99）."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.contract import Contract
from app.models.department import Department
from app.models.user import User
from app.services import obligation_service


async def _seed_contract(db_session, **overrides) -> tuple[int, int]:
    """契約とユーザーを作成し (contract_id, user_id) を返す（actor は実ユーザー）."""
    dept = Department(code=f"D-{uuid4().hex[:8]}", name="法務部")
    db_session.add(dept)
    await db_session.flush()
    user = User(
        entra_oid=uuid4(),
        email=f"{uuid4().hex[:10]}@test.local",
        display_name="作成者",
        role="drafter",
        department_id=dept.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    contract = Contract(
        contract_no=f"C-{uuid4().hex[:10]}",
        title="義務テスト契約",
        counterparty="株式会社テスト",
        contract_type="工事請負契約",
        department_id=dept.id,
        drafter_id=user.id,
        **overrides,
    )
    db_session.add(contract)
    await db_session.flush()
    return int(contract.id), int(user.id)


async def test_create_and_bucket_calendar(db_session) -> None:
    """#9/#10: 登録と期限バケット（overdue / within_30 は動的判定）."""
    cid, uid = await _seed_contract(db_session)
    today = datetime.now(UTC).date()
    o1 = await obligation_service.create_obligation(
        db_session,
        contract_id=cid,
        actor_id=uid,
        obligation_type="report",
        title="月次進捗報告",
        due_date=today - timedelta(days=1),
    )
    o2 = await obligation_service.create_obligation(
        db_session,
        contract_id=cid,
        actor_id=uid,
        obligation_type="insurance",
        title="保険証券提出",
        due_date=today + timedelta(days=10),
    )
    o3 = await obligation_service.create_obligation(
        db_session,
        contract_id=cid,
        actor_id=uid,
        obligation_type="renewal",
        title="更新手続",
        due_date=today + timedelta(days=90),
    )
    assert o1.status == "open"
    assert obligation_service.obligation_bucket(o1.due_date, status=o1.status) == "overdue"
    assert obligation_service.obligation_bucket(o2.due_date, status=o2.status) == "within_30"
    assert obligation_service.obligation_bucket(o3.due_date, status=o3.status) == "future"

    overdue, _ = await obligation_service.list_obligations(
        db_session, contract_id=cid, bucket="overdue"
    )
    assert [o.id for o in overdue] == [o1.id]
    within, _ = await obligation_service.list_obligations(
        db_session, contract_id=cid, bucket="within_30"
    )
    assert [o.id for o in within] == [o2.id]


async def test_completed_excludes_from_bucket(db_session) -> None:
    """完了済み義務は未完了バケットに含まれない."""
    cid, uid = await _seed_contract(db_session)
    today = datetime.now(UTC).date()
    o = await obligation_service.create_obligation(
        db_session,
        contract_id=cid,
        actor_id=uid,
        obligation_type="submit",
        title="書類提出",
        due_date=today - timedelta(days=5),
    )
    await obligation_service.complete_obligation(db_session, obligation_id=o.id, actor_id=uid)
    assert obligation_service.obligation_bucket(o.due_date, status=o.status) is None
    overdue, _ = await obligation_service.list_obligations(
        db_session, contract_id=cid, bucket="overdue"
    )
    assert overdue == []


async def test_complete_twice_conflict_and_update_after_complete(db_session) -> None:
    """二重完了は 409・完了後の更新は 409."""
    cid, uid = await _seed_contract(db_session)
    o = await obligation_service.create_obligation(
        db_session,
        contract_id=cid,
        actor_id=uid,
        obligation_type="notice",
        title="事故通知",
        due_date=None,
    )
    await obligation_service.complete_obligation(db_session, obligation_id=o.id, actor_id=uid)
    assert o.completed_at is not None
    with pytest.raises(ConflictError):
        await obligation_service.complete_obligation(db_session, obligation_id=o.id, actor_id=uid)
    with pytest.raises(ConflictError):
        await obligation_service.update_obligation(
            db_session, obligation_id=o.id, actor_id=uid, title="変更"
        )


async def test_waive_and_unknown(db_session) -> None:
    """放棄・不明 id 404・不明 assignee 404."""
    cid, uid = await _seed_contract(db_session)
    o = await obligation_service.create_obligation(
        db_session, contract_id=cid, actor_id=uid,
        obligation_type="closing", title="精算確認",
    )
    w = await obligation_service.waive_obligation(db_session, obligation_id=o.id, actor_id=uid)
    assert w.status == "waived"
    with pytest.raises(NotFoundError):
        await obligation_service.complete_obligation(
            db_session, obligation_id=999_999, actor_id=uid
        )
    with pytest.raises(NotFoundError):
        await obligation_service.create_obligation(
            db_session,
            contract_id=cid,
            actor_id=uid,
            obligation_type="other",
            title="担当なし",
            assignee_id=999_999,
        )


async def test_invalid_type_or_status(db_session) -> None:
    """不正な種別・作成時ステータスは ValidationError."""
    cid, uid = await _seed_contract(db_session)
    with pytest.raises(ValidationError):
        await obligation_service.create_obligation(
            db_session, contract_id=cid, actor_id=uid,
            obligation_type="unknown", title="x",
        )
    with pytest.raises(ValidationError):
        await obligation_service.create_obligation(
            db_session, contract_id=cid, actor_id=uid,
            obligation_type="other", title="x", status="completed",
        )


async def test_renewal_check_states(db_session) -> None:
    """#12: 自動更新の通知期限判定（notice_overdue / upcoming / ok / expired）."""
    today = datetime.now(UTC).date()
    cid_overdue, _uid_overdue = await _seed_contract(
        db_session, auto_renewal=True, renewal_notice_days=60,
        start_date=today - timedelta(days=400), end_date=today + timedelta(days=20),
    )
    cid_ok, _uid_ok = await _seed_contract(
        db_session, auto_renewal=True, renewal_notice_days=60,
        start_date=today - timedelta(days=200), end_date=today + timedelta(days=120),
    )
    cid_expired, _ = await _seed_contract(
        db_session, auto_renewal=True, renewal_notice_days=60,
        start_date=today - timedelta(days=500), end_date=today - timedelta(days=10),
    )
    rows = await obligation_service.renewal_check(db_session)
    states = {r["contract_id"]: r["state"] for r in rows}
    assert states[cid_overdue] == "notice_overdue"
    assert states[cid_ok] == "ok"
    assert states[cid_expired] == "expired"
    single = await obligation_service.renewal_check(db_session, contract_id=cid_ok)
    assert len(single) == 1 and single[0]["state"] == "ok"
