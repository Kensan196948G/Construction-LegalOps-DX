"""労務費基準マスタサービスの単体テスト（Issue #111・#16〜#20）."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.models.department import Department
from app.models.user import User
from app.services import labor_wage_service


async def _seed_user(db_session) -> int:
    dept = Department(code=f"D-{uuid4().hex[:8]}", name="法務部")
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


async def _seed_standards(db_session, uid: int) -> None:
    """土木の全国基準を 2 期（2026/1〜・2026/7〜）登録する."""
    await labor_wage_service.upsert_standard(
        db_session,
        actor_id=uid,
        work_type="土木",
        amount_jpy=20_000,
        effective_from=date(2026, 1, 1),
        source_ref="2026年1月基準",
    )
    await labor_wage_service.upsert_standard(
        db_session,
        actor_id=uid,
        work_type="土木",
        amount_jpy=22_000,
        effective_from=date(2026, 7, 1),
        source_ref="2026年7月基準（更新）",
    )


async def test_latest_resolution_by_as_of(db_session) -> None:
    """#16: as-of 日で適用中の最新基準を解決する."""
    uid = await _seed_user(db_session)
    await _seed_standards(db_session, uid)

    latest_jun = await labor_wage_service.resolve_latest(
        db_session, work_type="土木", as_of=date(2026, 6, 30)
    )
    assert latest_jun.amount_jpy == 20_000
    latest_dec = await labor_wage_service.resolve_latest(
        db_session, work_type="土木", as_of=date(2026, 12, 1)
    )
    assert latest_dec.amount_jpy == 22_000
    assert latest_dec.source_ref == "2026年7月基準（更新）"


async def test_effective_to_closes_period(db_session) -> None:
    """適用終了後は解決対象外・期間外は 404."""
    uid = await _seed_user(db_session)
    await labor_wage_service.upsert_standard(
        db_session,
        actor_id=uid,
        work_type="舗装",
        amount_jpy=25_000,
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 6, 30),
    )
    inside = await labor_wage_service.resolve_latest(
        db_session, work_type="舗装", as_of=date(2026, 3, 1)
    )
    assert inside.amount_jpy == 25_000
    with pytest.raises(NotFoundError):
        await labor_wage_service.resolve_latest(
            db_session, work_type="舗装", as_of=date(2026, 12, 1)
        )


async def test_discrepancy_ok_and_below(db_session) -> None:
    """#20: 基準以上 ok・基準未満 below（不足率付き）."""
    uid = await _seed_user(db_session)
    await _seed_standards(db_session, uid)

    ok = await labor_wage_service.discrepancy(db_session, work_type="土木", quote_day_jpy=23_000)
    assert ok["status"] == "ok" and ok["ratio"] >= 1.0

    below = await labor_wage_service.discrepancy(db_session, work_type="土木", quote_day_jpy=19_000)
    assert below["status"] == "below"
    assert below["shortage_rate"] > 0
    # 2026-12 as_of では最新 22,000 に対して 19,000 → 不足率 = 1 - 19/22
    assert below["standard_day_jpy"] == 22_000


async def test_validation_and_list(db_session) -> None:
    """不正工種・負値 422・一覧絞り込み."""
    uid = await _seed_user(db_session)
    with pytest.raises(ValidationError):
        await labor_wage_service.upsert_standard(
            db_session,
            actor_id=uid,
            work_type="不明",
            amount_jpy=1000,
            effective_from=date(2026, 1, 1),
        )
    with pytest.raises(ValidationError):
        await labor_wage_service.discrepancy(db_session, work_type="土木", quote_day_jpy=-1)

    await _seed_standards(db_session, uid)
    _, total = await labor_wage_service.list_standards(db_session, work_type="土木")
    assert total == 2
    rows_asof, _ = await labor_wage_service.list_standards(
        db_session, work_type="土木", as_of=date(2026, 1, 15)
    )
    assert len(rows_asof) == 1
