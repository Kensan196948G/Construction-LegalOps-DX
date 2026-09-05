"""公共工事特化の業務サービス（ロードマップ #41-#43・#54-#57）.

- #41/#42 発注機関マスタ・機関別契約条件: 発注機関ごとの支払日数・前払率等を管理。
- #54 発注者通知期限管理: 通知の送付期限（due_date）を管理し、期限バケット
  （overdue / within_30 / future）を動的に算出する（保存しない）。
- #55 工期延伸協議・#56 スライド請求・#57 設計変更協議: 発注者との協議プロセスの
  証跡（申出 → 回答・結果／取下げ）。**台帳（確定内容）は既存 change_orders が正本**。
- #43 標準請負約款差分チェック: 契約条項を公共工事標準請負契約約款の重要条項
  カテゴリ（キーワード規則）と突合し、欠落カテゴリを決定論的に検出（AI 不使用）。
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.clause import Clause
from app.models.contract import Contract
from app.models.enums import (
    AgencyType,
    OwnerNotificationStatus,
    OwnerNotificationType,
    PublicWorksConsultationStatus,
    PublicWorksConsultationType,
)
from app.models.public_works import (
    ContractingAgency,
    OwnerNotification,
    PublicWorksConsultation,
)

logger = structlog.get_logger(__name__)

# --------------------------------------------------------------- 約款差分チェック ---
# 公共工事標準請負契約約款の重要条項カテゴリ（決定論的なキーワード規則）
STANDARD_CLAUSE_CATEGORIES: list[tuple[str, tuple[str, ...]]] = [
    ("契約金額", ("契約金額", "請負金額")),
    ("工期・完成期日", ("工期", "完成期日")),
    ("支払・検収", ("支払", "検収", "支払期日")),
    ("前払金", ("前払金", "前払")),
    ("設計変更・契約変更", ("設計変更", "契約変更", "変更")),
    ("工期延長", ("工期延長", "完成期日の変更", "工期の延長")),
    ("監督職員", ("監督職員", "監督員")),
    ("損害賠償", ("損害賠償",)),
    ("危険負担", ("危険負担", "滅失", "き損")),
    ("契約解除", ("解除",)),
    ("瑕疵担保・保証", ("瑕疵", "保証", "契約不適合")),
    ("紛争処理・協議", ("協議", "紛争", "ADR", "和解", "調停", "仲裁")),
]


# --------------------------------------------------------------- #41/#42 機関 ---
async def list_agencies(
    session: AsyncSession,
    *,
    agency_type: str | None = None,
    is_active: bool | None = None,
    page: int = 1,
    size: int = 50,
) -> tuple[list[ContractingAgency], int]:
    stmt = select(ContractingAgency)
    if agency_type is not None:
        try:
            stmt = stmt.where(
                ContractingAgency.agency_type == AgencyType(agency_type).value
            )
        except ValueError as exc:
            raise ValidationError(f"不正な機関種別: {agency_type!r}") from exc
    if is_active is not None:
        stmt = stmt.where(ContractingAgency.is_active == is_active)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = (
        stmt.order_by(ContractingAgency.code)
        .offset((page - 1) * size)
        .limit(size)
    )
    return list((await session.execute(stmt)).scalars().all()), int(total)


async def create_agency(
    session: AsyncSession,
    *,
    actor_id: int | None,
    code: str,
    name: str,
    agency_type: str,
    prefecture: str | None = None,
    contact_email: str | None = None,
    phone: str | None = None,
    payment_deadline_days: int | None = None,
    advance_payment_ratio: float | None = None,
    warranty_period_months: int | None = None,
    requires_slide_clause: bool = False,
    notes: str | None = None,
) -> ContractingAgency:
    """#41/#42 発注機関を登録する."""
    try:
        agency_type_value = AgencyType(agency_type).value
    except ValueError as exc:
        raise ValidationError(f"不正な機関種別: {agency_type!r}") from exc
    if payment_deadline_days is not None and payment_deadline_days <= 0:
        raise ValidationError("支払日数は 1 日以上です。")
    if advance_payment_ratio is not None and not 0.0 <= advance_payment_ratio <= 1.0:
        raise ValidationError("前払率は 0〜1（0〜100%）で指定してください。")
    existing = (
        await session.execute(
            select(ContractingAgency).where(ContractingAgency.code == code)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"発注機関コードが重複しています: {code!r}")

    row = ContractingAgency(
        code=code,
        name=name,
        agency_type=agency_type_value,
        prefecture=prefecture,
        contact_email=contact_email,
        phone=phone,
        payment_deadline_days=payment_deadline_days,
        advance_payment_ratio=advance_payment_ratio,
        warranty_period_months=warranty_period_months,
        requires_slide_clause=requires_slide_clause,
        notes=notes,
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def get_agency(session: AsyncSession, *, agency_id: int) -> ContractingAgency:
    row = await session.get(ContractingAgency, agency_id)
    if row is None:
        raise NotFoundError(f"発注機関が見つかりません（id={agency_id}）")
    return row


# --------------------------------------------------------------- #54 通知 ---
async def _build_notification_no(session: AsyncSession) -> str:
    year = datetime.now(UTC).strftime("%Y")
    prefix = f"ON-{year}-"
    last = (
        await session.execute(
            select(OwnerNotification.notification_no)
            .where(OwnerNotification.notification_no.like(f"{prefix}%"))
            .order_by(OwnerNotification.id.desc())
            .limit(1)
        )
    ).scalars().first()
    next_seq = int(last.split("-")[-1]) + 1 if last else 1
    return f"{prefix}{next_seq:06d}"


async def create_notification(
    session: AsyncSession,
    *,
    actor_id: int | None,
    notification_type: str,
    title: str,
    contract_id: int | None = None,
    agency_id: int | None = None,
    detail: str | None = None,
    due_date: date | None = None,
) -> OwnerNotification:
    """#54 発注者への通知・期限を登録する（open）."""
    try:
        ntype_value = OwnerNotificationType(notification_type).value
    except ValueError as exc:
        raise ValidationError(f"不正な通知種別: {notification_type!r}") from exc
    if contract_id is not None and await session.get(Contract, contract_id) is None:
        raise NotFoundError(f"契約が見つかりません（id={contract_id}）")
    if agency_id is not None:
        await get_agency(session, agency_id=agency_id)

    row = OwnerNotification(
        notification_no="",  # flush 後に採番（ON-YYYY-NNNNNN）
        contract_id=contract_id,
        agency_id=agency_id,
        notification_type=ntype_value,
        status=OwnerNotificationStatus.OPEN.value,
        title=title,
        detail=detail,
        due_date=due_date,
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    row.notification_no = await _build_notification_no(session)
    await session.flush()
    await session.refresh(row)
    return row


async def list_notifications(
    session: AsyncSession,
    *,
    status: str | None = None,
    notification_type: str | None = None,
    contract_id: int | None = None,
    page: int = 1,
    size: int = 50,
) -> tuple[list[OwnerNotification], int]:
    stmt = select(OwnerNotification)
    if status is not None:
        try:
            stmt = stmt.where(
                OwnerNotification.status == OwnerNotificationStatus(status).value
            )
        except ValueError as exc:
            raise ValidationError(f"不正な状態: {status!r}") from exc
    if notification_type is not None:
        stmt = stmt.where(OwnerNotification.notification_type == notification_type)
    if contract_id is not None:
        stmt = stmt.where(OwnerNotification.contract_id == contract_id)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = (
        stmt.order_by(OwnerNotification.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    return list((await session.execute(stmt)).scalars().all()), int(total)


def notification_bucket(notification: OwnerNotification, *, today: date | None = None) -> str:
    """#54 通知期限のバケットを動的に算出する（overdue / within_30 / future / none）."""
    if notification.status != OwnerNotificationStatus.OPEN.value:
        return "none"
    if notification.due_date is None:
        return "none"
    ref = today or date.today()
    diff = (notification.due_date - ref).days
    if diff < 0:
        return "overdue"
    if diff <= 30:
        return "within_30"
    return "future"


async def get_notification(
    session: AsyncSession, *, notification_id: int
) -> OwnerNotification:
    row = await session.get(OwnerNotification, notification_id)
    if row is None:
        raise NotFoundError(f"発注者通知が見つかりません（id={notification_id}）")
    return row


async def notify_notification(
    session: AsyncSession, *, notification_id: int, actor_id: int | None
) -> OwnerNotification:
    """#54 通知を送付済みにする（open → notified・証跡確定）."""
    row = await get_notification(session, notification_id=notification_id)
    if row.status != OwnerNotificationStatus.OPEN.value:
        raise ConflictError("通知できるのは open（送付待ち）のみです。")
    row.status = OwnerNotificationStatus.NOTIFIED.value
    row.notified_at = datetime.now(UTC)
    row.notified_by = actor_id
    row.updated_by = actor_id
    await session.flush()
    await session.refresh(row)
    return row


async def cancel_notification(
    session: AsyncSession, *, notification_id: int, actor_id: int | None, reason: str
) -> OwnerNotification:
    """#54 通知を取り下げる（open → cancelled）."""
    row = await get_notification(session, notification_id=notification_id)
    if row.status != OwnerNotificationStatus.OPEN.value:
        raise ConflictError("取消できるのは open（送付待ち）のみです。")
    row.status = OwnerNotificationStatus.CANCELLED.value
    row.cancel_reason = reason
    row.updated_by = actor_id
    await session.flush()
    await session.refresh(row)
    return row


# --------------------------------------------------- #55/#56/#57 協議プロセス ---
async def _build_consultation_no(session: AsyncSession) -> str:
    year = datetime.now(UTC).strftime("%Y")
    prefix = f"PW-{year}-"
    last = (
        await session.execute(
            select(PublicWorksConsultation.consultation_no)
            .where(PublicWorksConsultation.consultation_no.like(f"{prefix}%"))
            .order_by(PublicWorksConsultation.id.desc())
            .limit(1)
        )
    ).scalars().first()
    next_seq = int(last.split("-")[-1]) + 1 if last else 1
    return f"{prefix}{next_seq:06d}"


async def create_consultation(
    session: AsyncSession,
    *,
    actor_id: int | None,
    consultation_type: str,
    title: str,
    contract_id: int | None = None,
    agency_id: int | None = None,
    detail: str | None = None,
    requested_at: date | None = None,
    due_date: date | None = None,
    claimed_days: int | None = None,
    claimed_amount_jpy: int | None = None,
) -> PublicWorksConsultation:
    """#55/#56/#57 発注者との協議を申出する（open）."""
    try:
        ctype_value = PublicWorksConsultationType(consultation_type).value
    except ValueError as exc:
        raise ValidationError(f"不正な協議種別: {consultation_type!r}") from exc
    if claimed_days is not None and claimed_days <= 0:
        raise ValidationError("申出日数は 1 日以上です。")
    if claimed_amount_jpy is not None and claimed_amount_jpy < 0:
        raise ValidationError("申出金額は 0 以上です。")
    if contract_id is not None and await session.get(Contract, contract_id) is None:
        raise NotFoundError(f"契約が見つかりません（id={contract_id}）")
    if agency_id is not None:
        await get_agency(session, agency_id=agency_id)

    row = PublicWorksConsultation(
        consultation_no="",  # flush 後に採番（PW-YYYY-NNNNNN）
        contract_id=contract_id,
        agency_id=agency_id,
        consultation_type=ctype_value,
        status=PublicWorksConsultationStatus.OPEN.value,
        title=title,
        detail=detail,
        requested_at=requested_at or date.today(),
        due_date=due_date,
        claimed_days=claimed_days,
        claimed_amount_jpy=claimed_amount_jpy,
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    row.consultation_no = await _build_consultation_no(session)
    await session.flush()
    await session.refresh(row)
    return row


async def list_consultations(
    session: AsyncSession,
    *,
    status: str | None = None,
    consultation_type: str | None = None,
    contract_id: int | None = None,
    page: int = 1,
    size: int = 50,
) -> tuple[list[PublicWorksConsultation], int]:
    stmt = select(PublicWorksConsultation)
    if status is not None:
        try:
            stmt = stmt.where(
                PublicWorksConsultation.status
                == PublicWorksConsultationStatus(status).value
            )
        except ValueError as exc:
            raise ValidationError(f"不正な状態: {status!r}") from exc
    if consultation_type is not None:
        stmt = stmt.where(PublicWorksConsultation.consultation_type == consultation_type)
    if contract_id is not None:
        stmt = stmt.where(PublicWorksConsultation.contract_id == contract_id)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = (
        stmt.order_by(PublicWorksConsultation.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    return list((await session.execute(stmt)).scalars().all()), int(total)


async def get_consultation(
    session: AsyncSession, *, consultation_id: int
) -> PublicWorksConsultation:
    row = await session.get(PublicWorksConsultation, consultation_id)
    if row is None:
        raise NotFoundError(f"協議が見つかりません（id={consultation_id}）")
    return row


async def respond_consultation(
    session: AsyncSession,
    *,
    consultation_id: int,
    actor_id: int | None,
    response_note: str,
    resolved_days: int | None = None,
    resolved_amount_jpy: int | None = None,
) -> PublicWorksConsultation:
    """#55/#56/#57 協議の回答・結果を記録する（open → responded）."""
    row = await get_consultation(session, consultation_id=consultation_id)
    if row.status != PublicWorksConsultationStatus.OPEN.value:
        raise ConflictError("回答できるのは open（協議中）のみです。")
    if resolved_days is not None and resolved_days <= 0:
        raise ValidationError("確定日数は 1 日以上です。")
    if resolved_amount_jpy is not None and resolved_amount_jpy < 0:
        raise ValidationError("確定金額は 0 以上です。")
    row.status = PublicWorksConsultationStatus.RESPONDED.value
    row.response_note = response_note
    row.resolved_days = resolved_days
    row.resolved_amount_jpy = resolved_amount_jpy
    row.responded_at = datetime.now(UTC)
    row.updated_by = actor_id
    await session.flush()
    await session.refresh(row)
    return row


async def cancel_consultation(
    session: AsyncSession,
    *,
    consultation_id: int,
    actor_id: int | None,
    reason: str,
) -> PublicWorksConsultation:
    row = await get_consultation(session, consultation_id=consultation_id)
    if row.status != PublicWorksConsultationStatus.OPEN.value:
        raise ConflictError("取消できるのは open（協議中）のみです。")
    row.status = PublicWorksConsultationStatus.CANCELLED.value
    row.cancel_reason = reason
    row.updated_by = actor_id
    await session.flush()
    await session.refresh(row)
    return row


# --------------------------------------------------------------- #43 約款差分 ---
async def check_standard_clauses(
    session: AsyncSession,
    *,
    contract_id: int,
) -> dict[str, object]:
    """#43 標準請負約款差分チェック: 条項を重要カテゴリと突合する（決定論的）."""
    contract = await session.get(Contract, contract_id)
    if contract is None:
        raise NotFoundError(f"契約が見つかりません（id={contract_id}）")
    clauses = (
        await session.execute(
            select(Clause)
            .where(Clause.contract_id == contract_id)
            .order_by(Clause.seq)
        )
    ).scalars().all()

    categories: list[dict[str, object]] = []
    missing_count = 0
    for category_name, keywords in STANDARD_CLAUSE_CATEGORIES:
        matched_seqs: list[int] = []
        for clause in clauses:
            haystack = f"{clause.title or ''}\n{clause.body}"
            if any(keyword in haystack for keyword in keywords):
                matched_seqs.append(clause.seq)
        covered = len(matched_seqs) > 0
        if not covered:
            missing_count += 1
        categories.append(
            {
                "category": category_name,
                "covered": covered,
                "matched_clause_seqs": matched_seqs[:5],
            }
        )
    return {
        "contract_id": contract_id,
        "contract_no": contract.contract_no,
        "title": contract.title,
        "total_categories": len(STANDARD_CLAUSE_CATEGORIES),
        "covered_categories": len(STANDARD_CLAUSE_CATEGORIES) - missing_count,
        "missing_categories": missing_count,
        "categories": categories,
    }


# --------------------------------------------------------------- #60 Dashboard ---
async def dashboard(session: AsyncSession) -> dict[str, object]:
    """#60 公共工事ダッシュボード集計（決定論的）."""
    agencies_active = (
        await session.execute(
            select(func.count())
            .select_from(ContractingAgency)
            .where(ContractingAgency.is_active.is_(True))
        )
    ).scalar_one()
    notifications_open = (
        await session.execute(
            select(func.count())
            .select_from(OwnerNotification)
            .where(OwnerNotification.status == OwnerNotificationStatus.OPEN.value)
        )
    ).scalar_one()
    open_rows = (
        await session.execute(
            select(OwnerNotification).where(
                OwnerNotification.status == OwnerNotificationStatus.OPEN.value
            )
        )
    ).scalars().all()
    today = date.today()
    notifications_overdue = sum(
        1 for n in open_rows if notification_bucket(n, today=today) == "overdue"
    )
    consultations_open = (
        await session.execute(
            select(func.count())
            .select_from(PublicWorksConsultation)
            .where(PublicWorksConsultation.status == PublicWorksConsultationStatus.OPEN.value)
        )
    ).scalar_one()
    consult_by_type_rows = (
        await session.execute(
            select(
                PublicWorksConsultation.consultation_type,
                func.count(),
            )
            .group_by(PublicWorksConsultation.consultation_type)
        )
    ).all()
    return {
        "agencies_active": int(agencies_active),
        "notifications_open": int(notifications_open),
        "notifications_overdue": int(notifications_overdue),
        "consultations_open": int(consultations_open),
        "consultations_by_type": {t: int(c) for t, c in consult_by_type_rows},
    }


__all__ = [
    "cancel_consultation",
    "cancel_notification",
    "check_standard_clauses",
    "create_agency",
    "create_consultation",
    "create_notification",
    "dashboard",
    "get_agency",
    "get_consultation",
    "get_notification",
    "list_agencies",
    "list_consultations",
    "list_notifications",
    "notification_bucket",
    "notify_notification",
    "respond_consultation",
]
