"""顧問弁護士・外部法律事務所管理の業務サービス.

ロードマップ #85〜#96 / Issue #102:
- 台帳: law_firms（#86）・counsel_lawyers（#87）
- 依頼（#85/#88）: question 付きエンゲージメント起票・回答期限（#90）
- 回答管理（#89）: open → answered → confirmed（cancel 可）
- 利益相反（#91）・Confidential 分類（#92）・費用見込み（#93）

状態遷移はルールエンジン（AI 不使用）。過去回答のナレッジ化（#96）は
confirmed を出口とし、後続の Knowledge 連携で実施する。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.enums import EngagementStatus
from app.models.matter import LegalMatter
from app.models.outside_counsel import CounselLawyer, LawFirm, LegalEngagement
from app.models.user import User

logger = structlog.get_logger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


async def _validate_user(session: AsyncSession, *, user_id: int | None) -> None:
    if user_id is None:
        return
    row = await session.get(User, user_id)
    if row is None:
        raise NotFoundError(f"user {user_id} not found")


# ------------------------------------------------------------------ 台帳 ---
async def create_firm(
    session: AsyncSession,
    *,
    actor_id: int | None,
    firm_name: str,
    contact_email: str | None = None,
    phone: str | None = None,
    address: str | None = None,
    notes: str | None = None,
) -> LawFirm:
    firm = LawFirm(
        firm_name=firm_name,
        contact_email=contact_email,
        phone=phone,
        address=address,
        notes=notes,
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(firm)
    await session.flush()
    await session.refresh(firm)
    return firm


async def list_firms(
    session: AsyncSession, *, active_only: bool = True, page: int = 1, size: int = 50
) -> tuple[list[LawFirm], int]:
    stmt = select(LawFirm)
    if active_only:
        stmt = stmt.where(LawFirm.is_active.is_(True))
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(LawFirm.id.asc()).offset((page - 1) * size).limit(size)
    return list((await session.execute(stmt)).scalars().all()), int(total)


async def get_firm(session: AsyncSession, *, firm_id: int) -> LawFirm:
    firm = await session.get(LawFirm, firm_id)
    if firm is None:
        raise NotFoundError(f"law firm {firm_id} not found")
    return firm


async def create_lawyer(
    session: AsyncSession,
    *,
    actor_id: int | None,
    firm_id: int,
    lawyer_name: str,
    email: str | None = None,
    bar_number: str | None = None,
    specialties: str | None = None,
) -> CounselLawyer:
    await get_firm(session, firm_id=firm_id)
    lawyer = CounselLawyer(
        firm_id=firm_id,
        lawyer_name=lawyer_name,
        email=email,
        bar_number=bar_number,
        specialties=specialties,
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(lawyer)
    await session.flush()
    await session.refresh(lawyer)
    return lawyer


async def list_lawyers(
    session: AsyncSession, *, firm_id: int | None = None, page: int = 1, size: int = 50
) -> tuple[list[CounselLawyer], int]:
    stmt = select(CounselLawyer).where(CounselLawyer.is_active.is_(True))
    if firm_id is not None:
        stmt = stmt.where(CounselLawyer.firm_id == firm_id)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(CounselLawyer.id.asc()).offset((page - 1) * size).limit(size)
    return list((await session.execute(stmt)).scalars().all()), int(total)


# ------------------------------------------------------------------ 依頼 ---
async def _validate_lawyer_firm(
    session: AsyncSession, *, firm_id: int, lawyer_id: int | None
) -> None:
    await get_firm(session, firm_id=firm_id)
    if lawyer_id is not None:
        lawyer = await session.get(CounselLawyer, lawyer_id)
        if lawyer is None:
            raise NotFoundError(f"counsel lawyer {lawyer_id} not found")
        if lawyer.firm_id != firm_id:
            raise ValidationError("担当弁護士は依頼先事務所に所属していません。")


async def create_engagement(
    session: AsyncSession,
    *,
    actor_id: int | None,
    firm_id: int,
    title: str,
    question: str,
    lawyer_id: int | None = None,
    matter_id: int | None = None,
    due_date: Any | None = None,
    conflict_of_interest: bool = False,
    conflict_note: str | None = None,
    confidential: bool = False,
    fee_estimate_jpy: int | None = None,
) -> LegalEngagement:
    await _validate_lawyer_firm(session, firm_id=firm_id, lawyer_id=lawyer_id)
    if matter_id is not None:
        matter = await session.get(LegalMatter, matter_id)
        if matter is None:
            raise NotFoundError(f"matter {matter_id} not found")
    engagement = LegalEngagement(
        engagement_no="",
        firm_id=firm_id,
        lawyer_id=lawyer_id,
        matter_id=matter_id,
        title=title,
        question=question,
        status=EngagementStatus.OPEN.value,
        due_date=due_date,
        conflict_of_interest=conflict_of_interest,
        conflict_note=conflict_note,
        confidential=confidential,
        fee_estimate_jpy=fee_estimate_jpy,
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(engagement)
    await session.flush()
    year = _now().year
    engagement.engagement_no = f"LEG-{year}-{engagement.id:06d}"
    await session.flush()
    await session.refresh(engagement)
    return engagement


async def get_engagement(session: AsyncSession, *, engagement_id: int) -> LegalEngagement:
    engagement = await session.get(LegalEngagement, engagement_id)
    if engagement is None:
        raise NotFoundError(f"engagement {engagement_id} not found")
    return engagement


async def list_engagements(
    session: AsyncSession,
    *,
    status: str | None = None,
    firm_id: int | None = None,
    matter_id: int | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[LegalEngagement], int]:
    stmt = select(LegalEngagement)
    if status is not None:
        stmt = stmt.where(LegalEngagement.status == EngagementStatus(status).value)
    if firm_id is not None:
        stmt = stmt.where(LegalEngagement.firm_id == firm_id)
    if matter_id is not None:
        stmt = stmt.where(LegalEngagement.matter_id == matter_id)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(LegalEngagement.id.desc()).offset((page - 1) * size).limit(size)
    return list((await session.execute(stmt)).scalars().all()), int(total)


async def update_engagement(
    session: AsyncSession,
    *,
    engagement_id: int,
    actor_id: int | None,
    due_date: Any | None = None,
    conflict_note: str | None = None,
    fee_estimate_jpy: int | None = None,
    confidential: bool | None = None,
    conflict_of_interest: bool | None = None,
) -> LegalEngagement:
    engagement = await get_engagement(session, engagement_id=engagement_id)
    if engagement.status in {
        EngagementStatus.CONFIRMED.value,
        EngagementStatus.CANCELLED.value,
    }:
        raise ConflictError("確定・取消済みの依頼は更新できません。")
    if due_date is not None:
        engagement.due_date = due_date
    if conflict_note is not None:
        engagement.conflict_note = conflict_note
    if fee_estimate_jpy is not None:
        engagement.fee_estimate_jpy = fee_estimate_jpy
    if confidential is not None:
        engagement.confidential = confidential
    if conflict_of_interest is not None:
        engagement.conflict_of_interest = conflict_of_interest
    engagement.updated_by = actor_id
    await session.flush()
    await session.refresh(engagement)
    return engagement


async def submit_answer(
    session: AsyncSession,
    *,
    engagement_id: int,
    actor_id: int | None,
    answer: str,
) -> LegalEngagement:
    engagement = await get_engagement(session, engagement_id=engagement_id)
    if engagement.status != EngagementStatus.OPEN.value:
        raise ConflictError(
            f"回答できるのは open（回答待ち）のみです（現在: {engagement.status!r}）。"
        )
    engagement.answer = answer
    engagement.status = EngagementStatus.ANSWERED.value
    engagement.answered_at = _now()
    engagement.answered_by = actor_id
    engagement.updated_by = actor_id
    await session.flush()
    await session.refresh(engagement)
    return engagement


async def confirm_engagement(
    session: AsyncSession, *, engagement_id: int, actor_id: int | None
) -> LegalEngagement:
    engagement = await get_engagement(session, engagement_id=engagement_id)
    if engagement.status != EngagementStatus.ANSWERED.value:
        raise ConflictError("確認できるのは answered のみです。")
    engagement.status = EngagementStatus.CONFIRMED.value
    engagement.updated_by = actor_id
    await session.flush()
    await session.refresh(engagement)
    return engagement


async def cancel_engagement(
    session: AsyncSession,
    *,
    engagement_id: int,
    actor_id: int | None,
    reason: str | None = None,
) -> LegalEngagement:
    engagement = await get_engagement(session, engagement_id=engagement_id)
    if engagement.status == EngagementStatus.CANCELLED.value:
        raise ConflictError("既に取消済みです。")
    if engagement.status == EngagementStatus.CONFIRMED.value:
        raise ConflictError("確認済みの依頼は取消できません。")
    engagement.status = EngagementStatus.CANCELLED.value
    engagement.updated_by = actor_id
    if reason:
        engagement.notes = reason
    await session.flush()
    await session.refresh(engagement)
    return engagement


__all__ = [
    "cancel_engagement",
    "confirm_engagement",
    "create_engagement",
    "create_firm",
    "create_lawyer",
    "get_engagement",
    "get_firm",
    "list_engagements",
    "list_firms",
    "list_lawyers",
    "submit_answer",
    "update_engagement",
]
