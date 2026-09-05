"""協力会社拡張エンドポイント（#136〜#152）.

- ``GET  /partners/alerts`` … #138/#146/#151 期限アラート一覧
- ``GET  /partners/{partner_id}/expiry-flags`` … 期限状態フラグ
- ``GET  /partners/{partner_id}/risk-score`` … #150 Risk Score（計算のみ・保存しない）
- ``POST /partners/{partner_id}/risk-score/refresh`` … #150 算出して保存
- ``GET  /partners/{partner_id}/reviews`` / ``POST`` … #147-#149/#151 再審査
- ``POST /partner-reviews/{review_id}/complete`` … #151 審査完了（次回期限反映）
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.deps import CurrentUser, require_role
from app.models.partner import Partner
from app.schemas.common import Page
from app.schemas.partner_ext import (
    PartnerExpiryFlagsOut,
    PartnerReviewComplete,
    PartnerReviewCreate,
    PartnerReviewOut,
    PartnerRiskScoreOut,
)
from app.services import audit_service, partner_ext_service

router = APIRouter(prefix="/partners", tags=["partner-ext"])

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
        target_type="partner_reviews",
        target_id=target_id,
        request=request,
        payload=payload,
    )


@router.get(
    "/alerts",
    response_model=list[PartnerExpiryFlagsOut],
    summary="協力会社期限アラート（#138/#146/#151・expired/expiring）",
)
async def list_alerts(
    within_days: int = Query(default=60, ge=1, le=365),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> list[PartnerExpiryFlagsOut]:
    partners, _total = await partner_ext_service.list_expiry_alerts(
        session, within_days=within_days, page=page, size=size
    )
    return [
        PartnerExpiryFlagsOut(**partner_ext_service.partner_expiry_flags(p))
        for p in partners
    ]


@router.get(
    "/{partner_id}/expiry-flags",
    response_model=PartnerExpiryFlagsOut,
    summary="協力会社の期限状態フラグ（#138/#146/#151）",
)
async def expiry_flags(
    partner_id: int,
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> PartnerExpiryFlagsOut:
    partner_row = await session.get(Partner, partner_id)
    if partner_row is None:
        raise NotFoundError(f"協力会社が見つかりません（id={partner_id}）")
    return PartnerExpiryFlagsOut(**partner_ext_service.partner_expiry_flags(partner_row))


@router.get(
    "/{partner_id}/risk-score",
    response_model=PartnerRiskScoreOut,
    summary="Partner Risk Score（#150・計算のみ・保存しない）",
)
async def risk_score(
    partner_id: int,
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> PartnerRiskScoreOut:
    partner_row = await session.get(Partner, partner_id)
    if partner_row is None:
        raise NotFoundError(f"協力会社が見つかりません（id={partner_id}）")
    result = partner_ext_service.compute_risk_score(partner_row)
    return PartnerRiskScoreOut(
        partner_id=partner_row.id,
        partner_name=partner_row.name,
        **result,
    )


@router.post(
    "/{partner_id}/risk-score/refresh",
    response_model=PartnerRiskScoreOut,
    summary="Partner Risk Score を算出して保存（#150）",
)
async def refresh_risk_score(
    partner_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> PartnerRiskScoreOut:
    partner = await partner_ext_service.refresh_risk_score(session, partner_id=partner_id)
    await _audit(
        session,
        request,
        current_user,
        action="partner.risk_score_refresh",
        target_id=partner.id,
        payload={"risk_score": partner.risk_score, "risk_level": partner.risk_level},
    )
    result = partner_ext_service.compute_risk_score(partner)
    return PartnerRiskScoreOut(
        partner_id=partner.id,
        partner_name=partner.name,
        **result,
    )


@router.get(
    "/{partner_id}/reviews",
    response_model=Page[PartnerReviewOut],
    summary="協力会社の再審査・incident/violation 一覧（#147-#149/#151）",
)
async def list_reviews(
    partner_id: int,
    status_: str | None = Query(default=None, alias="status"),
    review_type: str | None = Query(default=None, alias="type"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> Page[PartnerReviewOut]:
    items, total = await partner_ext_service.list_reviews(
        session,
        partner_id=partner_id,
        status=status_,
        review_type=review_type,
        page=page,
        size=size,
    )
    return Page[PartnerReviewOut](
        items=[PartnerReviewOut.model_validate(i) for i in items],
        total=total,
        page=page,
        size=size,
    )


@router.post(
    "/{partner_id}/reviews",
    response_model=PartnerReviewOut,
    status_code=status.HTTP_201_CREATED,
    summary="再審査・incident/violation を起票（#147-#149/#151・PRV-YYYY-NNNNNN）",
)
async def create_review(
    partner_id: int,
    body: PartnerReviewCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> PartnerReviewOut:
    row = await partner_ext_service.create_review(
        session,
        actor_id=current_user.db_id,
        partner_id=partner_id,
        review_type=body.review_type,
        title=body.title,
        safety_score=body.safety_score,
        findings=body.findings,
        violation_count=body.violation_count,
        incident_count=body.incident_count,
        notes=body.notes,
    )
    await _audit(
        session,
        request,
        current_user,
        action="partner_review.create",
        target_id=row.id,
        payload={"review_no": row.review_no, "type": row.review_type},
    )
    return PartnerReviewOut.model_validate(row)


@router.post(
    "/partner-reviews/{review_id}/complete",
    response_model=PartnerReviewOut,
    summary="再審査を完了（#151・open → completed・次回期限を Partner へ反映）",
)
async def complete_review(
    review_id: int,
    body: PartnerReviewComplete,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> PartnerReviewOut:
    row = await partner_ext_service.complete_review(
        session,
        review_id=review_id,
        actor_id=current_user.db_id,
        safety_score=body.safety_score,
        findings=body.findings,
        violation_count=body.violation_count,
        incident_count=body.incident_count,
        next_review_due=body.next_review_due,
    )
    await _audit(
        session,
        request,
        current_user,
        action="partner_review.complete",
        target_id=row.id,
        payload={"review_no": row.review_no, "status": row.status},
    )
    return PartnerReviewOut.model_validate(row)
