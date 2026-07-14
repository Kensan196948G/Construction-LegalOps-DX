"""リスク管理エンドポイント。

- GET `/risks` : リスク一覧 (重大度・状態・契約 ID で絞り込み)
- GET `/risks/aggregate` : 集計 KPI (ヒートマップ・ステータス別件数)
- PATCH `/risks/{id}` : 状態・対応策更新
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, get_current_user, require_role
from app.schemas.common import Page
from app.schemas.risk import (
    RiskAggregate,
    RiskOut,
    RiskUpdate,
)
from app.services import audit_service, risk_service

router = APIRouter(prefix="/risks", tags=["risks"])


@router.get(
    "",
    response_model=Page[RiskOut],
    summary="リスク一覧",
    description="severity / status / contract_id / owner_id / department_id で絞り込み。RLS 適用。",
)
async def list_risks(
    severity: str | None = Query(default=None, description="low/medium/high/critical"),
    status_: str | None = Query(default=None, alias="status"),
    contract_id: int | None = Query(default=None),
    owner_id: int | None = Query(default=None),
    department_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Page[RiskOut]:
    items, total = await risk_service.list_risks(
        session,
        viewer=current_user,
        severity=severity,
        status=status_,
        contract_id=contract_id,
        owner_id=owner_id,
        department_id=department_id,
        page=page,
        size=size,
    )
    return Page[RiskOut](items=items, total=total, page=page, size=size)


@router.get(
    "/aggregate",
    response_model=RiskAggregate,
    summary="リスク集計 KPI",
    description=(
        "重大度ヒートマップ・ステータス別件数・部門別件数・期日超過件数を集計して返却。"
        " ダッシュボードや KPI 画面で利用。"
    ),
)
async def aggregate_risks(
    department_id: int | None = Query(default=None),
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> RiskAggregate:
    return await risk_service.aggregate(
        session,
        viewer=current_user,
        department_id=department_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.patch(
    "/{risk_id}",
    response_model=RiskOut,
    summary="リスク更新",
    description="status (open/mitigated/accepted/closed) や対応策 mitigation を更新する。",
)
async def update_risk(
    risk_id: int,
    payload: RiskUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_role("legal", "manager", "admin")),
) -> RiskOut:
    try:
        risk = await risk_service.update_risk(
            session, risk_id=risk_id, data=payload, editor=current_user
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="risk not found")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="risk.update",
        target_type="risks",
        target_id=risk["id"],
        payload={"after": payload.model_dump(exclude_unset=True)},
        request=request,
    )
    return RiskOut.model_validate(risk)
