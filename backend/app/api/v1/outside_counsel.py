"""顧問弁護士・外部法律事務所管理エンドポイント（Issue #102・#85〜#96）.

- 台帳: 法律事務所（#86）・担当弁護士（#87）
- 依頼（#85/#88）・回答期限（#90）・利益相反（#91）・Confidential（#92）・費用（#93）
- 回答管理（#89）: answer → confirm（cancel 可）・全変更を監査ログへ
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, require_role
from app.schemas.common import Page
from app.schemas.outside_counsel import (
    CounselLawyerCreate,
    CounselLawyerOut,
    EngagementAnswerIn,
    EngagementCancelIn,
    EngagementCreate,
    EngagementOut,
    EngagementUpdate,
    LawFirmCreate,
    LawFirmOut,
)
from app.services import audit_service, outside_counsel_service

router = APIRouter(prefix="/outside-counsel", tags=["outside-counsel"])

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
) -> None:
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        request=request,
        payload=None,
    )


# ---------------------------------------------------------------- 台帳 ---
@router.get("/firms", response_model=Page[LawFirmOut], summary="法律事務所台帳（#86）")
async def list_firms(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> Page[LawFirmOut]:
    items, total = await outside_counsel_service.list_firms(session, page=page, size=size)
    return Page[LawFirmOut](
        items=[LawFirmOut.model_validate(f) for f in items], total=total, page=page, size=size
    )


@router.post(
    "/firms", response_model=LawFirmOut, status_code=status.HTTP_201_CREATED, summary="事務所登録"
)
async def create_firm(
    body: LawFirmCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> LawFirmOut:
    firm = await outside_counsel_service.create_firm(
        session,
        actor_id=current_user.db_id,
        firm_name=body.firm_name,
        contact_email=body.contact_email,
        phone=body.phone,
        address=body.address,
        notes=body.notes,
    )
    await _audit(
        session,
        request,
        current_user,
        action="law_firm.create",
        target_type="law_firms",
        target_id=firm.id,
    )
    return LawFirmOut.model_validate(firm)


@router.get(
    "/firms/{firm_id}/lawyers",
    response_model=Page[CounselLawyerOut],
    summary="事務所の弁護士一覧（#87）",
)
async def list_firm_lawyers(
    firm_id: int,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> Page[CounselLawyerOut]:
    await outside_counsel_service.get_firm(session, firm_id=firm_id)
    items, total = await outside_counsel_service.list_lawyers(
        session, firm_id=firm_id, page=page, size=size
    )
    return Page[CounselLawyerOut](
        items=[CounselLawyerOut.model_validate(lawyer) for lawyer in items],
        total=total,
        page=page,
        size=size,
    )


@router.post(
    "/firms/{firm_id}/lawyers",
    response_model=CounselLawyerOut,
    status_code=status.HTTP_201_CREATED,
    summary="弁護士登録",
)
async def create_lawyer(
    firm_id: int,
    body: CounselLawyerCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> CounselLawyerOut:
    lawyer = await outside_counsel_service.create_lawyer(
        session,
        actor_id=current_user.db_id,
        firm_id=firm_id,
        lawyer_name=body.lawyer_name,
        email=body.email,
        bar_number=body.bar_number,
        specialties=body.specialties,
    )
    await _audit(
        session,
        request,
        current_user,
        action="counsel_lawyer.create",
        target_type="counsel_lawyers",
        target_id=lawyer.id,
    )
    return CounselLawyerOut.model_validate(lawyer)


@router.get("/lawyers", response_model=Page[CounselLawyerOut], summary="弁護士一覧")
async def list_lawyers(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> Page[CounselLawyerOut]:
    items, total = await outside_counsel_service.list_lawyers(session, page=page, size=size)
    return Page[CounselLawyerOut](
        items=[CounselLawyerOut.model_validate(lawyer) for lawyer in items],
        total=total,
        page=page,
        size=size,
    )


# ---------------------------------------------------------------- 依頼 ---
@router.get("/engagements", response_model=Page[EngagementOut], summary="依頼一覧")
async def list_engagements(
    status_: str | None = Query(default=None, alias="status"),
    firm_id: int | None = Query(default=None),
    matter_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> Page[EngagementOut]:
    items, total = await outside_counsel_service.list_engagements(
        session, status=status_, firm_id=firm_id, matter_id=matter_id, page=page, size=size
    )
    return Page[EngagementOut](
        items=[EngagementOut.model_validate(e) for e in items], total=total, page=page, size=size
    )


@router.post(
    "/engagements",
    response_model=EngagementOut,
    status_code=status.HTTP_201_CREATED,
    summary="依頼起票（#85）",
)
async def create_engagement(
    body: EngagementCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> EngagementOut:
    engagement = await outside_counsel_service.create_engagement(
        session,
        actor_id=current_user.db_id,
        firm_id=body.firm_id,
        title=body.title,
        question=body.question,
        lawyer_id=body.lawyer_id,
        matter_id=body.matter_id,
        due_date=body.due_date,
        conflict_of_interest=body.conflict_of_interest,
        conflict_note=body.conflict_note,
        confidential=body.confidential,
        fee_estimate_jpy=body.fee_estimate_jpy,
    )
    await _audit(
        session,
        request,
        current_user,
        action="engagement.create",
        target_type="legal_engagements",
        target_id=engagement.id,
    )
    return EngagementOut.model_validate(engagement)


@router.get("/engagements/{engagement_id}", response_model=EngagementOut, summary="依頼詳細")
async def get_engagement(
    engagement_id: int,
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> EngagementOut:
    engagement = await outside_counsel_service.get_engagement(session, engagement_id=engagement_id)
    return EngagementOut.model_validate(engagement)


@router.patch(
    "/engagements/{engagement_id}",
    response_model=EngagementOut,
    summary="依頼の期限・利益相反等の更新",
)
async def update_engagement(
    engagement_id: int,
    body: EngagementUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> EngagementOut:
    engagement = await outside_counsel_service.update_engagement(
        session,
        engagement_id=engagement_id,
        actor_id=current_user.db_id,
        due_date=body.due_date,
        conflict_note=body.conflict_note,
        fee_estimate_jpy=body.fee_estimate_jpy,
        confidential=body.confidential,
        conflict_of_interest=body.conflict_of_interest,
    )
    await _audit(
        session,
        request,
        current_user,
        action="engagement.update",
        target_type="legal_engagements",
        target_id=engagement.id,
    )
    return EngagementOut.model_validate(engagement)


@router.post(
    "/engagements/{engagement_id}/answer",
    response_model=EngagementOut,
    summary="回答登録（#89・open→answered）",
)
async def submit_answer(
    engagement_id: int,
    body: EngagementAnswerIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> EngagementOut:
    engagement = await outside_counsel_service.submit_answer(
        session, engagement_id=engagement_id, actor_id=current_user.db_id, answer=body.answer
    )
    await _audit(
        session,
        request,
        current_user,
        action="engagement.answer",
        target_type="legal_engagements",
        target_id=engagement.id,
    )
    return EngagementOut.model_validate(engagement)


@router.post(
    "/engagements/{engagement_id}/confirm",
    response_model=EngagementOut,
    summary="回答確認（answered→confirmed）",
)
async def confirm_engagement(
    engagement_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> EngagementOut:
    engagement = await outside_counsel_service.confirm_engagement(
        session, engagement_id=engagement_id, actor_id=current_user.db_id
    )
    await _audit(
        session,
        request,
        current_user,
        action="engagement.confirm",
        target_type="legal_engagements",
        target_id=engagement.id,
    )
    return EngagementOut.model_validate(engagement)


@router.post(
    "/engagements/{engagement_id}/cancel", response_model=EngagementOut, summary="依頼取消"
)
async def cancel_engagement(
    engagement_id: int,
    body: EngagementCancelIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> EngagementOut:
    engagement = await outside_counsel_service.cancel_engagement(
        session, engagement_id=engagement_id, actor_id=current_user.db_id, reason=body.reason
    )
    await _audit(
        session,
        request,
        current_user,
        action="engagement.cancel",
        target_type="legal_engagements",
        target_id=engagement.id,
    )
    return EngagementOut.model_validate(engagement)
