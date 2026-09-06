"""顧問弁護士管理サービスの単体テスト（Issue #102）."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.department import Department
from app.models.user import User
from app.services import matter_service, outside_counsel_service


async def _seed(db_session) -> tuple[int, int]:
    """ユーザー・Matter を作成し (user_id, matter_id) を返す."""
    dept = Department(code=f"D-{uuid4().hex[:8]}", name="法務部")
    db_session.add(dept)
    await db_session.flush()
    user = User(
        entra_oid=uuid4(),
        email=f"{uuid4().hex[:10]}@test.example",
        display_name="法務担当",
        role="reviewer",
        department_id=dept.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    matter = await matter_service.create_matter(
        db_session, actor_id=user.id, title="協力会社紛争", matter_type="dispute"
    )
    return int(user.id), int(matter.id)


async def test_firm_and_lawyer_registry(db_session) -> None:
    """#86/#87: 事務所・弁護士の登録と一覧."""
    uid, _ = await _seed(db_session)
    firm = await outside_counsel_service.create_firm(
        db_session, actor_id=uid, firm_name="みらい法律事務所", contact_email="office@law.example"
    )
    assert firm.firm_name == "みらい法律事務所"
    lawyer = await outside_counsel_service.create_lawyer(
        db_session, actor_id=uid, firm_id=firm.id, lawyer_name="弁護士 一郎", bar_number="12345"
    )
    assert lawyer.firm_id == firm.id
    firms, total = await outside_counsel_service.list_firms(db_session)
    assert total >= 1 and any(f.id == firm.id for f in firms)
    lawyers, _ = await outside_counsel_service.list_lawyers(db_session, firm_id=firm.id)
    assert any(item.id == lawyer.id for item in lawyers)


async def test_engagement_lifecycle(db_session) -> None:
    """#85/#88/#89: 起票→回答→確認（回答期限・利益相反付き）."""
    uid, mid = await _seed(db_session)
    firm = await outside_counsel_service.create_firm(
        db_session, actor_id=uid, firm_name="第二法律事務所"
    )
    lawyer = await outside_counsel_service.create_lawyer(
        db_session, actor_id=uid, firm_id=firm.id, lawyer_name="弁護士 次郎"
    )
    due = date.today() + timedelta(days=7)
    eng = await outside_counsel_service.create_engagement(
        db_session,
        actor_id=uid,
        firm_id=firm.id,
        lawyer_id=lawyer.id,
        matter_id=mid,
        title="下請代金支払請求の法的見解",
        question="督促状を送付してよいか。",
        due_date=due,
        conflict_of_interest=False,
        fee_estimate_jpy=300_000,
    )
    assert eng.engagement_no.startswith("LEG-")
    assert eng.status == "open"
    assert eng.due_date == due

    with pytest.raises(ConflictError):
        await outside_counsel_service.confirm_engagement(
            db_session, engagement_id=eng.id, actor_id=uid
        )

    answered = await outside_counsel_service.submit_answer(
        db_session, engagement_id=eng.id, actor_id=uid, answer="送付して差し支えありません。"
    )
    assert answered.status == "answered" and answered.answered_at is not None

    confirmed = await outside_counsel_service.confirm_engagement(
        db_session, engagement_id=eng.id, actor_id=uid
    )
    assert confirmed.status == "confirmed"
    with pytest.raises(ConflictError):
        await outside_counsel_service.cancel_engagement(
            db_session, engagement_id=eng.id, actor_id=uid
        )


async def test_engagement_rules_and_validation(db_session) -> None:
    """二重回答 409・他事務所弁護士 422・不明 firm/matter 404・取消 reason 記録."""
    uid, _mid = await _seed(db_session)
    firm_a = await outside_counsel_service.create_firm(
        db_session, actor_id=uid, firm_name="事務所A"
    )
    firm_b = await outside_counsel_service.create_firm(
        db_session, actor_id=uid, firm_name="事務所B"
    )
    lawyer_b = await outside_counsel_service.create_lawyer(
        db_session, actor_id=uid, firm_id=firm_b.id, lawyer_name="弁護士 B"
    )
    eng = await outside_counsel_service.create_engagement(
        db_session, actor_id=uid, firm_id=firm_a.id, title="照会", question="確認したい。"
    )
    # 他事務所の弁護士指定
    with pytest.raises(ValidationError):
        await outside_counsel_service.create_engagement(
            db_session,
            actor_id=uid,
            firm_id=firm_a.id,
            title="照会2",
            question="確認したい。",
            lawyer_id=lawyer_b.id,
        )
    with pytest.raises(NotFoundError):
        await outside_counsel_service.create_engagement(
            db_session, actor_id=uid, firm_id=999_999, title="x", question="y"
        )
    with pytest.raises(NotFoundError):
        await outside_counsel_service.create_engagement(
            db_session, actor_id=uid, firm_id=firm_a.id, title="x", question="y", matter_id=999_999
        )

    ans = await outside_counsel_service.submit_answer(
        db_session, engagement_id=eng.id, actor_id=uid, answer="回答1"
    )
    with pytest.raises(ConflictError):
        await outside_counsel_service.submit_answer(
            db_session, engagement_id=ans.id, actor_id=uid, answer="回答2"
        )

    eng2 = await outside_counsel_service.create_engagement(
        db_session, actor_id=uid, firm_id=firm_a.id, title="取消テスト", question="q"
    )
    cancelled = await outside_counsel_service.cancel_engagement(
        db_session, engagement_id=eng2.id, actor_id=uid, reason="依頼取り下げ"
    )
    assert cancelled.status == "cancelled" and cancelled.notes == "依頼取り下げ"
    with pytest.raises(ConflictError):
        await outside_counsel_service.submit_answer(
            db_session, engagement_id=cancelled.id, actor_id=uid, answer="late"
        )
