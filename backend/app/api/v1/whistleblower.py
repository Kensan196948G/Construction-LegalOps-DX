"""内部通報・調査管理エンドポイント（Issue #123・ロードマップ #125〜#135）.

NOTE（統合担当者向け）: 本ルーターは ``app.api.v1.__init__`` に未登録。
並列実装との衝突を避けるため意図的に外してある。統合時に以下を追加する
こと（詳細は PR 本文 / エージェント最終報告を参照）。

    from app.api.v1 import whistleblower
    ...
    api_router.include_router(whistleblower.router)

アクセス制御方針:
* 通報の新規作成（POST /whistleblower/reports）は guest を除く全ロールに開放
  （内部通報は誰でも起票できる必要があるため）。
* 一覧・詳細・タイムライン・証拠・ヒアリング・措置・ACL 管理は
  admin/auditor または調査担当者 ACL（``WhistleblowerCaseAccess``）保有者
  のみに制限する（サービス層 ``whistleblower_service`` が最終判定）。
* 通報者識別情報（reporter profile）は上記に加え
  ``can_view_reporter_identity`` を保有する場合のみ閲覧できる
  （最重要の隔離ポイント）。
* ACL の付与・失効および経営報告匿名集計は admin/auditor 限定。
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import ALL_ROLES, ROLE_GUEST, CurrentUser, require_role
from app.schemas.common import Page
from app.schemas.whistleblower import (
    WhistleblowerActionIn,
    WhistleblowerActionOut,
    WhistleblowerActionStatusIn,
    WhistleblowerAggregateOut,
    WhistleblowerCaseAccessGrantIn,
    WhistleblowerCaseAccessOut,
    WhistleblowerEvidenceIn,
    WhistleblowerEvidenceOut,
    WhistleblowerInterviewIn,
    WhistleblowerInterviewOut,
    WhistleblowerNoteIn,
    WhistleblowerReportCreate,
    WhistleblowerReporterProfileOut,
    WhistleblowerReportOut,
    WhistleblowerStatusIn,
    WhistleblowerTimelineEventOut,
)
from app.services import audit_service, whistleblower_service

router = APIRouter(prefix="/whistleblower", tags=["whistleblower"])

# 通報起票は guest を除く全ロールに開放（誰でも通報できる必要がある）。
_SUBMIT_ROLES = tuple(r for r in ALL_ROLES if r != ROLE_GUEST)
# 案件参照系は全ロールに一旦開放するが、実アクセス可否は
# whistleblower_service（ACL / admin-auditor 判定）が最終決定する。
_CASE_ROLES = _SUBMIT_ROLES
_ADMIN_ROLES = ("admin", "auditor")


async def _audit(
    session: AsyncSession,
    request: Request,
    current_user: CurrentUser,
    *,
    action: str,
    target_id: int,
) -> None:
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action=action,
        target_type="whistleblower_reports",
        target_id=target_id,
        request=request,
        payload=None,
    )


@router.post(
    "/reports",
    response_model=WhistleblowerReportOut,
    status_code=status.HTTP_201_CREATED,
    summary="内部通報受付（匿名可・#125/#126）",
)
async def create_report(
    body: WhistleblowerReportCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_SUBMIT_ROLES)),
) -> WhistleblowerReportOut:
    report = await whistleblower_service.create_report(
        session,
        actor_id=current_user.db_id,
        category=body.category.value,
        title=body.title,
        description=body.description,
        severity=body.severity.value,
        is_anonymous=body.is_anonymous,
        occurred_at=body.occurred_at,
        reporter_name=body.reporter_name,
        contact_email=body.contact_email,
        contact_phone=body.contact_phone,
        department=body.department,
        relationship_to_subject=body.relationship_to_subject,
        consent_identity_disclosure=body.consent_identity_disclosure,
        lead_investigator_id=body.lead_investigator_id,
    )
    # 匿名通報時は actor_id・target_id を監査ログに残さない（隔離の一貫性）。
    # C2（CodeRabbit）: actor_id と target_id（report.id）の組み合わせで
    # 投稿者が特定できてしまうため、匿名通報では両方とも記録しない。
    # IP アドレス・User-Agent も request 由来で投稿者特定に使えるため、
    # 匿名時は request 自体を audit_service.log へ渡さない。
    await audit_service.log(
        session,
        actor_id=None if body.is_anonymous else current_user.db_id,
        action="whistleblower.create",
        target_type="whistleblower_reports",
        target_id=None if body.is_anonymous else report.id,
        request=None if body.is_anonymous else request,
        payload={"is_anonymous": body.is_anonymous},
    )
    return WhistleblowerReportOut.model_validate(report)


@router.get(
    "/reports",
    response_model=Page[WhistleblowerReportOut],
    summary="内部通報一覧（admin/auditor は全件・他は ACL 保有案件のみ）",
)
async def list_reports(
    status_: str | None = Query(default=None, alias="status"),
    category: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_CASE_ROLES)),
) -> Page[WhistleblowerReportOut]:
    items, total = await whistleblower_service.list_reports(
        session,
        role=current_user.role,
        user_id=current_user.db_id,
        status=status_,
        category=category,
        page=page,
        size=size,
    )
    return Page[WhistleblowerReportOut](
        items=[WhistleblowerReportOut.model_validate(r) for r in items],
        total=total,
        page=page,
        size=size,
    )


@router.get(
    "/reports/aggregate",
    response_model=WhistleblowerAggregateOut,
    summary="経営報告匿名集計（#134/#135・admin/auditor 限定）",
)
async def aggregate_reports(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_ADMIN_ROLES)),
) -> WhistleblowerAggregateOut:
    result = await whistleblower_service.aggregate_report(
        session, date_from=date_from, date_to=date_to
    )
    return WhistleblowerAggregateOut.model_validate(result)


@router.get(
    "/reports/{report_id}",
    response_model=WhistleblowerReportOut,
    summary="内部通報詳細（調査担当者 ACL 必須）",
)
async def get_report(
    report_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_CASE_ROLES)),
) -> WhistleblowerReportOut:
    report = await whistleblower_service.get_report(
        session, role=current_user.role, user_id=current_user.db_id, report_id=report_id
    )
    return WhistleblowerReportOut.model_validate(report)


@router.get(
    "/reports/{report_id}/reporter",
    response_model=WhistleblowerReporterProfileOut | None,
    summary="通報者識別情報（最重要の隔離対象・識別情報閲覧権限のみ）",
)
async def get_reporter_profile(
    report_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_CASE_ROLES)),
) -> WhistleblowerReporterProfileOut | None:
    profile = await whistleblower_service.get_reporter_profile(
        session, role=current_user.role, user_id=current_user.db_id, report_id=report_id
    )
    await _audit(
        session,
        request,
        current_user,
        action="whistleblower.reporter_view",
        target_id=report_id,
    )
    if profile is None:
        return None
    return WhistleblowerReporterProfileOut.model_validate(profile)


@router.post(
    "/reports/{report_id}/status",
    response_model=WhistleblowerReportOut,
    summary="通報状態遷移",
)
async def set_status(
    report_id: int,
    body: WhistleblowerStatusIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_CASE_ROLES)),
) -> WhistleblowerReportOut:
    report = await whistleblower_service.set_status(
        session,
        report_id=report_id,
        role=current_user.role,
        user_id=current_user.db_id,
        status=body.status.value,
        note=body.note,
    )
    await _audit(session, request, current_user, action="whistleblower.status", target_id=report_id)
    return WhistleblowerReportOut.model_validate(report)


@router.post(
    "/reports/{report_id}/promote-to-matter",
    response_model=WhistleblowerReportOut,
    summary="Investigative Matter へ昇格（法務 Matter と連携）",
)
async def promote_to_matter(
    report_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_CASE_ROLES)),
) -> WhistleblowerReportOut:
    report = await whistleblower_service.promote_to_matter(
        session, report_id=report_id, role=current_user.role, user_id=current_user.db_id
    )
    await _audit(
        session,
        request,
        current_user,
        action="whistleblower.promote_to_matter",
        target_id=report_id,
    )
    return WhistleblowerReportOut.model_validate(report)


# ---------------------------------------------------------------------------
# 調査担当者限定 ACL（#127）
# ---------------------------------------------------------------------------


@router.get(
    "/reports/{report_id}/access",
    response_model=list[WhistleblowerCaseAccessOut],
    summary="調査担当者 ACL 一覧",
)
async def list_case_access(
    report_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_CASE_ROLES)),
) -> list[WhistleblowerCaseAccessOut]:
    rows = await whistleblower_service.list_case_access(
        session, role=current_user.role, user_id=current_user.db_id, report_id=report_id
    )
    return [WhistleblowerCaseAccessOut.model_validate(r) for r in rows]


@router.post(
    "/reports/{report_id}/access",
    response_model=WhistleblowerCaseAccessOut,
    status_code=status.HTTP_201_CREATED,
    summary="調査担当者 ACL 付与（admin/auditor 限定）",
)
async def grant_case_access(
    report_id: int,
    body: WhistleblowerCaseAccessGrantIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_ADMIN_ROLES)),
) -> WhistleblowerCaseAccessOut:
    grant = await whistleblower_service.grant_case_access(
        session,
        report_id=report_id,
        actor_id=current_user.db_id,
        user_id=body.user_id,
        role_in_case=body.role_in_case.value,
        can_view_reporter_identity=body.can_view_reporter_identity,
        expires_at=body.expires_at,
    )
    await _audit(
        session, request, current_user, action="whistleblower.access_grant", target_id=report_id
    )
    return WhistleblowerCaseAccessOut.model_validate(grant)


@router.delete(
    "/reports/{report_id}/access/{grant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="調査担当者 ACL 失効（admin/auditor 限定）",
)
async def revoke_case_access(
    report_id: int,
    grant_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_ADMIN_ROLES)),
) -> None:
    from app.core.exceptions import NotFoundError

    ok = await whistleblower_service.revoke_case_access(
        session, report_id=report_id, actor_id=current_user.db_id, grant_id=grant_id
    )
    if not ok:
        raise NotFoundError(f"whistleblower case access {grant_id} not found")
    await _audit(
        session, request, current_user, action="whistleblower.access_revoke", target_id=report_id
    )


# ---------------------------------------------------------------------------
# 証拠保全（#129）
# ---------------------------------------------------------------------------


@router.get(
    "/reports/{report_id}/evidence",
    response_model=list[WhistleblowerEvidenceOut],
    summary="証拠一覧（#129）",
)
async def list_evidence(
    report_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_CASE_ROLES)),
) -> list[WhistleblowerEvidenceOut]:
    rows = await whistleblower_service.list_evidence(
        session, report_id=report_id, role=current_user.role, user_id=current_user.db_id
    )
    return [WhistleblowerEvidenceOut.model_validate(r) for r in rows]


@router.post(
    "/reports/{report_id}/evidence",
    response_model=WhistleblowerEvidenceOut,
    status_code=status.HTTP_201_CREATED,
    summary="証拠保全登録（#129）",
)
async def add_evidence(
    report_id: int,
    body: WhistleblowerEvidenceIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_CASE_ROLES)),
) -> WhistleblowerEvidenceOut:
    evidence = await whistleblower_service.add_evidence(
        session,
        report_id=report_id,
        role=current_user.role,
        user_id=current_user.db_id,
        evidence_type=body.evidence_type.value,
        description=body.description,
        occurred_at=body.occurred_at,
        attachment_id=body.attachment_id,
        preserved=body.preserved,
        chain_of_custody=body.chain_of_custody,
    )
    await _audit(
        session, request, current_user, action="whistleblower.evidence_add", target_id=report_id
    )
    return WhistleblowerEvidenceOut.model_validate(evidence)


# ---------------------------------------------------------------------------
# ヒアリング記録（#130）
# ---------------------------------------------------------------------------


@router.get(
    "/reports/{report_id}/interviews",
    response_model=list[WhistleblowerInterviewOut],
    summary="ヒアリング記録一覧（#130）",
)
async def list_interviews(
    report_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_CASE_ROLES)),
) -> list[WhistleblowerInterviewOut]:
    rows = await whistleblower_service.list_interviews(
        session, report_id=report_id, role=current_user.role, user_id=current_user.db_id
    )
    return [WhistleblowerInterviewOut.model_validate(r) for r in rows]


@router.post(
    "/reports/{report_id}/interviews",
    response_model=WhistleblowerInterviewOut,
    status_code=status.HTTP_201_CREATED,
    summary="ヒアリング記録登録（#130）",
)
async def add_interview(
    report_id: int,
    body: WhistleblowerInterviewIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_CASE_ROLES)),
) -> WhistleblowerInterviewOut:
    interview = await whistleblower_service.add_interview(
        session,
        report_id=report_id,
        role=current_user.role,
        user_id=current_user.db_id,
        interviewee_type=body.interviewee_type.value,
        conducted_at=body.conducted_at,
        interviewee_name=body.interviewee_name,
        summary=body.summary,
    )
    await _audit(
        session, request, current_user, action="whistleblower.interview_add", target_id=report_id
    )
    return WhistleblowerInterviewOut.model_validate(interview)


# ---------------------------------------------------------------------------
# 調査タイムライン（#131）
# ---------------------------------------------------------------------------


@router.get(
    "/reports/{report_id}/timeline",
    response_model=list[WhistleblowerTimelineEventOut],
    summary="調査タイムライン（#131・追記専用）",
)
async def list_timeline(
    report_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_CASE_ROLES)),
) -> list[WhistleblowerTimelineEventOut]:
    rows = await whistleblower_service.list_timeline(
        session, report_id=report_id, role=current_user.role, user_id=current_user.db_id
    )
    return [WhistleblowerTimelineEventOut.model_validate(r) for r in rows]


@router.post(
    "/reports/{report_id}/notes",
    response_model=WhistleblowerTimelineEventOut,
    status_code=status.HTTP_201_CREATED,
    summary="タイムラインへメモ追記",
)
async def add_note(
    report_id: int,
    body: WhistleblowerNoteIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_CASE_ROLES)),
) -> WhistleblowerTimelineEventOut:
    event = await whistleblower_service.add_note(
        session,
        report_id=report_id,
        role=current_user.role,
        user_id=current_user.db_id,
        note=body.note,
    )
    await _audit(session, request, current_user, action="whistleblower.note", target_id=report_id)
    return WhistleblowerTimelineEventOut.model_validate(event)


# ---------------------------------------------------------------------------
# 是正措置・再発防止管理（#132/#133）
# ---------------------------------------------------------------------------


@router.get(
    "/reports/{report_id}/actions",
    response_model=list[WhistleblowerActionOut],
    summary="是正措置・再発防止策一覧（#132/#133）",
)
async def list_actions(
    report_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_CASE_ROLES)),
) -> list[WhistleblowerActionOut]:
    rows = await whistleblower_service.list_actions(
        session, report_id=report_id, role=current_user.role, user_id=current_user.db_id
    )
    return [WhistleblowerActionOut.model_validate(r) for r in rows]


@router.post(
    "/reports/{report_id}/actions",
    response_model=WhistleblowerActionOut,
    status_code=status.HTTP_201_CREATED,
    summary="是正措置・再発防止策の登録（#132/#133）",
)
async def add_action(
    report_id: int,
    body: WhistleblowerActionIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_CASE_ROLES)),
) -> WhistleblowerActionOut:
    action = await whistleblower_service.add_action(
        session,
        report_id=report_id,
        role=current_user.role,
        user_id=current_user.db_id,
        action_category=body.action_category.value,
        title=body.title,
        description=body.description,
        owner_id=body.owner_id,
        due_date=body.due_date,
    )
    await _audit(
        session, request, current_user, action="whistleblower.action_add", target_id=report_id
    )
    return WhistleblowerActionOut.model_validate(action)


@router.post(
    "/reports/{report_id}/actions/{action_id}/status",
    response_model=WhistleblowerActionOut,
    summary="是正措置・再発防止策の状態更新",
)
async def update_action_status(
    report_id: int,
    action_id: int,
    body: WhistleblowerActionStatusIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_CASE_ROLES)),
) -> WhistleblowerActionOut:
    action = await whistleblower_service.update_action_status(
        session,
        report_id=report_id,
        action_id=action_id,
        role=current_user.role,
        user_id=current_user.db_id,
        status=body.status.value,
        verification_note=body.verification_note,
    )
    await _audit(
        session, request, current_user, action="whistleblower.action_status", target_id=report_id
    )
    return WhistleblowerActionOut.model_validate(action)


__all__ = ["router"]
