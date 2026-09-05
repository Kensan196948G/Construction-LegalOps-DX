"""公共工事特化エンドポイント（#41-#43・#54-#57・#60）.

- ``GET/POST /public-works/contracting-agencies`` … #41/#42 発注機関マスタ
- ``GET/POST /public-works/notifications`` … #54 発注者通知期限
  （``POST /{id}/notify`` = 送付済みへ・``POST /{id}/cancel`` = 取下げ）
- ``GET/POST /public-works/consultations`` … #55/#56/#57 発注者との協議
  （``POST /{id}/respond`` = 回答・結果記録 / ``POST /{id}/cancel`` = 取下げ）
- ``GET /public-works/standard-clause-check`` … #43 標準請負約款差分チェック
- ``GET  /public-works/dashboard`` … #60 公共工事ダッシュボード
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, require_role
from app.schemas.common import Page
from app.schemas.public_works import (
    ContractingAgencyCreate,
    ContractingAgencyOut,
    OwnerNotificationCancel,
    OwnerNotificationCreate,
    OwnerNotificationOut,
    PublicWorksConsultationCancel,
    PublicWorksConsultationCreate,
    PublicWorksConsultationOut,
    PublicWorksConsultationRespond,
    PublicWorksDashboardOut,
    StandardClauseCheckOut,
)
from app.services import audit_service, public_works_service

router = APIRouter(prefix="/public-works", tags=["public-works"])

_READ_ROLES = ("viewer", "drafter", "reviewer", "approver", "admin", "auditor")
_WRITE_ROLES = ("drafter", "reviewer", "approver", "admin")


async def _audit(
    session: AsyncSession,
    request: Request,
    current_user: CurrentUser,
    *,
    action: str,
    target_type: str,
    target_id: int,
    payload: dict[str, object] | None = None,
) -> None:
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        request=request,
        payload=payload,
    )


# ------------------------------------------------------- #41/#42 発注機関 ---
@router.get(
    "/contracting-agencies",
    response_model=Page[ContractingAgencyOut],
    summary="発注機関マスタ一覧（#41/#42）",
)
async def list_agencies(
    agency_type: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> Page[ContractingAgencyOut]:
    items, total = await public_works_service.list_agencies(
        session, agency_type=agency_type, is_active=is_active, page=page, size=size
    )
    return Page[ContractingAgencyOut](
        items=[ContractingAgencyOut.model_validate(i) for i in items],
        total=total,
        page=page,
        size=size,
    )


@router.post(
    "/contracting-agencies",
    response_model=ContractingAgencyOut,
    status_code=status.HTTP_201_CREATED,
    summary="発注機関を登録（#41/#42・契約条件付き）",
)
async def create_agency(
    body: ContractingAgencyCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> ContractingAgencyOut:
    row = await public_works_service.create_agency(
        session,
        actor_id=current_user.db_id,
        code=body.code,
        name=body.name,
        agency_type=body.agency_type.value
        if hasattr(body.agency_type, "value")
        else str(body.agency_type),
        prefecture=body.prefecture,
        contact_email=body.contact_email,
        phone=body.phone,
        payment_deadline_days=body.payment_deadline_days,
        advance_payment_ratio=body.advance_payment_ratio,
        warranty_period_months=body.warranty_period_months,
        requires_slide_clause=body.requires_slide_clause,
        notes=body.notes,
    )
    await _audit(
        session,
        request,
        current_user,
        action="contracting_agency.create",
        target_type="contracting_agencies",
        target_id=row.id,
        payload={"code": row.code, "name": row.name},
    )
    return ContractingAgencyOut.model_validate(row)


# ------------------------------------------------------- #54 通知期限 ---
@router.get(
    "/notifications",
    response_model=Page[OwnerNotificationOut],
    summary="発注者通知一覧（#54）",
)
async def list_notifications(
    status_: str | None = Query(default=None, alias="status"),
    notification_type: str | None = Query(default=None, alias="type"),
    contract_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> Page[OwnerNotificationOut]:
    items, total = await public_works_service.list_notifications(
        session,
        status=status_,
        notification_type=notification_type,
        contract_id=contract_id,
        page=page,
        size=size,
    )
    return Page[OwnerNotificationOut](
        items=[OwnerNotificationOut.model_validate(i) for i in items],
        total=total,
        page=page,
        size=size,
    )


@router.post(
    "/notifications",
    response_model=OwnerNotificationOut,
    status_code=status.HTTP_201_CREATED,
    summary="発注者通知を登録（#54・open）",
)
async def create_notification(
    body: OwnerNotificationCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> OwnerNotificationOut:
    row = await public_works_service.create_notification(
        session,
        actor_id=current_user.db_id,
        notification_type=body.notification_type,
        title=body.title,
        contract_id=body.contract_id,
        agency_id=body.agency_id,
        detail=body.detail,
        due_date=body.due_date,
    )
    await _audit(
        session,
        request,
        current_user,
        action="owner_notification.create",
        target_type="owner_notifications",
        target_id=row.id,
        payload={"notification_no": row.notification_no, "type": row.notification_type},
    )
    return OwnerNotificationOut.model_validate(row)


@router.post(
    "/notifications/{notification_id}/notify",
    response_model=OwnerNotificationOut,
    summary="発注者通知を送付済みにする（#54・open → notified）",
)
async def notify_notification(
    notification_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> OwnerNotificationOut:
    row = await public_works_service.notify_notification(
        session, notification_id=notification_id, actor_id=current_user.db_id
    )
    await _audit(
        session,
        request,
        current_user,
        action="owner_notification.notify",
        target_type="owner_notifications",
        target_id=row.id,
        payload={"notification_no": row.notification_no},
    )
    return OwnerNotificationOut.model_validate(row)


@router.post(
    "/notifications/{notification_id}/cancel",
    response_model=OwnerNotificationOut,
    summary="発注者通知を取り下げ（#54・open → cancelled）",
)
async def cancel_notification(
    notification_id: int,
    body: OwnerNotificationCancel,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> OwnerNotificationOut:
    row = await public_works_service.cancel_notification(
        session,
        notification_id=notification_id,
        actor_id=current_user.db_id,
        reason=body.reason,
    )
    await _audit(
        session,
        request,
        current_user,
        action="owner_notification.cancel",
        target_type="owner_notifications",
        target_id=row.id,
        payload={"notification_no": row.notification_no},
    )
    return OwnerNotificationOut.model_validate(row)


# ------------------------------------------------- #55/#56/#57 協議プロセス ---
@router.get(
    "/consultations",
    response_model=Page[PublicWorksConsultationOut],
    summary="発注者との協議一覧（#55/#56/#57）",
)
async def list_consultations(
    status_: str | None = Query(default=None, alias="status"),
    consultation_type: str | None = Query(default=None, alias="type"),
    contract_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> Page[PublicWorksConsultationOut]:
    items, total = await public_works_service.list_consultations(
        session,
        status=status_,
        consultation_type=consultation_type,
        contract_id=contract_id,
        page=page,
        size=size,
    )
    return Page[PublicWorksConsultationOut](
        items=[PublicWorksConsultationOut.model_validate(i) for i in items],
        total=total,
        page=page,
        size=size,
    )


@router.post(
    "/consultations",
    response_model=PublicWorksConsultationOut,
    status_code=status.HTTP_201_CREATED,
    summary="発注者との協議を申出（#55 工期延伸 / #56 スライド請求 / #57 設計変更）",
)
async def create_consultation(
    body: PublicWorksConsultationCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> PublicWorksConsultationOut:
    row = await public_works_service.create_consultation(
        session,
        actor_id=current_user.db_id,
        consultation_type=body.consultation_type,
        title=body.title,
        contract_id=body.contract_id,
        agency_id=body.agency_id,
        detail=body.detail,
        requested_at=body.requested_at,
        due_date=body.due_date,
        claimed_days=body.claimed_days,
        claimed_amount_jpy=body.claimed_amount_jpy,
    )
    await _audit(
        session,
        request,
        current_user,
        action="public_works_consultation.create",
        target_type="public_works_consultations",
        target_id=row.id,
        payload={"consultation_no": row.consultation_no, "type": row.consultation_type},
    )
    return PublicWorksConsultationOut.model_validate(row)


@router.post(
    "/consultations/{consultation_id}/respond",
    response_model=PublicWorksConsultationOut,
    summary="協議の回答・結果を記録（#55-#57・open → responded）",
)
async def respond_consultation(
    consultation_id: int,
    body: PublicWorksConsultationRespond,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> PublicWorksConsultationOut:
    row = await public_works_service.respond_consultation(
        session,
        consultation_id=consultation_id,
        actor_id=current_user.db_id,
        response_note=body.response_note,
        resolved_days=body.resolved_days,
        resolved_amount_jpy=body.resolved_amount_jpy,
    )
    await _audit(
        session,
        request,
        current_user,
        action="public_works_consultation.respond",
        target_type="public_works_consultations",
        target_id=row.id,
        payload={"consultation_no": row.consultation_no, "status": row.status},
    )
    return PublicWorksConsultationOut.model_validate(row)


@router.post(
    "/consultations/{consultation_id}/cancel",
    response_model=PublicWorksConsultationOut,
    summary="協議を取り下げ（#55-#57・open → cancelled）",
)
async def cancel_consultation(
    consultation_id: int,
    body: PublicWorksConsultationCancel,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> PublicWorksConsultationOut:
    row = await public_works_service.cancel_consultation(
        session,
        consultation_id=consultation_id,
        actor_id=current_user.db_id,
        reason=body.reason,
    )
    await _audit(
        session,
        request,
        current_user,
        action="public_works_consultation.cancel",
        target_type="public_works_consultations",
        target_id=row.id,
        payload={"consultation_no": row.consultation_no},
    )
    return PublicWorksConsultationOut.model_validate(row)


# ------------------------------------------------------- #43 約款差分チェック ---
@router.get(
    "/standard-clause-check",
    response_model=StandardClauseCheckOut,
    summary="標準請負約款差分チェック（#43・重要条項カテゴリ突合・決定論的）",
)
async def standard_clause_check(
    contract_id: int = Query(...),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> StandardClauseCheckOut:
    result = await public_works_service.check_standard_clauses(
        session, contract_id=contract_id
    )
    return StandardClauseCheckOut(**result)


# ------------------------------------------------------- #60 ダッシュボード ---
@router.get(
    "/dashboard",
    response_model=PublicWorksDashboardOut,
    summary="公共工事ダッシュボード（#60）",
)
async def dashboard(
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> PublicWorksDashboardOut:
    result = await public_works_service.dashboard(session)
    return PublicWorksDashboardOut(**result)
