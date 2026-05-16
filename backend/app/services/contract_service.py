"""Contract service — minimal list implementation with stub fallback.

`list_contracts` is implemented to return paginated results from the DB.
All other operations fall back to the 501 stub until fully implemented.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract
from app.models.user import User
from app.schemas.contract import ContractOut
from app.services._stub import make_stub

_stub = make_stub("contract_service")


async def list_contracts(
    session: AsyncSession,
    *,
    viewer: User,
    q: str | None = None,
    status: str | None = None,
    contract_type: str | None = None,
    department_id: int | None = None,
    risk_level: str | None = None,
    confidentiality: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    size: int = 20,
    sort: str | None = "-updated_at",
) -> tuple[list[ContractOut], int]:
    """Return paginated contract list visible to *viewer*.

    Currently returns all contracts without RLS filtering.
    Full RLS implementation is tracked in Sprint 1.
    """
    stmt = select(Contract)

    if q:
        stmt = stmt.where(
            Contract.title.ilike(f"%{q}%")
            | Contract.counterparty.ilike(f"%{q}%")
        )
    if status:
        stmt = stmt.where(Contract.status == status)
    if contract_type:
        stmt = stmt.where(Contract.contract_type == contract_type)
    if department_id is not None:
        stmt = stmt.where(Contract.department_id == department_id)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await session.execute(count_stmt)
    total: int = total_result.scalar_one()

    offset = (page - 1) * size
    stmt = stmt.offset(offset).limit(size)
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    items = [ContractOut.model_validate(r) for r in rows]
    return items, total


def __getattr__(item: str) -> Any:
    return getattr(_stub, item)
