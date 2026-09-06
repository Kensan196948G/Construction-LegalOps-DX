"""独禁法・入札談合コンプライアンス業務サービスの単体テスト（Issue #122）."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.contract import Contract
from app.models.department import Department
from app.models.user import User
from app.services import antitrust_service


async def _seed_user_and_contract(db_session) -> tuple[int, int]:
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
        contract_no=f"CTR-AT-{uuid4().hex[:6]}",
        title="独禁法テスト契約",
        counterparty="テスト（デモ）",
        contract_type="工事請負契約",
        amount=10_000_000,
        department_id=dept.id,
        drafter_id=user.id,
        status="approved",
    )
    db_session.add(contract)
    await db_session.flush()
    return int(user.id), int(contract.id)


# ---------------------------------------------------------------------------
# #113/#114/#117/#118/#119 チェック
# ---------------------------------------------------------------------------


async def test_create_check_general_persists_findings_and_severity(db_session) -> None:
    uid, contract_id = await _seed_user_and_contract(db_session)
    row = await antitrust_service.create_check(
        db_session,
        actor_id=uid,
        check_type="general",
        subject="テスト契約の独禁法スクリーニング",
        context={"text": "談合の懸念がある文言を含む契約書。"},
        contract_id=contract_id,
    )
    assert row.check_no.startswith("ATC-")
    assert row.severity == "block"
    assert len(row.findings) >= 1
    assert row.findings[0]["code"] == "antitrust_general_red_flag"


async def test_create_check_invalid_type_raises(db_session) -> None:
    uid, _ = await _seed_user_and_contract(db_session)
    with pytest.raises(ValidationError):
        await antitrust_service.create_check(
            db_session,
            actor_id=uid,
            check_type="bogus",
            subject="不正種別",
            context={},
        )


async def test_create_check_missing_contract_raises(db_session) -> None:
    uid, _ = await _seed_user_and_contract(db_session)
    with pytest.raises(NotFoundError):
        await antitrust_service.create_check(
            db_session,
            actor_id=uid,
            check_type="bid_rigging",
            subject="存在しない契約",
            context={},
            contract_id=999_999,
        )


async def test_list_checks_filters_by_type(db_session) -> None:
    uid, cid = await _seed_user_and_contract(db_session)
    await antitrust_service.create_check(
        db_session, actor_id=uid, check_type="general", subject="A", context={}, contract_id=cid
    )
    await antitrust_service.create_check(
        db_session,
        actor_id=uid,
        check_type="bid_rigging",
        subject="B",
        context={},
        contract_id=cid,
    )
    # 共有 PG テスト DB には他テストが作った bid_rigging チェックも含まれうるため、
    # 本テストが作成した contract_id で絞り込んで検証する。
    items, total = await antitrust_service.list_checks(
        db_session, check_type="bid_rigging", contract_id=cid
    )
    assert total == 1
    assert items[0].check_type == "bid_rigging"


async def test_get_check_not_found(db_session) -> None:
    with pytest.raises(NotFoundError):
        await antitrust_service.get_check(db_session, check_id=999_999)


# ---------------------------------------------------------------------------
# #115/#116/#121/#122/#123 事前申請ワークフロー
# ---------------------------------------------------------------------------


async def test_application_lifecycle_approve_then_complete(db_session) -> None:
    uid, _ = await _seed_user_and_contract(db_session)
    app_row = await antitrust_service.create_application(
        db_session,
        actor_id=uid,
        application_type="competitor_contact",
        title="業界団体会合での接触（テスト）",
        counterparty_name="競合A社",
        purpose="業界団体の定例会合",
    )
    assert app_row.application_no.startswith("AAP-")
    assert app_row.status == "submitted"

    approved = await antitrust_service.decide_application(
        db_session,
        application_id=app_row.id,
        actor_id=uid,
        decision="approved",
        decision_note="事業目的が明確なため承認",
    )
    assert approved.status == "approved"
    assert approved.approved_by == uid

    completed = await antitrust_service.complete_application(
        db_session,
        application_id=app_row.id,
        actor_id=uid,
        outcome_note="価格・数量に関する話題は一切なし。技術情報交換のみ。",
    )
    assert completed.status == "completed"
    assert completed.reported_at is not None


async def test_application_reject_flow(db_session) -> None:
    uid, _ = await _seed_user_and_contract(db_session)
    app_row = await antitrust_service.create_application(
        db_session,
        actor_id=uid,
        application_type="entertainment_gift",
        title="接待申請（テスト）",
        amount_jpy=50_000,
    )
    rejected = await antitrust_service.decide_application(
        db_session,
        application_id=app_row.id,
        actor_id=uid,
        decision="rejected",
        decision_note="金額が社内基準を超過",
    )
    assert rejected.status == "rejected"

    with pytest.raises(ConflictError):
        await antitrust_service.decide_application(
            db_session, application_id=app_row.id, actor_id=uid, decision="approved"
        )
    with pytest.raises(ConflictError):
        await antitrust_service.complete_application(
            db_session,
            application_id=app_row.id,
            actor_id=uid,
            outcome_note="実施した",
        )


async def test_application_cancel_flow(db_session) -> None:
    uid, _ = await _seed_user_and_contract(db_session)
    app_row = await antitrust_service.create_application(
        db_session,
        actor_id=uid,
        application_type="meeting_social",
        title="懇親会参加申請（テスト）",
    )
    cancelled = await antitrust_service.cancel_application(
        db_session,
        application_id=app_row.id,
        actor_id=uid,
        cancel_reason="予定変更のため取下げ",
    )
    assert cancelled.status == "cancelled"

    with pytest.raises(ConflictError):
        await antitrust_service.cancel_application(
            db_session, application_id=app_row.id, actor_id=uid, cancel_reason="再取下げ"
        )


async def test_create_application_invalid_type_raises(db_session) -> None:
    uid, _ = await _seed_user_and_contract(db_session)
    with pytest.raises(ValidationError):
        await antitrust_service.create_application(
            db_session, actor_id=uid, application_type="bogus", title="不正種別"
        )


async def test_create_application_negative_amount_raises(db_session) -> None:
    uid, _ = await _seed_user_and_contract(db_session)
    with pytest.raises(ValidationError):
        await antitrust_service.create_application(
            db_session,
            actor_id=uid,
            application_type="donation_sponsorship",
            title="寄付申請（テスト）",
            amount_jpy=-1,
        )


async def test_complete_application_requires_outcome_note(db_session) -> None:
    uid, _ = await _seed_user_and_contract(db_session)
    app_row = await antitrust_service.create_application(
        db_session,
        actor_id=uid,
        application_type="public_official_contact",
        title="公務員接触申請（テスト）",
    )
    await antitrust_service.decide_application(
        db_session, application_id=app_row.id, actor_id=uid, decision="approved"
    )
    with pytest.raises(ValidationError):
        await antitrust_service.complete_application(
            db_session, application_id=app_row.id, actor_id=uid, outcome_note="  "
        )


# ---------------------------------------------------------------------------
# #120 競争法 AI 相談
# ---------------------------------------------------------------------------


async def test_create_consultation_returns_disclaimer_and_citations(db_session) -> None:
    uid, _ = await _seed_user_and_contract(db_session)
    row = await antitrust_service.create_consultation(
        db_session, actor_id=uid, query_text="下請法の書面交付義務について教えてください"
    )
    assert row.query_text.startswith("下請法")
    assert isinstance(row.citations, list)
    assert row.answer_text  # 何らかの参考回答が生成される


async def test_create_consultation_requires_query_text(db_session) -> None:
    uid, _ = await _seed_user_and_contract(db_session)
    with pytest.raises(ValidationError):
        await antitrust_service.create_consultation(db_session, actor_id=uid, query_text="  ")


# ---------------------------------------------------------------------------
# #124 コンプライアンス研修履歴
# ---------------------------------------------------------------------------


async def test_create_training_with_user_id(db_session) -> None:
    uid, _ = await _seed_user_and_contract(db_session)
    row = await antitrust_service.create_training(
        db_session,
        actor_id=uid,
        training_title="独占禁止法コンプライアンス研修（テスト）",
        completed_at=date(2026, 4, 1),
        user_id=uid,
        score=90,
    )
    assert row.training_title.startswith("独占禁止法")
    assert row.category == "antitrust"


async def test_create_training_requires_user_or_attendee(db_session) -> None:
    uid, _ = await _seed_user_and_contract(db_session)
    with pytest.raises(ValidationError):
        await antitrust_service.create_training(
            db_session,
            actor_id=uid,
            training_title="研修（テスト）",
            completed_at=date(2026, 4, 1),
        )


async def test_create_training_missing_user_raises_not_found(db_session) -> None:
    uid, _ = await _seed_user_and_contract(db_session)
    with pytest.raises(NotFoundError):
        await antitrust_service.create_training(
            db_session,
            actor_id=uid,
            training_title="研修（テスト）",
            completed_at=date(2026, 4, 1),
            user_id=999999,
        )


async def test_list_trainings_filters_by_category(db_session) -> None:
    uid, _ = await _seed_user_and_contract(db_session)
    await antitrust_service.create_training(
        db_session,
        actor_id=uid,
        training_title="独禁法研修（テスト）",
        completed_at=date(2026, 4, 1),
        user_id=uid,
        category="antitrust",
    )
    await antitrust_service.create_training(
        db_session,
        actor_id=uid,
        training_title="情報セキュリティ研修（テスト）",
        completed_at=date(2026, 4, 2),
        user_id=uid,
        category="security",
    )
    # 共有 PG テスト DB には他テストが作った antitrust カテゴリの研修履歴も
    # 含まれうるため、本テストが作成した user_id で絞り込んで検証する。
    items, total = await antitrust_service.list_trainings(
        db_session, category="antitrust", user_id=uid
    )
    assert total == 1
    assert items[0].category == "antitrust"
