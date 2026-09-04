"""Contract service — CRUD implementation with stub fallback for legacy ops."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import CurrentUser
from app.models.clause import Clause
from app.models.contract import Contract
from app.models.enums import ContractStatus
from app.schemas.clause import ClauseOut
from app.schemas.contract import ContractCreate, ContractOut, ContractUpdate, ContractVersionOut
from app.services._stub import make_stub

_stub = make_stub("contract_service")


async def create_contract(
    session: AsyncSession,
    *,
    creator: CurrentUser,
    data: ContractCreate,
    idempotency_key: str | None = None,
) -> Contract:
    contract_no = f"C-{uuid.uuid4().hex[:12].upper()}"
    # Resolved users.id from JIT provisioning (Issue #45). Never derive an id
    # from the token subject — contracts.drafter_id is a real FK on PG.
    drafter_id = creator.db_id
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
        order_date=data.order_date,
        receipt_date=data.receipt_date,
        inspection_date=data.inspection_date,
        payment_date=data.payment_date,
        transaction_kind=data.transaction_kind,
        is_public_work=data.is_public_work,
        handles_personal_data=data.handles_personal_data,
        our_capital_jpy=data.our_capital_jpy,
        counterparty_capital_jpy=data.counterparty_capital_jpy,
        our_employees=data.our_employees,
        counterparty_employees=data.counterparty_employees,
        case_category=data.case_category,
        ethical_wall=data.ethical_wall,
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


async def submit_for_review(
    session: AsyncSession,
    *,
    contract_id: int,
    actor: CurrentUser,
) -> Contract:
    """Move a draft contract into review.

    Workflow instances are started by ``workflow_service.start_workflow`` via
    ``POST /contracts/{id}/workflows``. This endpoint owns the contract
    lifecycle transition and audit boundary for the submit action.
    """

    contract = await get_contract(session, contract_id=contract_id, viewer=actor)
    if contract is None:
        raise LookupError(f"Contract {contract_id} not found")
    if contract.status != ContractStatus.DRAFT.value:
        raise ValueError(
            f"Contract {contract_id} cannot be submitted from status {contract.status}"
        )
    contract.status = ContractStatus.IN_REVIEW.value
    contract.version += 1
    await session.flush()
    await session.refresh(contract)
    return contract


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
        stmt = stmt.where(Contract.title.ilike(f"%{q}%") | Contract.counterparty.ilike(f"%{q}%"))
    if status:
        stmt = stmt.where(Contract.status == status)
    if contract_type:
        stmt = stmt.where(Contract.contract_type == contract_type)
    if department_id is not None:
        stmt = stmt.where(Contract.department_id == department_id)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await session.execute(count_stmt)
    total: int = total_result.scalar_one()

    # 決定論的な整列（従来 sort 引数は未使用で無順序のため、同時刻更新が
    # 多数あるとページングが不安定になった）。許可列のみ受け付け、最後に
    # id DESC のタイブレークを必ず付与する。
    _SORTABLE = {
        "id": Contract.id,
        "created_at": Contract.created_at,
        "updated_at": Contract.updated_at,
        "title": Contract.title,
        "amount": Contract.amount,
        "status": Contract.status,
        "contract_type": Contract.contract_type,
        "counterparty": Contract.counterparty,
    }
    sort_key = (sort or "-updated_at").strip()
    descending = sort_key.startswith("-")
    field_name = sort_key.lstrip("-")
    column = _SORTABLE.get(field_name, Contract.updated_at)
    stmt = stmt.order_by(
        column.desc() if descending else column.asc(),
        Contract.id.desc(),
    )

    offset = (page - 1) * size
    stmt = stmt.offset(offset).limit(size)
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    items = [ContractOut.model_validate(r) for r in rows]
    return items, total


async def list_versions(
    session: AsyncSession,
    *,
    contract_id: int,
    viewer: CurrentUser,
    page: int = 1,
    size: int = 20,
) -> tuple[list[ContractVersionOut], int]:
    """Return the current contract version as a stable API snapshot.

    The current schema does not include a separate ``contract_versions`` table.
    Until a non-destructive history table migration is approved, the endpoint
    exposes the authoritative current row so callers do not hit the legacy
    501 fallback.
    """

    contract = await get_contract(session, contract_id=contract_id, viewer=viewer)
    if contract is None:
        raise LookupError(f"Contract {contract_id} not found")
    if page != 1:
        return [], 1
    item = ContractVersionOut(
        id=contract.id,
        contract_id=contract.id,
        version=contract.version,
        title=contract.title,
        status=ContractStatus(contract.status),
        sharepoint_item_id=contract.sharepoint_item_id,
        created_at=contract.updated_at or contract.created_at,
        created_by=contract.updated_by or contract.created_by,
    )
    return [item][:size], 1


async def list_clauses(
    session: AsyncSession,
    *,
    contract_id: int,
    viewer: CurrentUser,
) -> list[ClauseOut]:
    """Return active clauses for a contract in ``seq`` order."""

    contract = await get_contract(session, contract_id=contract_id, viewer=viewer)
    if contract is None:
        raise LookupError(f"Contract {contract_id} not found")
    stmt = (
        select(Clause)
        .where(Clause.contract_id == contract_id, Clause.deleted_at.is_(None))
        .order_by(Clause.seq.asc())
    )
    result = await session.execute(stmt)
    clauses = list(result.scalars().all())
    return [
        ClauseOut(
            id=clause.id,
            contract_id=clause.contract_id,
            seq=clause.seq,
            title=clause.title,
            text=clause.body,
            category=(clause.ai_findings or {}).get("category"),
            risk_level=clause.risk_level,
        )
        for clause in clauses
    ]


def __getattr__(item: str) -> Any:
    return getattr(_stub, item)
