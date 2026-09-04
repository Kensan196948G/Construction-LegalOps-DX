"""労務費基準マスタ・乖離率判定エンドポイント（Issue #111・#16〜#20）."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, require_role
from app.schemas.common import Page
from app.schemas.labor_wage import (
    LaborWageDiscrepancyOut,
    LaborWageStandardCreate,
    LaborWageStandardOut,
)
from app.services import audit_service, labor_wage_service

router = APIRouter(prefix="/labor-wage", tags=["labor-wage"])

_READ_ROLES = ("viewer", "drafter", "reviewer", "approver", "admin", "auditor")
_WRITE_ROLES = ("drafter", "reviewer", "approver", "admin")


@router.get(
    "/standards",
    response_model=Page[LaborWageStandardOut],
    summary="労務費基準一覧（#17 工種・#18 都道府県・as-of 絞り込み）",
)
async def list_standards(
    work_type: str | None = Query(default=None),
    prefecture: str | None = Query(default=None),
    as_of: date | None = Query(default=None, description="基準日（適用期間内のみ）"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> Page[LaborWageStandardOut]:
    items, total = await labor_wage_service.list_standards(
        session, work_type=work_type, prefecture=prefecture, as_of=as_of, page=page, size=size
    )
    return Page[LaborWageStandardOut](
        items=[LaborWageStandardOut.model_validate(s) for s in items],
        total=total,
        page=page,
        size=size,
    )


@router.post(
    "/standards",
    response_model=LaborWageStandardOut,
    status_code=status.HTTP_201_CREATED,
    summary="労務費基準を登録（#16 データ更新・履歴蓄積）",
)
async def create_standard(
    body: LaborWageStandardCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> LaborWageStandardOut:
    standard = await labor_wage_service.upsert_standard(
        session,
        actor_id=current_user.db_id,
        work_type=body.work_type.value if hasattr(body.work_type, "value") else str(body.work_type),
        amount_jpy=body.amount_jpy,
        prefecture=body.prefecture,
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        amount_unit=body.amount_unit,
        source_ref=body.source_ref,
    )
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="labor_wage.create",
        target_type="labor_wage_standards",
        target_id=standard.id,
        request=request,
        payload={
            "work_type": standard.work_type,
            "prefecture": standard.prefecture,
            "amount_jpy": standard.amount_jpy,
            "effective_from": standard.effective_from.isoformat(),
        },
    )
    return LaborWageStandardOut.model_validate(standard)


@router.get(
    "/standards/latest",
    response_model=LaborWageStandardOut,
    summary="as-of 日時点の最新基準値（#16/#17/#18）",
)
async def resolve_latest(
    work_type: str = Query(...),
    prefecture: str | None = Query(default=None),
    as_of: date | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> LaborWageStandardOut:
    standard = await labor_wage_service.resolve_latest(
        session, work_type=work_type, prefecture=prefecture, as_of=as_of
    )
    return LaborWageStandardOut.model_validate(standard)


@router.get(
    "/discrepancy",
    response_model=LaborWageDiscrepancyOut,
    summary="労務費乖離率判定（#20・基準未満を below で検出）",
)
async def discrepancy(
    work_type: str = Query(...),
    quote_day_jpy: int = Query(..., ge=0, description="見積単価（円/日）"),
    prefecture: str | None = Query(default=None),
    as_of: date | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> LaborWageDiscrepancyOut:
    result = await labor_wage_service.discrepancy(
        session,
        work_type=work_type,
        quote_day_jpy=quote_day_jpy,
        prefecture=prefecture,
        as_of=as_of,
    )
    return LaborWageDiscrepancyOut(**result)
