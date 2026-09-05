"""労務費コミットメント・見積様式生成エンドポイント（#27/#28）."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, require_role
from app.schemas.common import Page
from app.schemas.labor_commitment import (
    LaborCommitmentCreate,
    LaborCommitmentOut,
    LaborCommitmentVerify,
)
from app.services import audit_service, estimate_form_service, labor_commitment_service

router = APIRouter(prefix="/labor-wage", tags=["labor-wage"])

_READ_ROLES = ("viewer", "drafter", "reviewer", "approver", "admin", "auditor")
_WRITE_ROLES = ("drafter", "reviewer", "approver", "admin")

_COMMITMENT_TARGET = "labor_commitments"


# ------------------------------------------------------- #27 見積様式生成 ---
class EstimateFormItem(BaseModel):
    work_type: str = Field(..., min_length=1, max_length=64)
    spec: str | None = Field(default=None, max_length=256)
    quantity: float = Field(..., gt=0)
    unit: str | None = Field(default=None, max_length=16)
    unit_price_jpy: int = Field(..., ge=0)
    labor_cost_jpy: int = Field(default=0, ge=0)
    material_cost_jpy: int = Field(default=0, ge=0)
    safety_cost_jpy: int = Field(default=0, ge=0)
    welfare_cost_jpy: int = Field(default=0, ge=0)


class EstimateFormRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)
    contractor_name: str = Field(..., min_length=1, max_length=256)
    tax_rate: float = Field(default=0.10, ge=0, le=1)
    items: list[EstimateFormItem] = Field(..., min_length=1)
    notes: str | None = Field(default=None, max_length=4000)


@router.post(
    "/estimate-form",
    summary="見積書様式生成（#27・総括表＋明細表・決定論的テンプレート処理）",
)
async def estimate_form(
    body: EstimateFormRequest,
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> dict[str, Any]:
    return estimate_form_service.generate_estimate_form(
        title=body.title,
        contractor_name=body.contractor_name,
        items=[item.model_dump() for item in body.items],
        tax_rate=body.tax_rate,
        notes=body.notes,
    )


# ------------------------------------------------------- #28 コミットメント ---
@router.get(
    "/commitments",
    response_model=Page[LaborCommitmentOut],
    summary="労務費コミットメント一覧（#28）",
)
async def list_commitments(
    contract_id: int | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status"),
    commitment_type: str | None = Query(default=None, alias="type"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> Page[LaborCommitmentOut]:
    items, total = await labor_commitment_service.list_commitments(
        session,
        contract_id=contract_id,
        status=status_,
        commitment_type=commitment_type,
        page=page,
        size=size,
    )
    return Page[LaborCommitmentOut](
        items=[LaborCommitmentOut.model_validate(i) for i in items],
        total=total,
        page=page,
        size=size,
    )


@router.post(
    "/commitments",
    response_model=LaborCommitmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="労務費コミットメント（表明）を登録（#28）",
)
async def create_commitment(
    body: LaborCommitmentCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> LaborCommitmentOut:
    row = await labor_commitment_service.create_commitment(
        session,
        actor_id=current_user.db_id,
        contract_id=body.contract_id,
        commitment_type=body.commitment_type,
        title=body.title,
        statement=body.statement,
        confirmed_at=body.confirmed_at,
    )
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="labor_commitment.create",
        target_type=_COMMITMENT_TARGET,
        target_id=row.id,
        request=request,
        payload={"contract_id": row.contract_id, "type": row.commitment_type},
    )
    return LaborCommitmentOut.model_validate(row)


@router.post(
    "/commitments/{commitment_id}/verify",
    response_model=LaborCommitmentOut,
    summary="表明の履行確認/違反確認（#28・active → fulfilled/violated）",
)
async def verify_commitment(
    commitment_id: int,
    body: LaborCommitmentVerify,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> LaborCommitmentOut:
    row = await labor_commitment_service.verify_commitment(
        session,
        commitment_id=commitment_id,
        actor_id=current_user.db_id,
        outcome=body.outcome,
        verify_note=body.verify_note,
    )
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="labor_commitment.verify",
        target_type=_COMMITMENT_TARGET,
        target_id=row.id,
        request=request,
        payload={"outcome": row.status},
    )
    return LaborCommitmentOut.model_validate(row)
