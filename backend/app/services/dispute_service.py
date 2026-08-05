"""紛争・クレーム・事故・債権管理サービス."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser
from app.models.dispute import Dispute, DisputeEvidence, DisputeTimelineEvent


def _next_dispute_no() -> str:
    return f"D-{uuid.uuid4().hex[:10].upper()}"


async def create_dispute(
    session: AsyncSession,
    *,
    actor: CurrentUser,
    data: dict[str, Any],
) -> Dispute:
    dispute = Dispute(
        dispute_no=_next_dispute_no(),
        contract_id=data.get("contract_id"),
        dispute_type=data["dispute_type"],
        title=data["title"],
        description=data.get("description"),
        status=str(data.get("status") or "open"),
        priority=str(data.get("priority") or "中"),
        counterparty=data.get("counterparty"),
        amount_claimed_jpy=data.get("amount_claimed_jpy"),
        reserve_amount_jpy=data.get("reserve_amount_jpy"),
        assignee_id=data.get("assignee_id"),
        statute_limitations_date=data.get("statute_limitations_date"),
        notice_deadline=data.get("notice_deadline"),
        resolution_method=str(data.get("resolution_method") or "negotiation"),
        legal_hold_id=data.get("legal_hold_id"),
        exposure=data.get("exposure") or {},
        created_by=actor.db_id,
        updated_by=actor.db_id,
    )
    session.add(dispute)
    await session.flush()
    await session.refresh(dispute)
    return dispute


async def get_dispute(
    session: AsyncSession,
    *,
    dispute_id: int,
    viewer: CurrentUser,
    include_deleted: bool = False,
) -> Dispute | None:
    stmt = select(Dispute).where(Dispute.id == dispute_id)
    if not include_deleted:
        stmt = stmt.where(Dispute.deleted_at.is_(None))
    stmt = stmt.options(
        selectinload(Dispute.timeline),
        selectinload(Dispute.evidence),
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_disputes(
    session: AsyncSession,
    *,
    q: str | None = None,
    status: str | None = None,
    dispute_type: str | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[Dispute], int]:
    stmt = select(Dispute).where(Dispute.deleted_at.is_(None))
    if q:
        stmt = stmt.where(
            Dispute.title.ilike(f"%{q}%")
            | Dispute.dispute_no.ilike(f"%{q}%")
            | Dispute.counterparty.ilike(f"%{q}%")
        )
    if status:
        stmt = stmt.where(Dispute.status == status)
    if dispute_type:
        stmt = stmt.where(Dispute.dispute_type == dispute_type)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(Dispute.updated_at.desc()).offset((page - 1) * size).limit(size)
    rows = list((await session.execute(stmt)).scalars().all())
    return rows, total


async def update_dispute(
    session: AsyncSession,
    *,
    dispute_id: int,
    actor: CurrentUser,
    data: dict[str, Any],
) -> Dispute:
    dispute = await get_dispute(session, dispute_id=dispute_id, viewer=actor)
    if dispute is None:
        raise LookupError(f"Dispute {dispute_id} not found")
    for field, value in data.items():
        if hasattr(dispute, field):
            setattr(dispute, field, value)
    if dispute.status in {"resolved", "closed"} and dispute.resolved_at is None:
        dispute.resolved_at = datetime.now(UTC)
    elif dispute.status not in {"resolved", "closed"}:
        dispute.resolved_at = None
    dispute.updated_by = actor.db_id
    await session.flush()
    await session.refresh(dispute)
    return dispute


async def delete_dispute(
    session: AsyncSession,
    *,
    dispute_id: int,
    actor: CurrentUser,
) -> None:
    dispute = await get_dispute(session, dispute_id=dispute_id, viewer=actor)
    if dispute is None:
        raise LookupError(f"Dispute {dispute_id} not found")
    dispute.deleted_at = datetime.now(UTC)
    dispute.updated_by = actor.db_id
    await session.flush()


async def add_timeline_event(
    session: AsyncSession,
    *,
    dispute_id: int,
    actor: CurrentUser,
    data: dict[str, Any],
) -> DisputeTimelineEvent:
    dispute = await get_dispute(session, dispute_id=dispute_id, viewer=actor)
    if dispute is None:
        raise LookupError(f"Dispute {dispute_id} not found")
    event = DisputeTimelineEvent(
        dispute_id=dispute_id,
        occurred_at=data.get("occurred_at") or datetime.now(UTC),
        event_type=data["event_type"],
        description=data.get("description"),
        created_by=actor.db_id,
        updated_by=actor.db_id,
    )
    session.add(event)
    await session.flush()
    await session.refresh(event)
    return event


async def add_evidence(
    session: AsyncSession,
    *,
    dispute_id: int,
    actor: CurrentUser,
    data: dict[str, Any],
) -> DisputeEvidence:
    dispute = await get_dispute(session, dispute_id=dispute_id, viewer=actor)
    if dispute is None:
        raise LookupError(f"Dispute {dispute_id} not found")
    evidence = DisputeEvidence(
        dispute_id=dispute_id,
        evidence_type=data["evidence_type"],
        description=data.get("description"),
        occurred_at=data.get("occurred_at"),
        attachment_id=data.get("attachment_id"),
        preserved=bool(data.get("preserved")),
        created_by=actor.db_id,
        updated_by=actor.db_id,
    )
    session.add(evidence)
    await session.flush()
    await session.refresh(evidence)
    return evidence


async def exposure_summary(session: AsyncSession) -> dict[str, Any]:
    """紛争エクスポージャー集計（経営層向け）。"""
    rows = list(
        (
            await session.execute(
                select(Dispute).where(Dispute.deleted_at.is_(None))
            )
        )
        .scalars()
        .all()
    )
    by_status: dict[str, dict[str, int]] = {}
    for row in rows:
        bucket = by_status.setdefault(row.status, {"count": 0})
        bucket["count"] += 1
    today = date.today()
    deadline_cutoff = today + timedelta(days=180)
    deadlines = sum(
        1
        for row in rows
        if row.status in {"open", "investigating", "escalated"}
        and (
            (
                row.statute_limitations_date is not None
                and row.statute_limitations_date <= deadline_cutoff
            )
            or (row.notice_deadline is not None and row.notice_deadline <= deadline_cutoff)
        )
    )
    return {
        "by_status": by_status,
        "total_claimed_jpy": sum(row.amount_claimed_jpy or 0 for row in rows),
        "total_reserve_jpy": sum(row.reserve_amount_jpy or 0 for row in rows),
        "deadlines_within_180d": deadlines,
    }


__all__ = [
    "add_evidence",
    "add_timeline_event",
    "create_dispute",
    "delete_dispute",
    "exposure_summary",
    "get_dispute",
    "list_disputes",
    "update_dispute",
]
