"""変更契約・追加工事・クレーム管理サービス（通知期限・失権リスク・累積影響）. """

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser
from app.models.change_order import ChangeOrder, ChangeOrderEvidence
from app.models.contract import Contract

# 通知期限の既定日数（設計変更等の申出は 14 日以内に書面通知が通例）
DEFAULT_NOTICE_DAYS = 14

_FORFEITURE_STATUSES = {"registered", "notice_sent", "in_consultation"}


def _forfeiture_warning(order: ChangeOrder, today: date | None = None) -> str | None:
    today = today or date.today()
    if order.status in _FORFEITURE_STATUSES and order.response_deadline is not None:
        if today > order.response_deadline:
            return (
                f"通知期限（{order.response_deadline.isoformat()}）を超過しています。"
                "失権リスクの可能性があるため、直ちに相手方へ書面通知を発出してください。"
            )
        remaining = (order.response_deadline - today).days
        if remaining <= 3:
            return (
                f"通知期限（{order.response_deadline.isoformat()}）まで残り {remaining} 日です。"
                "期限切れによる失権リスクに注意してください。"
            )
    return None


async def get_order(
    session: AsyncSession,
    *,
    order_id: int,
    viewer: CurrentUser,
    include_deleted: bool = False,
) -> ChangeOrder | None:
    stmt = select(ChangeOrder).where(ChangeOrder.id == order_id)
    if not include_deleted:
        stmt = stmt.where(ChangeOrder.deleted_at.is_(None))
    stmt = stmt.options(selectinload(ChangeOrder.evidence))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_change_order(
    session: AsyncSession,
    *,
    contract_id: int,
    actor: CurrentUser,
    data: dict[str, Any],
) -> ChangeOrder:
    contract = await session.get(Contract, contract_id)
    if contract is None or contract.deleted_at is not None:
        raise LookupError(f"Contract {contract_id} not found")

    requested_at = data.get("requested_at")
    deadline = data.get("response_deadline")
    if deadline is None and requested_at is not None:
        deadline = requested_at + timedelta(days=DEFAULT_NOTICE_DAYS)

    original = contract.amount
    original_int = int(original) if original is not None else None
    order = ChangeOrder(
        contract_id=contract_id,
        change_no=str(data.get("change_no") or f"CO-{uuid.uuid4().hex[:8].upper()}"),
        change_type=data["change_type"],
        title=data["title"],
        description=data.get("description"),
        requested_by=data.get("requested_by"),
        requested_at=requested_at,
        response_deadline=deadline,
        status=str(data.get("status") or "registered"),
        amount_jpy=data.get("amount_jpy"),
        schedule_impact_days=data.get("schedule_impact_days"),
        evidence_summary=data.get("evidence_summary") or {},
        original_amount_jpy=original_int,
        created_by=actor.db_id,
        updated_by=actor.db_id,
    )
    session.add(order)
    await session.flush()
    order.forfeiture_warning = _forfeiture_warning(order)
    order.cumulative_after_jpy = await _cumulative_amount(session, contract_id)
    await session.flush()
    await session.refresh(order)
    return order


async def _cumulative_amount(
    session: AsyncSession,
    contract_id: int,
) -> int | None:
    stmt = select(func.coalesce(func.sum(ChangeOrder.amount_jpy), 0)).where(
        ChangeOrder.contract_id == contract_id,
        ChangeOrder.status == "approved",
        ChangeOrder.deleted_at.is_(None),
        ChangeOrder.amount_jpy.is_not(None),
    )
    approved_delta = int((await session.execute(stmt)).scalar_one() or 0)
    contract = await session.get(Contract, contract_id)
    base = int(contract.amount) if contract is not None and contract.amount is not None else 0
    return base + approved_delta


async def list_change_orders(
    session: AsyncSession,
    *,
    contract_id: int | None = None,
    status: str | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[ChangeOrder], int]:
    stmt = select(ChangeOrder).where(ChangeOrder.deleted_at.is_(None))
    if contract_id is not None:
        stmt = stmt.where(ChangeOrder.contract_id == contract_id)
    if status:
        stmt = stmt.where(ChangeOrder.status == status)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(ChangeOrder.updated_at.desc()).offset((page - 1) * size).limit(size)
    rows = list((await session.execute(stmt)).scalars().all())
    return rows, total


async def update_change_order(
    session: AsyncSession,
    *,
    change_order_id: int,
    actor: CurrentUser,
    data: dict[str, Any],
) -> ChangeOrder:
    order = await get_order(session, order_id=change_order_id, viewer=actor)
    if order is None:
        raise LookupError(f"ChangeOrder {change_order_id} not found")
    for field, value in data.items():
        if hasattr(order, field):
            setattr(order, field, value)
    order.updated_by = actor.db_id
    await session.flush()
    order.forfeiture_warning = _forfeiture_warning(order)
    order.cumulative_after_jpy = await _cumulative_amount(session, order.contract_id)
    await session.flush()
    await session.refresh(order)
    return order


async def delete_order(
    session: AsyncSession,
    *,
    order_id: int,
    actor: CurrentUser,
) -> None:
    order = await get_order(session, order_id=order_id, viewer=actor)
    if order is None:
        raise LookupError(f"ChangeOrder {order_id} not found")
    order.deleted_at = datetime.now(UTC)
    order.updated_by = actor.db_id
    await session.flush()


async def add_evidence(
    session: AsyncSession,
    *,
    change_order_id: int,
    actor: CurrentUser,
    data: dict[str, Any],
) -> ChangeOrderEvidence:
    order = await get_order(session, order_id=change_order_id, viewer=actor)
    if order is None:
        raise LookupError(f"ChangeOrder {change_order_id} not found")
    evidence = ChangeOrderEvidence(
        change_order_id=change_order_id,
        evidence_type=data["evidence_type"],
        description=data.get("description"),
        occurred_at=data.get("occurred_at"),
        attachment_id=data.get("attachment_id"),
        created_by=actor.db_id,
        updated_by=actor.db_id,
    )
    session.add(evidence)
    await session.flush()
    await session.refresh(evidence)
    return evidence


async def impact_analysis(
    session: AsyncSession,
    *,
    contract_id: int,
    viewer: CurrentUser,
) -> dict[str, Any]:
    contract = await session.get(Contract, contract_id)
    if contract is None or contract.deleted_at is not None:
        raise LookupError(f"Contract {contract_id} not found")
    rows = list(
        (
            await session.execute(
                select(ChangeOrder).where(
                    ChangeOrder.contract_id == contract_id,
                    ChangeOrder.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    approved = [r for r in rows if r.status == "approved"]
    approved_delta = sum(int(r.amount_jpy or 0) for r in approved)
    base = int(contract.amount) if contract.amount is not None else 0
    return {
        "contract_id": contract_id,
        "original_amount_jpy": base if contract.amount is not None else None,
        "approved_delta_jpy": approved_delta,
        "cumulative_after_jpy": base + approved_delta,
        "order_count": len(rows),
        "approved_count": len(approved),
        "schedule_impact_days_total": sum(r.schedule_impact_days or 0 for r in approved),
        "forfeiture_risks": sum(1 for r in rows if _forfeiture_warning(r) is not None),
    }


__all__ = [
    "DEFAULT_NOTICE_DAYS",
    "add_evidence",
    "create_change_order",
    "delete_order",
    "get_order",
    "impact_analysis",
    "list_change_orders",
    "update_change_order",
]
