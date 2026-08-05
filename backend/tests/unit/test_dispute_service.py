"""紛争・クレーム管理サービスのユニットテスト（モックセッション）. """

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import dispute_service


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


def _dispute(**kwargs) -> MagicMock:
    d = MagicMock()
    d.id = kwargs.get("id", 1)
    d.dispute_no = kwargs.get("dispute_no", "D-ABC123")
    d.contract_id = kwargs.get("contract_id")
    d.dispute_type = kwargs.get("dispute_type", "claim")
    d.title = kwargs.get("title", "紛争")
    d.status = kwargs.get("status", "open")
    d.priority = kwargs.get("priority", "中")
    d.amount_claimed_jpy = kwargs.get("amount_claimed_jpy")
    d.reserve_amount_jpy = kwargs.get("reserve_amount_jpy")
    d.resolved_at = kwargs.get("resolved_at")
    d.deleted_at = kwargs.get("deleted_at")
    d.statute_limitations_date = kwargs.get("statute_limitations_date")
    d.notice_deadline = kwargs.get("notice_deadline")
    d.timeline = kwargs.get("timeline", [])
    d.evidence = kwargs.get("evidence", [])
    d.created_at = datetime.now(UTC)
    d.updated_at = datetime.now(UTC)
    return d


@pytest.mark.asyncio
async def test_create_dispute_sets_fields():
    session = _session()
    actor = _actor()
    dispute = await dispute_service.create_dispute(
        session,
        actor=actor,
        data={
            "contract_id": 10,
            "dispute_type": "claim",
            "title": "追加工事費の請求紛争",
            "counterparty": "テスト下請株式会社",
            "amount_claimed_jpy": 5000000,
            "reserve_amount_jpy": 3000000,
            "status": "open",
            "priority": "高",
        },
    )
    session.add.assert_called_once()
    assert dispute.dispute_no.startswith("D-")
    assert dispute.contract_id == 10
    assert dispute.amount_claimed_jpy == 5000000
    assert dispute.created_by == 1


@pytest.mark.asyncio
async def test_update_resolved_sets_resolved_at():
    session = _session()
    actor = _actor()
    d = _dispute(status="open")
    with patch.object(dispute_service, "get_dispute", new=AsyncMock(return_value=d)):
        updated = await dispute_service.update_dispute(
            session, dispute_id=1, actor=actor, data={"status": "resolved"}
        )
    assert updated.status == "resolved"
    assert updated.resolved_at is not None
    session.flush.assert_awaited()


@pytest.mark.asyncio
async def test_update_reopen_clears_resolved_at():
    session = _session()
    actor = _actor()
    d = _dispute(status="resolved", resolved_at=datetime.now(UTC))
    with patch.object(dispute_service, "get_dispute", new=AsyncMock(return_value=d)):
        updated = await dispute_service.update_dispute(
            session, dispute_id=1, actor=actor, data={"status": "open"}
        )
    assert updated.resolved_at is None


@pytest.mark.asyncio
async def test_add_timeline_and_evidence():
    session = _session()
    actor = _actor()
    d = _dispute()
    with patch.object(dispute_service, "get_dispute", new=AsyncMock(return_value=d)):
        event = await dispute_service.add_timeline_event(
            session,
            dispute_id=1,
            actor=actor,
            data={"event_type": "fact", "description": "事実記録"},
        )
        evidence = await dispute_service.add_evidence(
            session,
            dispute_id=1,
            actor=actor,
            data={
                "evidence_type": "photo",
                "description": "現場写真",
                "preserved": True,
            },
        )
    assert event.dispute_id == 1
    assert event.event_type == "fact"
    assert event.occurred_at is not None
    assert evidence.preserved is True


@pytest.mark.asyncio
async def test_exposure_summary():
    session = _session()
    rows = [
        _dispute(
            id=1,
            status="escalated",
            amount_claimed_jpy=1000000,
            reserve_amount_jpy=500000,
            notice_deadline=datetime.now(UTC).date(),
        ),
        _dispute(id=2, status="open"),
        _dispute(id=3, status="closed"),
    ]
    result_obj = MagicMock()
    result_obj.scalars.return_value.all.return_value = rows
    session.execute = AsyncMock(return_value=result_obj)
    result = await dispute_service.exposure_summary(session)
    assert result["by_status"]["escalated"]["count"] == 1
    assert result["by_status"]["open"]["count"] == 1
    assert result["total_claimed_jpy"] == 1000000
    assert result["total_reserve_jpy"] == 500000
    assert result["deadlines_within_180d"] == 1


@pytest.mark.asyncio
async def test_delete_dispute_sets_deleted_at():
    session = _session()
    actor = _actor()
    d = _dispute()
    with patch.object(dispute_service, "get_dispute", new=AsyncMock(return_value=d)):
        await dispute_service.delete_dispute(session, dispute_id=1, actor=actor)
    assert d.deleted_at is not None
