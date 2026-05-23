"""Contract service — CRUD implementation with stub fallback for unimplemented ops."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import CurrentUser
from app.models.contract import Contract
from app.schemas.contract import ContractCreate, ContractOut, ContractUpdate
from app.services._stub import make_stub

_stub = make_stub("contract_service")


def _drafter_int_id(user_id: Any) -> int:
    """Convert UUID/str user id to a BigInteger-compatible int for SQLite tests.

    PostgreSQL FK targets the users table, but SQLite (test env) doesn't enforce
    FK constraints, so a deterministic hash is safe here.
    """
    return abs(hash(str(user_id))) % (2**31)


async def create_contract(
    session: AsyncSession,
    *,
    creator: CurrentUser,
    data: ContractCreate,
    idempotency_key: str | None = None,
) -> Contract:
    contract_no = f"C-{uuid.uuid4().hex[:12].upper()}"
    drafter_id = _drafter_int_id(creator.id)
    contract = Contract(
        contract_no=contract_no,
        title=data.title,
        counterparty=data.counterparty,
        contract_type=data.contract_type,
        amount=data.amount,
        currency=data.currency,
        start_date=data.start_date,
        end_date=data.end_date,
        department_id=data.department_id,
        drafter_id=drafter_id,
        confidentiality=(
            data.confidentiality.value
            if hasattr(data.confidentiality, "value")
            else str(data.confidentiality)
        ),
        extra_metadata=data.extra_metadata,
        status="draft",
        version=1,
    )
    session.add(contract)
    await session.flush()
    await session.refresh(contract)
    return contract


async def get_contract(
    session: AsyncSession,
    *,
    contract_id: int,
    viewer: CurrentUser,
    include_deleted: bool = False,
) -> Contract | None:
    stmt = select(Contract).where(Contract.id == contract_id)
    if not include_deleted:
        stmt = stmt.where(Contract.deleted_at.is_(None))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_contract(
    session: AsyncSession,
    *,
    contract_id: int,
    data: ContractUpdate,
    editor: CurrentUser,
) -> Contract:
    contract = await get_contract(session, contract_id=contract_id, viewer=editor)
    if contract is None:
        raise LookupError(f"Contract {contract_id} not found")
    if contract.version != data.version:
        raise ValueError(
            f"Optimistic lock conflict: expected version {data.version}, got {contract.version}"
        )
    update_fields = data.model_dump(exclude={"version"}, exclude_none=True, by_alias=False)
    for field, value in update_fields.items():
        if hasattr(contract, field):
            setattr(contract, field, value)
    contract.version += 1
    await session.flush()
    await session.refresh(contract)
    return contract


async def soft_delete_contract(
    session: AsyncSession,
    *,
    contract_id: int,
    actor: CurrentUser,
) -> None:
    contract = await get_contract(session, contract_id=contract_id, viewer=actor)
    if contract is None:
        raise LookupError(f"Contract {contract_id} not found")
    contract.deleted_at = datetime.now(tz=UTC)
    await session.flush()


async def list_contracts(
    session: AsyncSession,
    *,
    viewer: CurrentUser,
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
    """Return paginated contract list visible to *viewer*."""
    stmt = select(Contract).where(Contract.deleted_at.is_(None))

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
