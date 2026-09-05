"""JV（共同企業体）管理サービスの単体テスト（#61〜#70）."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError, ValidationError
from app.models.department import Department
from app.models.user import User
from app.services import jv_service


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


async def _seed_jv(db_session, uid: int, name: str = "デモJV（テスト）") -> object:
    return await jv_service.create_jv(db_session, actor_id=uid, name=name)


async def test_jv_lifecycle(db_session) -> None:
    """#61: 登録（prospecting）→ active → completed / 不正遷移 409."""
    uid = await _seed_user(db_session)
    jv = await _seed_jv(db_session, uid)
    assert jv.jv_no.startswith("JV-")
    assert jv.status == "prospecting"

    active = await jv_service.set_jv_status(
        db_session, jv_id=jv.id, actor_id=uid, status="active"
    )
    assert active.status == "active"

    completed = await jv_service.set_jv_status(
        db_session, jv_id=jv.id, actor_id=uid, status="completed"
    )
    assert completed.status == "completed"
    assert completed.dissolved_at is not None

    with pytest.raises(ConflictError):
        await jv_service.set_jv_status(
            db_session, jv_id=jv.id, actor_id=uid, status="active"
        )
    with pytest.raises(ValidationError):
        await jv_service.set_jv_status(
            db_session, jv_id=jv.id, actor_id=uid, status="bogus"
        )


async def test_member_representative_and_ratios(db_session) -> None:
    """#63/#64/#65: 代表 1 社制・出資比率合計 100% 検証."""
    uid = await _seed_user(db_session)
    jv = await _seed_jv(db_session, uid)

    await jv_service.add_member(
        db_session,
        jv_id=jv.id,
        actor_id=uid,
        company_name="デモ建設（代表）",
        role="representative",
        equity_ratio=60.0,
    )
    with pytest.raises(ConflictError):
        await jv_service.add_member(
            db_session,
            jv_id=jv.id,
            actor_id=uid,
            company_name="デモ建設2（代表重複）",
            role="representative",
        )
    await jv_service.add_member(
        db_session,
        jv_id=jv.id,
        actor_id=uid,
        company_name="デモ土木（構成員）",
        equity_ratio=40.0,
    )
    with pytest.raises(ValidationError):
        await jv_service.add_member(
            db_session,
            jv_id=jv.id,
            actor_id=uid,
            company_name="デモ電気（超過）",
            equity_ratio=10.0,
        )
    with pytest.raises(ValidationError):
        await jv_service.add_member(
            db_session,
            jv_id=jv.id,
            actor_id=uid,
            company_name="デモ電気（不正）",
            equity_ratio=150.0,
        )
    members = await jv_service.list_members(db_session, jv_id=jv.id)
    assert len(members) == 2


async def test_agreement_lifecycle(db_session) -> None:
    """#62: draft で登録 → signed_at 指定で signed → terminate."""
    uid = await _seed_user(db_session)
    jv = await _seed_jv(db_session, uid)

    draft = await jv_service.create_agreement(
        db_session, jv_id=jv.id, actor_id=uid, title="JV 協定書（ドラフト・デモ）"
    )
    assert draft.status == "draft"
    assert draft.agreement_no.startswith("JVA-")

    signed = await jv_service.create_agreement(
        db_session,
        jv_id=jv.id,
        actor_id=uid,
        title="JV 協定書（締結・デモ）",
        signed_at=date.today(),
    )
    assert signed.status == "signed"

    terminated = await jv_service.terminate_agreement(
        db_session, agreement_id=signed.id, actor_id=uid
    )
    assert terminated.status == "terminated"
    assert terminated.terminated_at is not None

    with pytest.raises(ConflictError):
        await jv_service.terminate_agreement(
            db_session, agreement_id=draft.id, actor_id=uid
        )


async def test_dispute_and_settlement(db_session) -> None:
    """#69 紛争（open→responded・409）/#70 清算（completed 前提・pending→settled）."""
    uid = await _seed_user(db_session)
    jv = await _seed_jv(db_session, uid)

    dispute = await jv_service.create_dispute(
        db_session,
        jv_id=jv.id,
        actor_id=uid,
        title="精算金額を巡る協議（デモ）",
        claimant_name="デモ土木",
        respondent_name="デモ建設（代表）",
        amount_claimed_jpy=1_000_000,
    )
    assert dispute.dispute_no.startswith("JVD-")

    responded = await jv_service.respond_dispute(
        db_session, dispute_id=dispute.id, actor_id=uid, response_note="合意（デモ回答）"
    )
    assert responded.status == "responded"
    with pytest.raises(ConflictError):
        await jv_service.respond_dispute(
            db_session, dispute_id=dispute.id, actor_id=uid, response_note="2回目"
        )

    # completed 前の清算は 409
    with pytest.raises(ConflictError):
        await jv_service.create_settlement(
            db_session,
            jv_id=jv.id,
            actor_id=uid,
            title="早期清算（デモ）",
            settlement_amount_jpy=1_000_000,
        )

    await jv_service.set_jv_status(
        db_session, jv_id=jv.id, actor_id=uid, status="active"
    )
    await jv_service.set_jv_status(
        db_session, jv_id=jv.id, actor_id=uid, status="completed"
    )
    settlement = await jv_service.create_settlement(
        db_session,
        jv_id=jv.id,
        actor_id=uid,
        title="JV 清算（デモ）",
        settlement_amount_jpy=5_000_000,
    )
    assert settlement.settlement_no.startswith("JVS-")
    assert settlement.status == "pending"

    settled = await jv_service.settle(
        db_session, settlement_id=settlement.id, actor_id=uid
    )
    assert settled.status == "settled"
    assert settled.settled_at is not None
    with pytest.raises(ConflictError):
        await jv_service.settle(db_session, settlement_id=settlement.id, actor_id=uid)


async def test_dashboard_summary(db_session) -> None:
    """JV サマリー集計."""
    uid = await _seed_user(db_session)
    await _seed_jv(db_session, uid, name="サマリー用 JV（デモ）")
    summary = await jv_service.dashboard_summary(db_session)
    assert sum(summary["jvs_by_status"].values()) >= 1  # type: ignore[index,union-attr]
