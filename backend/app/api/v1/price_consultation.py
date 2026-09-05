"""労務費価格協議・乖離確認エンドポイント（#21/#23/#24）.

- ``GET  /price-consultations`` … 価格協議ログ一覧（状態/方向/深刻度/契約絞り込み）
- ``POST /price-consultations`` … 協議申出（#24・乖離スナップショット付き）
- ``GET  /price-consultations/{id}`` … 詳細
- ``POST /price-consultations/{id}/respond`` … 回答（open→responded）
- ``POST /price-consultations/{id}/cancel`` … 取下げ（open→cancelled）
- ``GET  /price-consultations/monitor/quote-changes`` … #23 見積変更要求監視（未回答のみ）
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, require_role
from app.schemas.common import Page
from app.schemas.price_consultation import (
    PriceConsultationCancel,
    PriceConsultationCreate,
    PriceConsultationOut,
    PriceConsultationRespond,
)
from app.services import audit_service, price_consultation_service

router = APIRouter(prefix="/price-consultations", tags=["price-consultations"])

_READ_ROLES = ("viewer", "drafter", "reviewer", "approver", "admin", "auditor")
_WRITE_ROLES = ("drafter", "reviewer", "approver", "admin")


async def _audit(
    session: AsyncSession,
    request: Request,
    current_user: CurrentUser,
    *,
    action: str,
    target_id: int,
    payload: dict[str, object] | None = None,
) -> None:
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action=action,
        target_type="price_consultation_logs",
        target_id=target_id,
        request=request,
        payload=payload,
    )


@router.get(
    "",
    response_model=Page[PriceConsultationOut],
    summary="価格協議ログ一覧（#24/#23）",
)
async def list_consultations(
    status_: str | None = Query(default=None, alias="status"),
    direction: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    contract_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> Page[PriceConsultationOut]:
    items, total = await price_consultation_service.list_logs(
        session,
        status=status_,
        direction=direction,
        severity=severity,
        contract_id=contract_id,
        page=page,
        size=size,
    )
    return Page[PriceConsultationOut](
        items=[PriceConsultationOut.model_validate(i) for i in items],
        total=total,
        page=page,
        size=size,
    )


@router.post(
    "",
    response_model=PriceConsultationOut,
    status_code=status.HTTP_201_CREATED,
    summary="価格協議申出を記録（#24・乖離スナップショット付き）",
)
async def create_consultation(
    body: PriceConsultationCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> PriceConsultationOut:
    row = await price_consultation_service.create_log(
        session,
        actor_id=current_user.db_id,
        direction=body.direction.value if hasattr(body.direction, "value") else str(body.direction),
        work_type=body.work_type,
        contract_id=body.contract_id,
        prefecture=body.prefecture,
        quote_day_jpy=body.quote_day_jpy,
        summary=body.summary,
        request_detail=body.request_detail,
        requested_at=body.requested_at,
    )
    await _audit(
        session,
        request,
        current_user,
        action="price_consultation.create",
        target_id=row.id,
        payload={"log_no": row.log_no, "severity": row.severity},
    )
    return PriceConsultationOut.model_validate(row)


@router.get(
    "/{log_id}",
    response_model=PriceConsultationOut,
    summary="価格協議ログ詳細",
)
async def get_consultation(
    log_id: int,
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> PriceConsultationOut:
    row = await price_consultation_service.get_log(session, log_id=log_id)
    return PriceConsultationOut.model_validate(row)


@router.post(
    "/{log_id}/respond",
    response_model=PriceConsultationOut,
    summary="価格協議へ回答（#24・open → responded）",
)
async def respond_consultation(
    log_id: int,
    body: PriceConsultationRespond,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> PriceConsultationOut:
    row = await price_consultation_service.respond_log(
        session,
        log_id=log_id,
        actor_id=current_user.db_id,
        response_summary=body.response_summary,
    )
    await _audit(
        session,
        request,
        current_user,
        action="price_consultation.respond",
        target_id=row.id,
        payload={"log_no": row.log_no, "status": row.status},
    )
    return PriceConsultationOut.model_validate(row)


@router.post(
    "/{log_id}/cancel",
    response_model=PriceConsultationOut,
    summary="価格協議の取下げ（#24・open → cancelled）",
)
async def cancel_consultation(
    log_id: int,
    body: PriceConsultationCancel,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> PriceConsultationOut:
    row = await price_consultation_service.cancel_log(
        session,
        log_id=log_id,
        actor_id=current_user.db_id,
        reason=body.reason,
    )
    await _audit(
        session,
        request,
        current_user,
        action="price_consultation.cancel",
        target_id=row.id,
        payload={"log_no": row.log_no, "status": row.status},
    )
    return PriceConsultationOut.model_validate(row)


@router.get(
    "/monitor/quote-changes",
    response_model=Page[PriceConsultationOut],
    summary="#23 見積変更要求監視（未回答の協議一覧）",
)
async def monitor_quote_changes(
    severity: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> Page[PriceConsultationOut]:
    items, total = await price_consultation_service.list_open_monitor(
        session, severity=severity, page=page, size=size
    )
    return Page[PriceConsultationOut](
        items=[PriceConsultationOut.model_validate(i) for i in items],
        total=total,
        page=page,
        size=size,
    )


