"""Risk service — SQLAlchemy CRUD implementation.

Replaces the Loop 5 stub with concrete database operations over
:class:`~app.models.risk_item.RiskItem`.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.risk_item import RiskItem
from app.schemas.risk import RiskAggregate, RiskUpdate

# Roles that can see every record regardless of ownership.
_FULL_ACCESS_ROLES = {"admin", "legal", "auditor", "reviewer", "approver"}

_RISK_DISCLAIMER = (
    "本リスク評価は AI / ルール出力の参考情報です。最終判断は法務担当者"
    "および顧問弁護士が行ってください。"
)


def _is_full_access(viewer: Any) -> bool:
    return getattr(viewer, "role", None) in _FULL_ACCESS_ROLES


def _to_dict(risk: RiskItem) -> dict[str, Any]:
    """Convert a RiskItem ORM row to a dict compatible with RiskOut schema.

    ``category`` is exposed as ``title`` because the API schema uses that field
    name (RiskOut.title) while the DB column is named ``category``.
    ``department_id`` is not stored on RiskItem; we return ``None``.
    """
    return {
        "id": risk.id,
        "contract_id": risk.contract_id,
        "severity": risk.severity,
        "status": risk.status,
        "title": risk.category,  # category -> title mapping
        "description": risk.description,
        "mitigation": risk.mitigation,
        "owner_id": risk.owner_id,
        "department_id": None,  # no column on RiskItem
        "due_date": risk.due_date,
        "created_at": risk.created_at,
        "updated_at": risk.updated_at,
    }


async def list_risks(
    session: AsyncSession,
    *,
    viewer: Any,
    severity: str | None = None,
    status: str | None = None,
    contract_id: int | None = None,
    owner_id: int | None = None,
    department_id: int | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    """Return paginated risk items with optional filters.

    Row-level scoping:
    - admin / legal / auditor / reviewer / approver: all non-deleted rows
    - others: only rows whose contract was drafted by the viewer
    """
    stmt = select(RiskItem).where(RiskItem.deleted_at.is_(None))

    if not _is_full_access(viewer):
        # Restrict to contracts where this user is the drafter.
        from app.models.contract import Contract  # local import avoids circular dep

        stmt = stmt.join(Contract, Contract.id == RiskItem.contract_id).where(
            Contract.drafter_id == viewer.id
        )

    if severity is not None:
        stmt = stmt.where(RiskItem.severity == severity)
    if status is not None:
        stmt = stmt.where(RiskItem.status == status)
    if contract_id is not None:
        stmt = stmt.where(RiskItem.contract_id == contract_id)
    if owner_id is not None:
        stmt = stmt.where(RiskItem.owner_id == owner_id)
    # department_id filter: RiskItem has no department column; ignore silently.

    # Total count (reuse the filtered query, strip ordering).
    count_q = await session.execute(stmt.with_only_columns(func.count(RiskItem.id)).order_by(None))
    total: int = count_q.scalar() or 0

    stmt = stmt.order_by(RiskItem.id.desc()).offset((page - 1) * size).limit(size)
    rows = await session.execute(stmt)
    items = [_to_dict(r) for r in rows.scalars()]
    return items, total


async def aggregate(
    session: AsyncSession,
    *,
    viewer: Any,
    department_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> RiskAggregate:
    """Return aggregated risk KPIs for the heat-map / dashboard."""

    base = select(RiskItem).where(RiskItem.deleted_at.is_(None))

    if not _is_full_access(viewer):
        from app.models.contract import Contract

        base = base.join(Contract, Contract.id == RiskItem.contract_id).where(
            Contract.drafter_id == viewer.id
        )

    # Optional date range filter on due_date.
    if date_from:
        try:
            from_date = date.fromisoformat(date_from)
            base = base.where(RiskItem.due_date >= from_date)
        except ValueError:
            pass
    if date_to:
        try:
            to_date = date.fromisoformat(date_to)
            base = base.where(RiskItem.due_date <= to_date)
        except ValueError:
            pass

    # ---- by_severity -------------------------------------------------------
    severity_q = await session.execute(
        base.with_only_columns(RiskItem.severity, func.count(RiskItem.id))
        .order_by(None)
        .group_by(RiskItem.severity)
    )
    by_severity: dict[str, int] = {row[0]: row[1] for row in severity_q}

    # ---- by_status ---------------------------------------------------------
    status_q = await session.execute(
        base.with_only_columns(RiskItem.status, func.count(RiskItem.id))
        .order_by(None)
        .group_by(RiskItem.status)
    )
    by_status: dict[str, int] = {row[0]: row[1] for row in status_q}

    open_count = by_status.get("open", 0)
    closed_count = by_status.get("closed", 0)

    return RiskAggregate(
        by_severity=by_severity,
        by_status=by_status,
        open_count=open_count,
        closed_count=closed_count,
        disclaimer=_RISK_DISCLAIMER,
    )


async def update_risk(
    session: AsyncSession,
    *,
    risk_id: int,
    data: RiskUpdate,
    editor: Any,
) -> dict[str, Any]:
    """Apply a partial update to a RiskItem.

    Raises:
        LookupError: risk not found or soft-deleted.
    """
    result = await session.execute(
        select(RiskItem).where(
            RiskItem.id == risk_id,
            RiskItem.deleted_at.is_(None),
        )
    )
    risk: RiskItem | None = result.scalar_one_or_none()
    if risk is None:
        raise LookupError(f"RiskItem id={risk_id} not found")

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        # due_date in RiskUpdate is datetime | None; RiskItem stores date | None.
        if field == "due_date" and value is not None:
            value = value.date() if hasattr(value, "date") else value
        setattr(risk, field, value)

    await session.flush()
    await session.refresh(risk)
    return _to_dict(risk)
