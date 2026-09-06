"""価格協議・ダンピング警告サービスの単体テスト（#21/#23/#24）."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.department import Department
from app.models.user import User
from app.services import labor_wage_service, price_consultation_service


async def _seed_user(db_session) -> int:
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
    return int(user.id)


async def _seed_standard(db_session, uid: int, amount: int = 20_000) -> None:
    await labor_wage_service.upsert_standard(
        db_session,
        actor_id=uid,
        work_type="土木",
        amount_jpy=amount,
        effective_from=date(2026, 1, 1),
        source_ref="2026年1月基準",
    )


async def test_dumping_check_ok_watch_warning_critical(db_session) -> None:
    """#21: 乖離率からの深刻度導出（none/watch/warning/critical）."""
    # 基準 20,000 に対して:
    assert labor_wage_service._derive_severity("ok", 0.0) == "none"
    assert labor_wage_service._derive_severity("below", 0.05) == "watch"
    assert labor_wage_service._derive_severity("below", 0.10) == "warning"
    assert labor_wage_service._derive_severity("below", 0.25) == "critical"


async def test_discrepancy_includes_severity_and_dumping(db_session) -> None:
    """#20+#21: discrepancy が severity / dumping を含む."""
    uid = await _seed_user(db_session)
    await _seed_standard(db_session, uid, amount=20_000)

    ok = await labor_wage_service.discrepancy(db_session, work_type="土木", quote_day_jpy=22_000)
    assert ok["severity"] == "none" and ok["dumping"] is False

    below = await labor_wage_service.discrepancy(db_session, work_type="土木", quote_day_jpy=17_000)
    assert below["status"] == "below"
    assert below["severity"] == "warning"  # 不足率 15%
    assert below["dumping"] is True

    critical = await labor_wage_service.discrepancy(
        db_session, work_type="土木", quote_day_jpy=15_000
    )
    assert critical["severity"] == "critical"  # 不足率 25%
    assert critical["dumping"] is True


async def test_create_log_with_snapshot(db_session) -> None:
    """#24: 協議申出は乖離スナップショット付きで記録される."""
    uid = await _seed_user(db_session)
    await _seed_standard(db_session, uid, amount=20_000)

    row = await price_consultation_service.create_log(
        db_session,
        actor_id=uid,
        direction="from_subcontractor",
        work_type="土木",
        quote_day_jpy=15_000,
        summary="単価引上げ協議の申出（デモ）",
        requested_at=date(2026, 2, 1),
    )
    assert row.log_no.startswith("LC-")
    assert row.status == "open"
    assert row.standard_day_jpy == 20_000
    assert row.severity == "critical"
    assert row.shortage_rate is not None and row.shortage_rate > 0


async def test_respond_and_cancel_transitions(db_session) -> None:
    """#24: respond (open→responded)・cancel (open→cancelled)."""
    uid = await _seed_user(db_session)
    row = await price_consultation_service.create_log(
        db_session,
        actor_id=uid,
        direction="to_subcontractor",
        work_type="舗装",
        summary="価格確認（デモ）",
    )
    responded = await price_consultation_service.respond_log(
        db_session,
        log_id=row.id,
        actor_id=uid,
        response_summary="協議内容を確認しました（デモ回答）。",
    )
    assert responded.status == "responded"
    assert responded.responded_at is not None

    # responded への再回答・取消は 409
    with pytest.raises(ConflictError):
        await price_consultation_service.respond_log(
            db_session, log_id=row.id, actor_id=uid, response_summary="2回目"
        )
    with pytest.raises(ConflictError):
        await price_consultation_service.cancel_log(
            db_session, log_id=row.id, actor_id=uid, reason="遅すぎる"
        )

    row2 = await price_consultation_service.create_log(
        db_session,
        actor_id=uid,
        direction="to_subcontractor",
        work_type="解体",
        summary="価格確認（デモ・取消用）",
    )
    cancelled = await price_consultation_service.cancel_log(
        db_session, log_id=row2.id, actor_id=uid, reason="取下げ（デモ）"
    )
    assert cancelled.status == "cancelled"


async def test_invalid_direction_and_quote(db_session) -> None:
    """不正な direction / 負の単価は 422."""
    uid = await _seed_user(db_session)
    with pytest.raises(ValidationError):
        await price_consultation_service.create_log(
            db_session,
            actor_id=uid,
            direction="bogus",
            work_type="土木",
            summary="不正",
        )
    with pytest.raises(ValidationError):
        await price_consultation_service.create_log(
            db_session,
            actor_id=uid,
            direction="from_subcontractor",
            work_type="土木",
            quote_day_jpy=-1,
            summary="不正",
        )


async def test_list_and_monitor_filters(db_session) -> None:
    """#23: 未回答監視は open のみ・深刻度絞り込み可能.

    共有 PG テスト DB には他テストが作った open/critical な協議ログも
    含まれうるため、絶対件数ではなくシード前後の差分で検証する。
    """
    uid = await _seed_user(db_session)
    await _seed_standard(db_session, uid, amount=20_000)

    _, total_before = await price_consultation_service.list_open_monitor(db_session)
    _, crit_total_before = await price_consultation_service.list_open_monitor(
        db_session, severity="critical"
    )
    _, all_total_before = await price_consultation_service.list_logs(db_session)

    critical_row = await price_consultation_service.create_log(
        db_session,
        actor_id=uid,
        direction="from_subcontractor",
        work_type="土木",
        quote_day_jpy=15_000,
        summary="深刻な協議（デモ）",
    )
    await price_consultation_service.create_log(
        db_session,
        actor_id=uid,
        direction="from_subcontractor",
        work_type="土木",
        quote_day_jpy=19_500,
        summary="軽微な協議（デモ）",
    )
    _, total = await price_consultation_service.list_open_monitor(db_session)
    assert total - total_before == 2

    crit_rows, crit_total = await price_consultation_service.list_open_monitor(
        db_session, severity="critical"
    )
    assert crit_total - crit_total_before == 1
    assert any(row.id == critical_row.id and row.severity == "critical" for row in crit_rows)

    _, all_total = await price_consultation_service.list_logs(db_session)
    assert all_total - all_total_before == 2

    with pytest.raises(NotFoundError):
        await price_consultation_service.get_log(db_session, log_id=999_999)
