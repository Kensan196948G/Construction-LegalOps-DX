"""協力会社拡張サービスの単体テスト（#136〜#152）."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.department import Department
from app.models.user import User
from app.services import partner_ext_service


async def _seed_user(db_session) -> int:
    dept = Department(code=f"D-{uuid4().hex[:8]}", name="工事部")
    db_session.add(dept)
    await db_session.flush()
    user = User(
        entra_oid=uuid4(),
        email=f"{uuid4().hex[:10]}@test.local",
        display_name="作成者",
        role="reviewer",
        department_id=dept.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return int(user.id)


async def _seed_partner(db_session, uid: int, name: str = "デモ協力会社（テスト）") -> object:
    from app.models.partner import Partner

    partner = Partner(
        name=name,
        partner_type="下請",
        permit_number="デモ県知事許可（テスト）",
        permit_expiry=date.today() + timedelta(days=200),
        social_insurance_joined=True,
        ccus_registered=True,
        anti_social_check="confirmed",
        bankruptcy_risk="low",
        insurance_joined=True,
    )
    db_session.add(partner)
    await db_session.flush()
    return partner


async def test_review_lifecycle(db_session) -> None:
    """#151: 起票（open）→ 完了（next_review_due 反映）→ 再完了 409."""
    uid = await _seed_user(db_session)
    partner = await _seed_partner(db_session, uid)

    review = await partner_ext_service.create_review(
        db_session,
        actor_id=uid,
        partner_id=partner.id,
        review_type="periodic",
        title="定期再審査（テスト）",
    )
    assert review.review_no.startswith("PRV-")
    assert review.status == "open"

    completed = await partner_ext_service.complete_review(
        db_session,
        review_id=review.id,
        actor_id=uid,
        safety_score=85,
        findings="特記事項なし（テスト）",
    )
    assert completed.status == "completed"
    assert completed.reviewed_at is not None
    assert completed.next_review_due is not None
    # Partner へ次回期限が反映される
    await db_session.refresh(partner)
    assert partner.next_review_due == completed.next_review_due

    with pytest.raises(ConflictError):
        await partner_ext_service.complete_review(
            db_session, review_id=review.id, actor_id=uid, safety_score=90
        )


async def test_review_validation(db_session) -> None:
    """不正種別・安全成績範囲外 422・不明 partner 404."""
    uid = await _seed_user(db_session)
    partner = await _seed_partner(db_session, uid)
    with pytest.raises(ValidationError):
        await partner_ext_service.create_review(
            db_session,
            actor_id=uid,
            partner_id=partner.id,
            review_type="bogus",
            title="不正（テスト）",
        )
    with pytest.raises(ValidationError):
        await partner_ext_service.create_review(
            db_session,
            actor_id=uid,
            partner_id=partner.id,
            review_type="periodic",
            title="不正スコア（テスト）",
            safety_score=150,
        )
    with pytest.raises(NotFoundError):
        await partner_ext_service.create_review(
            db_session,
            actor_id=uid,
            partner_id=999_999,
            review_type="periodic",
            title="不明（テスト）",
        )


async def test_risk_score_computation(db_session) -> None:
    """#150: Risk Score が期限切れ・反社・倒産リスクで増加する（決定論的）."""
    uid = await _seed_user(db_session)
    healthy = await _seed_partner(db_session, uid, name="健全（テスト）")
    result_healthy = partner_ext_service.compute_risk_score(healthy)
    assert result_healthy["risk_score"] <= 45  # type: ignore[index,union-attr]

    risky = await _seed_partner(db_session, uid, name="リスク（テスト）")
    risky.permit_expiry = date.today() - timedelta(days=30)
    risky.insurance_expiry = date.today() - timedelta(days=10)
    risky.anti_social_check = "confirmed"
    result_risky = partner_ext_service.compute_risk_score(risky)
    assert result_risky["risk_score"] > result_healthy["risk_score"]  # type: ignore[index,union-attr]
    assert result_risky["expiry_overdue_count"] == 2  # type: ignore[index,union-attr]

    # refresh で Partner へ保存される
    saved = await partner_ext_service.refresh_risk_score(db_session, partner_id=risky.id)
    assert saved.risk_score is not None
    assert saved.risk_level in ("low", "medium", "high", "critical")


async def test_expiry_alerts(db_session) -> None:
    """#138/#146: 期限切れ・期限切れ近傍の協力会社がアラート対象になる."""
    uid = await _seed_user(db_session)
    ok_partner = await _seed_partner(db_session, uid, name="期限OK（テスト）")
    expiring = await _seed_partner(db_session, uid, name="期限切れ（テスト）")
    expiring.permit_expiry = date.today() - timedelta(days=1)
    await db_session.flush()

    rows, _total = await partner_ext_service.list_expiry_alerts(db_session, within_days=60)
    ids = {r.id for r in rows}
    assert expiring.id in ids
    assert ok_partner.id not in ids

    # フラグは partner_expiry_flags から取得できる
    flags = partner_ext_service.partner_expiry_flags(expiring)
    assert flags["permit_state"] == "expired"  # type: ignore[index,union-attr]
