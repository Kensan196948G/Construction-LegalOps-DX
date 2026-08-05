"""AI 入出力保持期限・パージ処理のテスト."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.models.contract import Contract
from app.models.department import Department
from app.models.legal_review import LegalReview
from app.models.user import User
from app.services import legal_hold_service, retention_service


async def _seed_review(db_session, *, finished_days_ago: int = 400) -> tuple[int, int]:
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
        title="テスト契約",
        counterparty="株式会社テスト",
        contract_type="請負",
        department_id=dept.id,
        drafter_id=user.id,
    )
    db_session.add(contract)
    await db_session.flush()
    review = LegalReview(
        contract_id=contract.id,
        review_type="ai",
        status="completed",
        ai_model="stub",
        summary="AI レビュー結果",
        overall_risk="medium",
        result={"issues": [{"code": "x"}]},
        finished_at=datetime.now(UTC) - timedelta(days=finished_days_ago),
        started_at=datetime.now(UTC) - timedelta(days=finished_days_ago + 1),
    )
    db_session.add(review)
    await db_session.flush()
    return int(contract.id), int(review.id)


async def test_default_settings(db_session) -> None:
    settings = await retention_service.get_settings(db_session)
    assert settings["ai_retention_days"] == retention_service.DEFAULT_AI_RETENTION_DAYS
    assert settings["audit_export_dir"] == retention_service.DEFAULT_AUDIT_EXPORT_DIR


async def test_update_settings(db_session) -> None:
    updated = await retention_service.update_settings(
        db_session, values={"ai_retention_days": 180}, actor_id=1
    )
    assert updated["ai_retention_days"] == 180
    reloaded = await retention_service.get_settings(db_session)
    assert reloaded["ai_retention_days"] == 180


async def test_purge_ai_artifacts_older_than_threshold(db_session) -> None:
    _, review_id = await _seed_review(db_session, finished_days_ago=400)
    result = await retention_service.purge_ai_artifacts(
        db_session, older_than_days=365
    )
    assert result["purged"] == 1
    review = await db_session.get(LegalReview, review_id)
    assert review.result == {}
    assert "削除済み" in (review.summary or "")


async def test_purge_skips_legal_hold(db_session) -> None:
    contract_id, review_id = await _seed_review(db_session, finished_days_ago=400)
    await legal_hold_service.start_legal_hold(
        db_session, contract_id=contract_id, reason="証拠保全", requested_by=1
    )
    result = await retention_service.purge_ai_artifacts(
        db_session, older_than_days=365
    )
    assert result["purged"] == 0
    assert result["skipped_legal_hold"] == 1
    review = await db_session.get(LegalReview, review_id)
    assert review.result != {}


async def test_purge_keeps_recent_artifacts(db_session) -> None:
    _, review_id = await _seed_review(db_session, finished_days_ago=30)
    result = await retention_service.purge_ai_artifacts(
        db_session, older_than_days=365
    )
    assert result["purged"] == 0
    review = await db_session.get(LegalReview, review_id)
    assert review.result != {}


async def test_update_unknown_key_raises(db_session) -> None:
    import pytest

    with pytest.raises(ValueError):
        await retention_service.update_settings(
            db_session, values={"unknown_key": 1}, actor_id=1
        )
