"""内部通報・調査管理 業務サービス（Phase3 §5.10 / Issue #123・#125〜#135）.

最重要要件: 通報者を特定できる情報（``WhistleblowerReporterProfile``）は
調査担当者 ACL（``WhistleblowerCaseAccess``）を持つ利用者と admin/auditor
以外からは一切読めない。PostgreSQL では migration 024 の RLS ポリシーが
DB レベルで強制するが、SQLite / テストではこのサービス層のチェックが
唯一の強制手段になるため、全ての読み取り経路（詳細取得・タイムライン・
証拠・ヒアリング・措置一覧）で :func:`_require_case_access` を必ず通す。

状態遷移・ACL 判定はルールエンジン（AI 不使用）で管理する。
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models.enums import (
    WhistleblowerActionCategory,
    WhistleblowerActionStatus,
    WhistleblowerCaseRole,
    WhistleblowerCategory,
    WhistleblowerEvidenceType,
    WhistleblowerIntervieweeType,
    WhistleblowerReportStatus,
    WhistleblowerSeverity,
    WhistleblowerTimelineEventType,
)
from app.models.user import User
from app.models.whistleblower import (
    WhistleblowerAction,
    WhistleblowerCaseAccess,
    WhistleblowerEvidence,
    WhistleblowerInterview,
    WhistleblowerReport,
    WhistleblowerReporterProfile,
    WhistleblowerTimelineEvent,
)

logger = structlog.get_logger(__name__)

# admin/auditor は案件 ACL 無しで全件アクセス可（既存 access_control.py の
# _ETHICAL_WALL_PRIVILEGED_ROLES と同じ特権ロール定義を踏襲）。
_PRIVILEGED_ROLES: frozenset[str] = frozenset({"admin", "auditor"})


def _now() -> datetime:
    return datetime.now(UTC)


class ReporterIdentityForbiddenError(ForbiddenError):
    """通報者識別情報への未許可アクセス."""

    title = "Reporter Identity Access Forbidden"
    type_slug = "whistleblower-identity-forbidden"


async def _fetch_report(session: AsyncSession, *, report_id: int) -> WhistleblowerReport:
    report = await session.get(WhistleblowerReport, report_id)
    if report is None:
        raise NotFoundError(f"whistleblower report {report_id} not found")
    return report


async def _active_grant(
    session: AsyncSession, *, report_id: int, user_id: int
) -> WhistleblowerCaseAccess | None:
    now = _now()
    row = (
        await session.execute(
            select(WhistleblowerCaseAccess).where(
                WhistleblowerCaseAccess.report_id == report_id,
                WhistleblowerCaseAccess.user_id == user_id,
                WhistleblowerCaseAccess.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    expires_at = row.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at is not None and expires_at <= now:
        return None
    return row


async def has_case_access(
    session: AsyncSession, *, role: str, user_id: int | None, report_id: int
) -> bool:
    """調査担当者 ACL 判定（案件本体・タイムライン・証拠・ヒアリング共通）."""
    if role in _PRIVILEGED_ROLES:
        return True
    if user_id is None:
        return False
    grant = await _active_grant(session, report_id=report_id, user_id=user_id)
    return grant is not None


async def can_view_reporter_identity(
    session: AsyncSession, *, role: str, user_id: int | None, report_id: int
) -> bool:
    """通報者識別情報（reporter profile）へのアクセス可否（最重要の隔離判定）."""
    if role in _PRIVILEGED_ROLES:
        return True
    if user_id is None:
        return False
    grant = await _active_grant(session, report_id=report_id, user_id=user_id)
    return grant is not None and grant.can_view_reporter_identity


async def _require_case_access(
    session: AsyncSession, *, role: str, user_id: int | None, report_id: int
) -> None:
    if not await has_case_access(session, role=role, user_id=user_id, report_id=report_id):
        raise ForbiddenError("この内部通報案件へのアクセス権がありません（調査担当者限定）。")


async def _append_timeline(
    session: AsyncSession,
    *,
    report: WhistleblowerReport,
    event_type: str,
    actor_id: int | None,
    note: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    session.add(
        WhistleblowerTimelineEvent(
            report_id=report.id,
            event_type=event_type,
            note=note,
            payload=payload,
            actor_id=actor_id,
        )
    )


# ---------------------------------------------------------------------------
# 通報受付（#125/#126・匿名通報対応）
# ---------------------------------------------------------------------------


async def create_report(
    session: AsyncSession,
    *,
    actor_id: int | None,
    category: str,
    title: str,
    description: str,
    severity: str = WhistleblowerSeverity.MEDIUM.value,
    is_anonymous: bool = False,
    occurred_at: date | None = None,
    reporter_name: str | None = None,
    contact_email: str | None = None,
    contact_phone: str | None = None,
    department: str | None = None,
    relationship_to_subject: str | None = None,
    consent_identity_disclosure: bool = False,
    lead_investigator_id: int | None = None,
) -> WhistleblowerReport:
    """通報を受け付ける。匿名時は識別情報を一切保存しない（隔離の起点）。"""
    try:
        category_value = WhistleblowerCategory(category).value
    except ValueError as exc:
        raise ValidationError(f"不正なカテゴリ: {category!r}") from exc
    try:
        severity_value = WhistleblowerSeverity(severity).value
    except ValueError as exc:
        raise ValidationError(f"不正な重大度: {severity!r}") from exc

    if lead_investigator_id is not None:
        user = await session.get(User, lead_investigator_id)
        if user is None:
            raise NotFoundError(f"user {lead_investigator_id} not found")

    # 匿名通報時は reporter 由来の識別情報を一切受け付けない（fail-closed）。
    if is_anonymous and any(
        (reporter_name, contact_email, contact_phone, department, relationship_to_subject)
    ):
        raise ValidationError("匿名通報では通報者を特定できる情報を登録できません。")

    report = WhistleblowerReport(
        report_no="",  # flush 後に採番（WB-YYYY-NNNNNN）
        category=category_value,
        title=title,
        description=description,
        status=WhistleblowerReportStatus.RECEIVED.value,
        severity=severity_value,
        is_anonymous=is_anonymous,
        occurred_at=occurred_at,
        received_at=_now(),
        lead_investigator_id=lead_investigator_id,
        # 匿名通報では投稿者を紐付けない（DB 上に一切の識別子を残さない）。
        created_by=None if is_anonymous else actor_id,
        updated_by=None if is_anonymous else actor_id,
    )
    session.add(report)
    await session.flush()

    year = _now().year
    report.report_no = f"WB-{year}-{report.id:06d}"

    if not is_anonymous and any(
        (reporter_name, contact_email, contact_phone, department, relationship_to_subject)
    ):
        profile = WhistleblowerReporterProfile(
            report_id=report.id,
            reporter_name=reporter_name,
            contact_email=contact_email,
            contact_phone=contact_phone,
            department=department,
            relationship_to_subject=relationship_to_subject,
            consent_identity_disclosure=consent_identity_disclosure,
        )
        session.add(profile)

    await _append_timeline(
        session,
        report=report,
        event_type=WhistleblowerTimelineEventType.RECEIVED.value,
        actor_id=None if is_anonymous else actor_id,
        note="受付",
        payload={"category": category_value, "is_anonymous": is_anonymous},
    )
    if lead_investigator_id is not None:
        session.add(
            WhistleblowerCaseAccess(
                report_id=report.id,
                user_id=lead_investigator_id,
                role_in_case=WhistleblowerCaseRole.LEAD_INVESTIGATOR.value,
                can_view_reporter_identity=True,
                granted_by=actor_id,
            )
        )
        await _append_timeline(
            session,
            report=report,
            event_type=WhistleblowerTimelineEventType.ASSIGNED.value,
            actor_id=actor_id,
            payload={"lead_investigator_id": lead_investigator_id},
        )
    await session.flush()
    await session.refresh(report)
    return report


async def list_reports(
    session: AsyncSession,
    *,
    role: str,
    user_id: int | None,
    status: str | None = None,
    category: str | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[WhistleblowerReport], int]:
    """一覧（admin/auditor は全件・それ以外は自分が ACL を持つ案件のみ）."""
    stmt = select(WhistleblowerReport)
    if role not in _PRIVILEGED_ROLES:
        if user_id is None:
            return [], 0
        accessible_ids = (
            (
                await session.execute(
                    select(WhistleblowerCaseAccess.report_id).where(
                        WhistleblowerCaseAccess.user_id == user_id,
                        WhistleblowerCaseAccess.revoked_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        if not accessible_ids:
            return [], 0
        stmt = stmt.where(WhistleblowerReport.id.in_(accessible_ids))
    if status is not None:
        stmt = stmt.where(WhistleblowerReport.status == WhistleblowerReportStatus(status).value)
    if category is not None:
        stmt = stmt.where(WhistleblowerReport.category == WhistleblowerCategory(category).value)

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(WhistleblowerReport.id.desc()).offset((page - 1) * size).limit(size)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows), int(total)


async def get_report(
    session: AsyncSession, *, role: str, user_id: int | None, report_id: int
) -> WhistleblowerReport:
    await _require_case_access(session, role=role, user_id=user_id, report_id=report_id)
    return await _fetch_report(session, report_id=report_id)


async def get_reporter_profile(
    session: AsyncSession, *, role: str, user_id: int | None, report_id: int
) -> WhistleblowerReporterProfile | None:
    """通報者識別情報を取得する（最重要の隔離チェック）."""
    await _fetch_report(session, report_id=report_id)
    if not await can_view_reporter_identity(
        session, role=role, user_id=user_id, report_id=report_id
    ):
        raise ReporterIdentityForbiddenError(
            "通報者情報は調査担当者（識別情報閲覧権限あり）のみ閲覧できます。"
        )
    row = (
        await session.execute(
            select(WhistleblowerReporterProfile).where(
                WhistleblowerReporterProfile.report_id == report_id
            )
        )
    ).scalar_one_or_none()
    return row


# ---------------------------------------------------------------------------
# 調査担当者限定 ACL（#127）
# ---------------------------------------------------------------------------


async def grant_case_access(
    session: AsyncSession,
    *,
    report_id: int,
    actor_id: int | None,
    user_id: int,
    role_in_case: str = WhistleblowerCaseRole.INVESTIGATOR.value,
    can_view_reporter_identity: bool = True,
    expires_at: datetime | None = None,
) -> WhistleblowerCaseAccess:
    report = await _fetch_report(session, report_id=report_id)
    try:
        role_value = WhistleblowerCaseRole(role_in_case).value
    except ValueError as exc:
        raise ValidationError(f"不正な役割: {role_in_case!r}") from exc
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError(f"user {user_id} not found")

    existing = (
        await session.execute(
            select(WhistleblowerCaseAccess).where(
                WhistleblowerCaseAccess.report_id == report_id,
                WhistleblowerCaseAccess.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        grant = WhistleblowerCaseAccess(
            report_id=report_id,
            user_id=user_id,
            role_in_case=role_value,
            can_view_reporter_identity=can_view_reporter_identity,
            granted_by=actor_id,
            expires_at=expires_at,
            revoked_at=None,
        )
        session.add(grant)
    else:
        existing.role_in_case = role_value
        existing.can_view_reporter_identity = can_view_reporter_identity
        existing.granted_by = actor_id
        existing.expires_at = expires_at
        existing.revoked_at = None
        grant = existing
    await _append_timeline(
        session,
        report=report,
        event_type=WhistleblowerTimelineEventType.ACCESS_GRANTED.value,
        actor_id=actor_id,
        payload={"user_id": user_id, "role_in_case": role_value},
    )
    await session.flush()
    await session.refresh(grant)
    return grant


async def revoke_case_access(
    session: AsyncSession, *, report_id: int, actor_id: int | None, grant_id: int
) -> bool:
    report = await _fetch_report(session, report_id=report_id)
    grant = await session.get(WhistleblowerCaseAccess, grant_id)
    if grant is None or grant.report_id != report_id or grant.revoked_at is not None:
        return False
    grant.revoked_at = _now()
    await _append_timeline(
        session,
        report=report,
        event_type=WhistleblowerTimelineEventType.ACCESS_REVOKED.value,
        actor_id=actor_id,
        payload={"user_id": grant.user_id},
    )
    await session.flush()
    return True


async def list_case_access(
    session: AsyncSession, *, role: str, user_id: int | None, report_id: int
) -> list[WhistleblowerCaseAccess]:
    await _require_case_access(session, role=role, user_id=user_id, report_id=report_id)
    rows = (
        (
            await session.execute(
                select(WhistleblowerCaseAccess)
                .where(WhistleblowerCaseAccess.report_id == report_id)
                .order_by(WhistleblowerCaseAccess.id)
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


# ---------------------------------------------------------------------------
# 状態遷移・是正措置連動
# ---------------------------------------------------------------------------


async def set_status(
    session: AsyncSession,
    *,
    report_id: int,
    role: str,
    user_id: int | None,
    status: str,
    note: str | None = None,
) -> WhistleblowerReport:
    await _require_case_access(session, role=role, user_id=user_id, report_id=report_id)
    try:
        target = WhistleblowerReportStatus(status).value
    except ValueError as exc:
        raise ValidationError(f"不正な状態: {status!r}") from exc
    report = await _fetch_report(session, report_id=report_id)
    if report.status == target:
        raise ConflictError(f"通報 {report_id} は既に {target!r} です。")
    if report.status in {
        WhistleblowerReportStatus.CLOSED.value,
        WhistleblowerReportStatus.DISMISSED.value,
    }:
        raise ConflictError("完了・却下済みの通報は状態変更できません。")

    status_from = report.status
    report.status = target
    report.updated_by = user_id
    if target in {
        WhistleblowerReportStatus.CLOSED.value,
        WhistleblowerReportStatus.DISMISSED.value,
    }:
        report.closed_at = _now()
        report.close_note = note
    await _append_timeline(
        session,
        report=report,
        event_type=WhistleblowerTimelineEventType.STATUS_CHANGED.value,
        actor_id=user_id,
        note=note,
        payload={"status_from": status_from, "status_to": target},
    )
    await session.flush()
    await session.refresh(report)
    return report


async def promote_to_matter(
    session: AsyncSession,
    *,
    report_id: int,
    role: str,
    user_id: int | None,
) -> WhistleblowerReport:
    """調査案件として法務 Matter へ昇格する（Investigative Matter 連携）."""
    await _require_case_access(session, role=role, user_id=user_id, report_id=report_id)
    report = await _fetch_report(session, report_id=report_id)
    if report.matter_id is not None:
        raise ConflictError("既に Matter が連携されています。")

    from app.services import matter_service

    matter = await matter_service.create_matter(
        session,
        actor_id=user_id,
        title=f"内部通報調査: {report.report_no}",
        matter_type="compliance",
        description="内部通報に基づく調査案件（詳細は内部通報システム側で管理）。",
        priority="high" if report.severity in {"high", "critical"} else "medium",
        source_type="whistleblower",
        source_id=report.id,
    )
    report.matter_id = matter.id
    report.updated_by = user_id
    await _append_timeline(
        session,
        report=report,
        event_type=WhistleblowerTimelineEventType.MATTER_LINKED.value,
        actor_id=user_id,
        payload={"matter_id": matter.id},
    )
    await session.flush()
    await session.refresh(report)
    return report


# ---------------------------------------------------------------------------
# 証拠保全（#129）
# ---------------------------------------------------------------------------


async def add_evidence(
    session: AsyncSession,
    *,
    report_id: int,
    role: str,
    user_id: int | None,
    evidence_type: str,
    description: str | None = None,
    occurred_at: date | None = None,
    attachment_id: int | None = None,
    preserved: bool = False,
    chain_of_custody: str | None = None,
) -> WhistleblowerEvidence:
    await _require_case_access(session, role=role, user_id=user_id, report_id=report_id)
    report = await _fetch_report(session, report_id=report_id)
    try:
        type_value = WhistleblowerEvidenceType(evidence_type).value
    except ValueError as exc:
        raise ValidationError(f"不正な証拠種別: {evidence_type!r}") from exc
    evidence = WhistleblowerEvidence(
        report_id=report.id,
        evidence_type=type_value,
        description=description,
        occurred_at=occurred_at,
        attachment_id=attachment_id,
        preserved=preserved,
        chain_of_custody=chain_of_custody,
        created_by=user_id,
        updated_by=user_id,
    )
    session.add(evidence)
    await _append_timeline(
        session,
        report=report,
        event_type=WhistleblowerTimelineEventType.EVIDENCE_ADDED.value,
        actor_id=user_id,
        payload={"evidence_type": type_value},
    )
    await session.flush()
    await session.refresh(evidence)
    return evidence


async def list_evidence(
    session: AsyncSession, *, report_id: int, role: str, user_id: int | None
) -> list[WhistleblowerEvidence]:
    await _require_case_access(session, role=role, user_id=user_id, report_id=report_id)
    rows = (
        (
            await session.execute(
                select(WhistleblowerEvidence)
                .where(WhistleblowerEvidence.report_id == report_id)
                .order_by(WhistleblowerEvidence.id)
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


# ---------------------------------------------------------------------------
# ヒアリング記録（#130）
# ---------------------------------------------------------------------------


async def add_interview(
    session: AsyncSession,
    *,
    report_id: int,
    role: str,
    user_id: int | None,
    interviewee_type: str,
    conducted_at: datetime,
    interviewee_name: str | None = None,
    summary: str | None = None,
) -> WhistleblowerInterview:
    await _require_case_access(session, role=role, user_id=user_id, report_id=report_id)
    report = await _fetch_report(session, report_id=report_id)
    try:
        type_value = WhistleblowerIntervieweeType(interviewee_type).value
    except ValueError as exc:
        raise ValidationError(f"不正なヒアリング対象種別: {interviewee_type!r}") from exc
    interview = WhistleblowerInterview(
        report_id=report.id,
        interviewee_type=type_value,
        interviewee_name=interviewee_name,
        conducted_at=conducted_at,
        conducted_by=user_id,
        summary=summary,
        created_by=user_id,
        updated_by=user_id,
    )
    session.add(interview)
    await _append_timeline(
        session,
        report=report,
        event_type=WhistleblowerTimelineEventType.INTERVIEW_CONDUCTED.value,
        actor_id=user_id,
        payload={"interviewee_type": type_value},
    )
    await session.flush()
    await session.refresh(interview)
    return interview


async def list_interviews(
    session: AsyncSession, *, report_id: int, role: str, user_id: int | None
) -> list[WhistleblowerInterview]:
    await _require_case_access(session, role=role, user_id=user_id, report_id=report_id)
    rows = (
        (
            await session.execute(
                select(WhistleblowerInterview)
                .where(WhistleblowerInterview.report_id == report_id)
                .order_by(WhistleblowerInterview.id)
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


# ---------------------------------------------------------------------------
# タイムライン（#131）
# ---------------------------------------------------------------------------


async def list_timeline(
    session: AsyncSession, *, report_id: int, role: str, user_id: int | None
) -> list[WhistleblowerTimelineEvent]:
    await _require_case_access(session, role=role, user_id=user_id, report_id=report_id)
    rows = (
        (
            await session.execute(
                select(WhistleblowerTimelineEvent)
                .where(WhistleblowerTimelineEvent.report_id == report_id)
                .order_by(WhistleblowerTimelineEvent.id)
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def add_note(
    session: AsyncSession, *, report_id: int, role: str, user_id: int | None, note: str
) -> WhistleblowerTimelineEvent:
    await _require_case_access(session, role=role, user_id=user_id, report_id=report_id)
    report = await _fetch_report(session, report_id=report_id)
    event = WhistleblowerTimelineEvent(
        report_id=report.id,
        event_type=WhistleblowerTimelineEventType.NOTE.value,
        note=note,
        actor_id=user_id,
    )
    session.add(event)
    await session.flush()
    await session.refresh(event)
    return event


# ---------------------------------------------------------------------------
# 是正措置・再発防止管理（#132/#133）
# ---------------------------------------------------------------------------


async def add_action(
    session: AsyncSession,
    *,
    report_id: int,
    role: str,
    user_id: int | None,
    action_category: str,
    title: str,
    description: str | None = None,
    owner_id: int | None = None,
    due_date: date | None = None,
) -> WhistleblowerAction:
    await _require_case_access(session, role=role, user_id=user_id, report_id=report_id)
    report = await _fetch_report(session, report_id=report_id)
    try:
        category_value = WhistleblowerActionCategory(action_category).value
    except ValueError as exc:
        raise ValidationError(f"不正な措置区分: {action_category!r}") from exc
    if owner_id is not None:
        owner = await session.get(User, owner_id)
        if owner is None:
            raise NotFoundError(f"user {owner_id} not found")
    action = WhistleblowerAction(
        report_id=report.id,
        action_category=category_value,
        title=title,
        description=description,
        owner_id=owner_id,
        due_date=due_date,
        status=WhistleblowerActionStatus.OPEN.value,
        created_by=user_id,
        updated_by=user_id,
    )
    session.add(action)
    await _append_timeline(
        session,
        report=report,
        event_type=WhistleblowerTimelineEventType.ACTION_ADDED.value,
        actor_id=user_id,
        payload={"action_category": category_value, "title": title},
    )
    await session.flush()
    await session.refresh(action)
    return action


async def update_action_status(
    session: AsyncSession,
    *,
    report_id: int,
    action_id: int,
    role: str,
    user_id: int | None,
    status: str,
    verification_note: str | None = None,
) -> WhistleblowerAction:
    await _require_case_access(session, role=role, user_id=user_id, report_id=report_id)
    action = await session.get(WhistleblowerAction, action_id)
    if action is None or action.report_id != report_id:
        raise NotFoundError(f"whistleblower action {action_id} not found")
    try:
        target = WhistleblowerActionStatus(status).value
    except ValueError as exc:
        raise ValidationError(f"不正な状態: {status!r}") from exc
    action.status = target
    action.updated_by = user_id
    now = _now()
    if target == WhistleblowerActionStatus.COMPLETED.value:
        action.completed_at = now
    elif target == WhistleblowerActionStatus.VERIFIED.value:
        action.verified_by = user_id
        action.verified_at = now
        action.verification_note = verification_note
    await session.flush()
    await session.refresh(action)
    return action


async def list_actions(
    session: AsyncSession, *, report_id: int, role: str, user_id: int | None
) -> list[WhistleblowerAction]:
    await _require_case_access(session, role=role, user_id=user_id, report_id=report_id)
    rows = (
        (
            await session.execute(
                select(WhistleblowerAction)
                .where(WhistleblowerAction.report_id == report_id)
                .order_by(WhistleblowerAction.id)
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


# ---------------------------------------------------------------------------
# 経営報告匿名集計（#134/#135・個人特定不可能な集計のみ）
# ---------------------------------------------------------------------------


async def aggregate_report(
    session: AsyncSession,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[str, Any]:
    """経営報告向け匿名集計。通報者・個人を一切特定できない件数集計のみ返す。

    admin/auditor 限定（router 側 ``require_role`` で強制）。個々の通報の
    タイトル・本文・reporter 情報は含めない。
    """
    stmt = select(WhistleblowerReport)
    if date_from is not None:
        stmt = stmt.where(func.date(WhistleblowerReport.received_at) >= date_from)
    if date_to is not None:
        stmt = stmt.where(func.date(WhistleblowerReport.received_at) <= date_to)
    rows = (await session.execute(stmt)).scalars().all()

    total = len(rows)
    by_category: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    anonymous_count = 0
    substantiated_count = 0
    dismissed_count = 0
    close_durations_days: list[int] = []

    for r in rows:
        by_category[r.category] = by_category.get(r.category, 0) + 1
        by_status[r.status] = by_status.get(r.status, 0) + 1
        by_severity[r.severity] = by_severity.get(r.severity, 0) + 1
        if r.is_anonymous:
            anonymous_count += 1
        if r.substantiated is True:
            substantiated_count += 1
        if r.status == WhistleblowerReportStatus.DISMISSED.value:
            dismissed_count += 1
        if r.closed_at is not None:
            received = r.received_at
            closed = r.closed_at
            if received.tzinfo is None:
                received = received.replace(tzinfo=UTC)
            if closed.tzinfo is None:
                closed = closed.replace(tzinfo=UTC)
            close_durations_days.append((closed - received).days)

    avg_days_to_close = (
        round(sum(close_durations_days) / len(close_durations_days), 1)
        if close_durations_days
        else None
    )

    return {
        "total": total,
        "anonymous_count": anonymous_count,
        "substantiated_count": substantiated_count,
        "dismissed_count": dismissed_count,
        "by_category": by_category,
        "by_status": by_status,
        "by_severity": by_severity,
        "avg_days_to_close": avg_days_to_close,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
    }


__all__ = [
    "ReporterIdentityForbiddenError",
    "add_action",
    "add_evidence",
    "add_interview",
    "add_note",
    "aggregate_report",
    "can_view_reporter_identity",
    "create_report",
    "get_report",
    "get_reporter_profile",
    "grant_case_access",
    "has_case_access",
    "list_actions",
    "list_case_access",
    "list_evidence",
    "list_interviews",
    "list_reports",
    "list_timeline",
    "promote_to_matter",
    "revoke_case_access",
    "set_status",
    "update_action_status",
]
