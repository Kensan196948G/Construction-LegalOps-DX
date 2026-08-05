"""変更契約サービスのユニットテスト（通知期限・失権リスク・累積影響）. """

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import change_order_service
from app.services.change_order_service import _forfeiture_warning


def _actor(user_id: int = 1) -> MagicMock:
    actor = MagicMock()
    actor.role = "admin"
    actor.db_id = user_id
    return actor


def _session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock(return_value=None)
    session.refresh = AsyncMock(side_effect=lambda obj: obj)
    return session


def _order(**kwargs) -> MagicMock:
    o = MagicMock()
    o.id = kwargs.get("id", 1)
    o.contract_id = kwargs.get("contract_id", 1)
    o.change_no = kwargs.get("change_no", "CO-001")
    o.change_type = kwargs.get("change_type", "design_change")
    o.title = kwargs.get("title", "変更")
    o.status = kwargs.get("status", "registered")
    o.requested_at = kwargs.get("requested_at")
    o.response_deadline = kwargs.get("response_deadline")
    o.amount_jpy = kwargs.get("amount_jpy")
    o.schedule_impact_days = kwargs.get("schedule_impact_days")
    o.forfeiture_warning = kwargs.get("forfeiture_warning")
    o.original_amount_jpy = kwargs.get("original_amount_jpy")
    o.cumulative_after_jpy = kwargs.get("cumulative_after_jpy")
    o.deleted_at = kwargs.get("deleted_at")
    o.updated_by = kwargs.get("updated_by")
    return o


def _contract(amount: int = 10000000) -> MagicMock:
    c = MagicMock()
    c.id = 1
    c.amount = Decimal(amount)
    c.deleted_at = None
    return c


@pytest.mark.asyncio
async def test_create_change_order_auto_notice_deadline():
    session = _session()
    actor = _actor()
    contract = _contract()
    session.get = AsyncMock(return_value=contract)
    zero_result = MagicMock()
    zero_result.scalar_one.return_value = 0
    session.execute = AsyncMock(return_value=zero_result)

    order = await change_order_service.create_change_order(
        session,
        contract_id=1,
        actor=actor,
        data={
            "change_type": "design_change",
            "title": "設計変更指示",
            "requested_at": date(2026, 8, 1),
            "amount_jpy": 500000,
        },
    )
    assert order.response_deadline == date(2026, 8, 15)
    assert order.original_amount_jpy == 10000000
    assert order.cumulative_after_jpy == 10000000
    assert order.change_no.startswith("CO-")


def test_forfeiture_warning_after_deadline():
    order = _order(response_deadline=date.today() - timedelta(days=1))
    warning = _forfeiture_warning(order)
    assert warning is not None
    assert "失権" in warning


def test_forfeiture_warning_none_within_deadline():
    order = _order(response_deadline=date.today() + timedelta(days=30))
    assert _forfeiture_warning(order) is None


def test_forfeiture_warning_none_when_approved():
    order = _order(status="approved", response_deadline=date.today() - timedelta(days=10))
    assert _forfeiture_warning(order) is None


@pytest.mark.asyncio
async def test_update_change_order_updates_cumulative():
    session = _session()
    actor = _actor()
    contract = _contract(amount=10000000)
    order = _order(
        contract_id=1,
        status="registered",
        amount_jpy=2000000,
        original_amount_jpy=10000000,
    )
    session.get = AsyncMock(return_value=contract)
    delta_result = MagicMock()
    delta_result.scalar_one.return_value = 2000000
    session.execute = AsyncMock(return_value=delta_result)
    with patch.object(
        change_order_service, "get_order", new=AsyncMock(return_value=order)
    ):
        updated = await change_order_service.update_change_order(
            session,
            change_order_id=1,
            actor=actor,
            data={"status": "approved"},
        )
    assert updated.cumulative_after_jpy == 12000000
    assert updated.updated_by == 1


@pytest.mark.asyncio
async def test_impact_analysis():
    session = _session()
    actor = _actor()
    contract = _contract(amount=10000000)
    session.get = AsyncMock(return_value=contract)
    rows = [
        _order(id=1, status="approved", amount_jpy=2000000, schedule_impact_days=10),
        _order(
            id=2,
            status="registered",
            amount_jpy=1000000,
            response_deadline=date.today() - timedelta(days=2),
        ),
    ]
    result_obj = MagicMock()
    result_obj.scalars.return_value.all.return_value = rows
    session.execute = AsyncMock(return_value=result_obj)

    impact = await change_order_service.impact_analysis(
        session, contract_id=1, viewer=actor
    )
    assert impact["approved_delta_jpy"] == 2000000
    assert impact["cumulative_after_jpy"] == 12000000
    assert impact["schedule_impact_days_total"] == 10
    assert impact["forfeiture_risks"] == 1


@pytest.mark.asyncio
async def test_delete_order_sets_deleted_at():
    session = _session()
    actor = _actor()
    order = _order()
    with patch.object(
        change_order_service, "get_order", new=AsyncMock(return_value=order)
    ):
        await change_order_service.delete_order(session, order_id=1, actor=actor)
    assert order.deleted_at is not None
    assert order.updated_by == 1
