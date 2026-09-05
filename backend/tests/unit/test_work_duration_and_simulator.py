"""標準工期マスタ・短工期判定・価格転嫁シミュレータの単体テスト（#22/#25/#26）."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.models.department import Department
from app.models.user import User
from app.services import price_simulator_service, work_duration_service


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


async def _seed_duration(db_session, uid: int, *, days: int = 120) -> None:
    await work_duration_service.upsert_duration(
        db_session,
        actor_id=uid,
        work_type="土木",
        amount_min_jpy=10_000_000,
        amount_max_jpy=50_000_000,
        standard_days=days,
        effective_from=date(2026, 1, 1),
        source_ref="標準工期設定要領（架空）",
    )


async def test_resolve_duration_band_and_prefecture_fallback(db_session) -> None:
    """#22: 金額帯解決・都道府県フォールバック."""
    uid = await _seed_user(db_session)
    await _seed_duration(db_session, uid, days=120)

    row = await work_duration_service.resolve_standard_duration(
        db_session, work_type="土木", amount_jpy=20_000_000
    )
    assert row.standard_days == 120

    with pytest.raises(NotFoundError):
        await work_duration_service.resolve_standard_duration(
            db_session, work_type="土木", amount_jpy=200_000_000
        )
    with pytest.raises(NotFoundError):
        await work_duration_service.resolve_standard_duration(
            db_session, work_type="舗装", amount_jpy=20_000_000
        )


async def test_short_duration_check_severities(db_session) -> None:
    """#22: 短縮率からの深刻度導出（ok/watch/warning/critical）."""
    uid = await _seed_user(db_session)
    await _seed_duration(db_session, uid, days=100)

    ok = await work_duration_service.short_duration_check(
        db_session, work_type="土木", amount_jpy=20_000_000, planned_days=110
    )
    assert ok["status"] == "ok" and ok["severity"] == "none"

    watch = await work_duration_service.short_duration_check(
        db_session, work_type="土木", amount_jpy=20_000_000, planned_days=95
    )
    assert watch["status"] == "short" and watch["severity"] == "watch"

    warning = await work_duration_service.short_duration_check(
        db_session, work_type="土木", amount_jpy=20_000_000, planned_days=85
    )
    assert warning["severity"] == "warning"

    critical = await work_duration_service.short_duration_check(
        db_session, work_type="土木", amount_jpy=20_000_000, planned_days=75
    )
    assert critical["severity"] == "critical"
    assert critical["shorten_rate"] >= 0.20


async def test_duration_validation(db_session) -> None:
    """不正入力 422（負金額・0日工期・不正期間）."""
    uid = await _seed_user(db_session)
    with pytest.raises(ValidationError):
        await work_duration_service.upsert_duration(
            db_session,
            actor_id=uid,
            work_type="土木",
            amount_min_jpy=-1,
            standard_days=100,
            effective_from=date(2026, 1, 1),
        )
    with pytest.raises(ValidationError):
        await work_duration_service.upsert_duration(
            db_session,
            actor_id=uid,
            work_type="土木",
            amount_min_jpy=1_000,
            standard_days=0,
            effective_from=date(2026, 1, 1),
        )
    await _seed_duration(db_session, uid, days=100)
    with pytest.raises(ValidationError):
        await work_duration_service.short_duration_check(
            db_session, work_type="土木", amount_jpy=20_000_000, planned_days=0
        )


def test_price_simulator_up_and_down() -> None:
    """#25/#26: 転嫁額・調整後金額（上昇/下落/平坦）."""
    up = price_simulator_service.simulate_price_pass_through(
        contract_amount_jpy=100_000_000,
        labor_cost_jpy=20_000_000,
        material_cost_jpy=30_000_000,
        labor_change_rate=0.08,
        material_change_rate=0.05,
        pass_through_rate=0.5,
    )
    # 労務 +1.6M・材料 +1.5M → 合計 +3.1M → 転嫁 50% = 1.55M
    assert up["labor_delta_jpy"] == 1_600_000
    assert up["material_delta_jpy"] == 1_500_000
    assert up["total_delta_jpy"] == 3_100_000
    assert up["pass_through_amount_jpy"] == 1_550_000
    assert up["adjusted_amount_jpy"] == 101_550_000
    assert up["direction"] == "up"

    down = price_simulator_service.simulate_price_pass_through(
        contract_amount_jpy=10_000_000,
        labor_cost_jpy=1_000_000,
        material_cost_jpy=2_000_000,
        labor_change_rate=-0.10,
        material_change_rate=0.0,
        pass_through_rate=1.0,
    )
    assert down["pass_through_amount_jpy"] == -100_000
    assert down["adjusted_amount_jpy"] == 9_900_000
    assert down["direction"] == "down"

    flat = price_simulator_service.simulate_price_pass_through(
        contract_amount_jpy=5_000_000,
        labor_cost_jpy=1_000_000,
        material_cost_jpy=1_000_000,
        labor_change_rate=0.0,
        material_change_rate=0.0,
        pass_through_rate=0.8,
    )
    assert flat["direction"] == "flat"


def test_price_simulator_validation() -> None:
    """不正入力 422（負値・転嫁率範囲外・変動率下限）."""
    with pytest.raises(ValidationError):
        price_simulator_service.simulate_price_pass_through(
            contract_amount_jpy=-1,
            labor_cost_jpy=0,
            material_cost_jpy=0,
            labor_change_rate=0.0,
            material_change_rate=0.0,
            pass_through_rate=0.5,
        )
    with pytest.raises(ValidationError):
        price_simulator_service.simulate_price_pass_through(
            contract_amount_jpy=100,
            labor_cost_jpy=0,
            material_cost_jpy=0,
            labor_change_rate=0.0,
            material_change_rate=0.0,
            pass_through_rate=1.5,
        )
    with pytest.raises(ValidationError):
        price_simulator_service.simulate_price_pass_through(
            contract_amount_jpy=100,
            labor_cost_jpy=0,
            material_cost_jpy=0,
            labor_change_rate=-1.5,
            material_change_rate=0.0,
            pass_through_rate=0.5,
        )
