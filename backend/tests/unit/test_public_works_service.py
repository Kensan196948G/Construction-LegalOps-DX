"""公共工事特化サービスの単体テスト（#41-#43・#54-#57）."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.contract import Contract
from app.models.department import Department
from app.models.public_works import ContractingAgency
from app.models.user import User
from app.services import public_works_service


async def _seed_user(db_session) -> int:
    dept = Department(code=f"D-{uuid4().hex[:8]}", name="工事部")
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
    return int(user.id)


async def _seed_agency(db_session, uid: int, code: str = "AG-TEST-001") -> ContractingAgency:
    return await public_works_service.create_agency(
        db_session,
        actor_id=uid,
        code=code,
        name="テスト発注機関（デモ）",
        agency_type="municipal",
        payment_deadline_days=50,
        advance_payment_ratio=0.4,
        requires_slide_clause=True,
    )


async def _seed_contract(db_session, uid: int, no: str = "CTR-PW-TEST-1") -> Contract:
    dept = (
        await db_session.execute(select(Department).limit(1))
    ).scalar_one()
    contract = Contract(
        contract_no=no,
        title="公共工事テスト契約（デモ）",
        counterparty="テスト発注機関（デモ）",
        contract_type="工事請負契約",
        amount=20_000_000,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        department_id=dept.id,
        drafter_id=uid,
        status="approved",
    )
    db_session.add(contract)
    await db_session.flush()
    return contract


async def test_agency_create_and_list(db_session) -> None:
    """#41/#42: 登録・一覧・重複コード 409."""
    uid = await _seed_user(db_session)
    agency = await _seed_agency(db_session, uid)
    assert agency.agency_type == "municipal"
    assert agency.payment_deadline_days == 50
    assert agency.requires_slide_clause is True

    with pytest.raises(ConflictError):
        await public_works_service.create_agency(
            db_session,
            actor_id=uid,
            code="AG-TEST-001",
            name="重複（デモ）",
            agency_type="national",
        )
    with pytest.raises(ValidationError):
        await public_works_service.create_agency(
            db_session,
            actor_id=uid,
            code="AG-TEST-002",
            name="不正前払率（デモ）",
            agency_type="national",
            advance_payment_ratio=1.5,
        )

    _, total = await public_works_service.list_agencies(db_session, agency_type="municipal")
    assert total >= 1


async def test_notification_lifecycle_and_bucket(db_session) -> None:
    """#54: 登録 → 期限バケット（動的算出）→ notify → cancel 409."""
    uid = await _seed_user(db_session)
    agency = await _seed_agency(db_session, uid)

    overdue_row = await public_works_service.create_notification(
        db_session,
        actor_id=uid,
        notification_type="delay",
        title="工期遅延通知（デモ）",
        agency_id=agency.id,
        due_date=date.today() - timedelta(days=3),
    )
    assert overdue_row.notification_no.startswith("ON-")
    assert public_works_service.notification_bucket(overdue_row) == "overdue"

    future_row = await public_works_service.create_notification(
        db_session,
        actor_id=uid,
        notification_type="design_change",
        title="設計変更通知（デモ）",
        agency_id=agency.id,
        due_date=date.today() + timedelta(days=10),
    )
    assert public_works_service.notification_bucket(future_row) == "within_30"

    notified = await public_works_service.notify_notification(
        db_session, notification_id=future_row.id, actor_id=uid
    )
    assert notified.status == "notified"
    assert notified.notified_at is not None
    # notified のバケットは none
    assert public_works_service.notification_bucket(notified) == "none"

    with pytest.raises(ConflictError):
        await public_works_service.notify_notification(
            db_session, notification_id=future_row.id, actor_id=uid
        )

    cancelled = await public_works_service.cancel_notification(
        db_session, notification_id=overdue_row.id, actor_id=uid, reason="取下げ（デモ）"
    )
    assert cancelled.status == "cancelled"

    with pytest.raises(ValidationError):
        await public_works_service.create_notification(
            db_session, actor_id=uid, notification_type="bogus", title="不正（デモ）"
        )


async def test_consultation_lifecycle(db_session) -> None:
    """#55/#56/#57: 申出 → 回答・結果記録 → 取下げ 409."""
    uid = await _seed_user(db_session)
    agency = await _seed_agency(db_session, uid)

    row = await public_works_service.create_consultation(
        db_session,
        actor_id=uid,
        consultation_type="extension_of_time",
        title="工期延伸協議（デモ）",
        agency_id=agency.id,
        claimed_days=30,
        due_date=date.today() + timedelta(days=14),
    )
    assert row.consultation_no.startswith("PW-")
    assert row.status == "open"

    responded = await public_works_service.respond_consultation(
        db_session,
        consultation_id=row.id,
        actor_id=uid,
        response_note="20 日の延伸を承認（デモ回答）",
        resolved_days=20,
    )
    assert responded.status == "responded"
    assert responded.resolved_days == 20
    assert responded.responded_at is not None

    with pytest.raises(ConflictError):
        await public_works_service.respond_consultation(
            db_session,
            consultation_id=row.id,
            actor_id=uid,
            response_note="2 回目（デモ）",
        )
    with pytest.raises(ConflictError):
        await public_works_service.cancel_consultation(
            db_session, consultation_id=row.id, actor_id=uid, reason="遅すぎる（デモ）"
        )

    with pytest.raises(ValidationError):
        await public_works_service.create_consultation(
            db_session,
            actor_id=uid,
            consultation_type="bogus",
            title="不正（デモ）",
        )
    # 別の open な協議で不正な結果日数を検証（resolved_days=0 → 422）
    row2 = await public_works_service.create_consultation(
        db_session,
        actor_id=uid,
        consultation_type="price_slide",
        title="スライド請求協議（デモ）",
        agency_id=agency.id,
        claimed_amount_jpy=500_000,
    )
    with pytest.raises(ValidationError):
        await public_works_service.respond_consultation(
            db_session,
            consultation_id=row2.id,
            actor_id=uid,
            response_note="x",
            resolved_days=0,
        )


async def test_standard_clause_check(db_session) -> None:
    """#43: 約款差分チェック（欠落カテゴリ検出・決定論的）."""
    uid = await _seed_user(db_session)
    contract = await _seed_contract(db_session, uid)
    # 最小限の条項を投入（契約金額・工期のみ → 多数カテゴリが欠落）
    from app.models.clause import Clause

    clause_cls = Clause
    db_session.add(
        clause_cls(
            contract_id=contract.id,
            seq=1,
            title="契約金額",
            body="契約金額は 20,000,000 円とする。",
        )
    )
    db_session.add(
        clause_cls(
            contract_id=contract.id,
            seq=2,
            title="工期",
            body="工期は 2026 年 12 月 31 日までとする。",
        )
    )
    await db_session.flush()

    result = await public_works_service.check_standard_clauses(
        db_session, contract_id=contract.id
    )
    assert result["total_categories"] >= 10
    assert result["covered_categories"] >= 2
    assert result["missing_categories"] >= 5
    categories = {c["category"]: c for c in result["categories"]}  # type: ignore[index,union-attr]
    assert categories["契約金額"]["covered"] is True  # type: ignore[union-attr]
    assert categories["損害賠償"]["covered"] is False  # type: ignore[union-attr]

    with pytest.raises(NotFoundError):
        await public_works_service.check_standard_clauses(
            db_session, contract_id=999_999
        )
