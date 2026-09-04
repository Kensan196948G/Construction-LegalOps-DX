"""Legal Matter Management 業務サービス（ロードマップ #71〜#84 / Issue #101）.

- #71 法務案件台帳 / #72 Matter ID 採番（MT-YYYY-NNNNNN）
- #73 昇格元の記録（source_type/source_id・dispute 等の存在検証付き）
- #74 担当法務アサイン・#78 案件タイムライン（追記専用イベント）
- #79 関係契約リンク（matter_contracts）・#82 Legal Hold 連動

状態遷移・イベントはルールエンジン（AI 不使用）で管理する。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.contract import Contract
from app.models.dispute import Dispute
from app.models.enums import (
    MatterEventType,
    MatterPriority,
    MatterStatus,
    MatterType,
)
from app.models.legal_hold import LegalHoldCase
from app.models.matter import LegalMatter, MatterEvent, matter_contracts_table
from app.models.user import User

logger = structlog.get_logger(__name__)

# 状態遷移: closed 以外は相互遷移可（同一不可）・closed は再 open のみ可
_ACTIVE_STATUSES = frozenset(
    {
        MatterStatus.OPEN.value,
        MatterStatus.IN_PROGRESS.value,
        MatterStatus.WAITING.value,
        MatterStatus.ON_HOLD.value,
    }
)


def _now() -> datetime:
    return datetime.now(UTC)


async def _fetch_matter(session: AsyncSession, *, matter_id: int) -> LegalMatter:
    matter = await session.get(LegalMatter, matter_id)
    if matter is None:
        raise NotFoundError(f"matter {matter_id} not found")
    return matter


async def _append_event(
    session: AsyncSession,
    *,
    matter: LegalMatter,
    event_type: str,
    actor_id: int | None,
    note: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    session.add(
        MatterEvent(
            matter_id=matter.id,
            event_type=event_type,
            note=note,
            payload=payload,
            actor_id=actor_id,
        )
    )


async def _validate_assignee(session: AsyncSession, *, assignee_id: int | None) -> None:
    if assignee_id is None:
        return
    user = await session.get(User, assignee_id)
    if user is None:
        raise NotFoundError(f"user {assignee_id} not found")


async def _validate_source(session: AsyncSession, *, source_type: str, source_id: int) -> None:
    """昇格元の存在検証（#73）: 現状 dispute に対応."""
    if source_type == "dispute":
        dispute = await session.get(Dispute, source_id)
        if dispute is None:
            raise NotFoundError(f"dispute {source_id} not found")


async def create_matter(
    session: AsyncSession,
    *,
    actor_id: int | None,
    title: str,
    matter_type: str,
    description: str | None = None,
    priority: str = MatterPriority.MEDIUM.value,
    assignee_id: int | None = None,
    source_type: str | None = None,
    source_id: int | None = None,
    contract_ids: list[int] | None = None,
    legal_hold_case_id: int | None = None,
) -> LegalMatter:
    """Matter を作成する（matter_no は flush 後に採番）."""
    try:
        type_value = MatterType(matter_type).value
    except ValueError as exc:
        raise ValidationError(f"不正な Matter 種別: {matter_type!r}") from exc
    try:
        priority_value = MatterPriority(priority).value
    except ValueError as exc:
        raise ValidationError(f"不正な優先度: {priority!r}") from exc

    await _validate_assignee(session, assignee_id=assignee_id)
    if source_type is not None:
        if source_id is None:
            raise ValidationError("source_type 指定時は source_id が必須です。")
        if source_type == "dispute":
            await _validate_source(session, source_type=source_type, source_id=source_id)
        elif source_type not in {"manual", "review", "other"}:
            raise ValidationError(f"不正な source_type: {source_type!r}")

    contract_objs: list[Contract] = []
    if contract_ids:
        rows = (
            (await session.execute(select(Contract).where(Contract.id.in_(contract_ids))))
            .scalars()
            .all()
        )
        found = {c.id for c in rows}
        missing = [cid for cid in contract_ids if cid not in found]
        if missing:
            raise NotFoundError(f"contracts not found: {missing}")
        contract_objs = list(rows)

    if legal_hold_case_id is not None:
        hold = await session.get(LegalHoldCase, legal_hold_case_id)
        if hold is None:
            raise NotFoundError(f"legal hold case {legal_hold_case_id} not found")

    matter = LegalMatter(
        matter_no="",  # flush 後に採番（MT-YYYY-NNNNNN）
        title=title,
        description=description,
        matter_type=type_value,
        status=MatterStatus.OPEN.value,
        priority=priority_value,
        assignee_id=assignee_id,
        source_type=source_type,
        source_id=source_id,
        legal_hold_case_id=legal_hold_case_id,
        opened_at=_now(),
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(matter)
    await session.flush()

    year = _now().year
    matter.matter_no = f"MT-{year}-{matter.id:06d}"
    await _append_event(
        session,
        matter=matter,
        event_type=MatterEventType.CREATED.value,
        actor_id=actor_id,
        note="起案",
        payload={"matter_type": type_value, "source_type": source_type},
    )
    if assignee_id is not None:
        await _append_event(
            session,
            matter=matter,
            event_type=MatterEventType.ASSIGNED.value,
            actor_id=actor_id,
            payload={"assignee_id": assignee_id},
        )
    if contract_objs:
        for c in contract_objs:
            await session.execute(
                insert(matter_contracts_table).values(
                    matter_id=matter.id, contract_id=c.id
                )
            )
            await _append_event(
                session,
                matter=matter,
                event_type=MatterEventType.CONTRACT_LINKED.value,
                actor_id=actor_id,
                payload={"contract_id": c.id},
            )
    if legal_hold_case_id is not None:
        await _append_event(
            session,
            matter=matter,
            event_type=MatterEventType.LEGAL_HOLD_LINKED.value,
            actor_id=actor_id,
            payload={"legal_hold_case_id": legal_hold_case_id},
        )
    await session.flush()
    await session.refresh(matter)
    return matter


async def matter_contract_ids(session: AsyncSession, *, matter_id: int) -> list[int]:
    """関係契約リンク id 一覧（async 安全・association 直接参照）."""
    rows = (
        await session.execute(
            select(matter_contracts_table.c.contract_id).where(
                matter_contracts_table.c.matter_id == matter_id
            )
        )
    ).scalars().all()
    return list(rows)


async def get_matter(session: AsyncSession, *, matter_id: int) -> LegalMatter:
    return await _fetch_matter(session, matter_id=matter_id)


async def list_matters(
    session: AsyncSession,
    *,
    status: str | None = None,
    matter_type: str | None = None,
    assignee_id: int | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[LegalMatter], int]:
    stmt = select(LegalMatter)
    if status is not None:
        stmt = stmt.where(LegalMatter.status == MatterStatus(status).value)
    if matter_type is not None:
        stmt = stmt.where(LegalMatter.matter_type == MatterType(matter_type).value)
    if assignee_id is not None:
        stmt = stmt.where(LegalMatter.assignee_id == assignee_id)

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(LegalMatter.id.desc()).offset((page - 1) * size).limit(size)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows), int(total)


async def list_events(session: AsyncSession, *, matter_id: int) -> list[MatterEvent]:
    matter = await _fetch_matter(session, matter_id=matter_id)
    stmt = (
        select(MatterEvent).where(MatterEvent.matter_id == matter.id).order_by(MatterEvent.id.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def set_status(
    session: AsyncSession,
    *,
    matter_id: int,
    actor_id: int | None,
    status: str,
    note: str | None = None,
) -> LegalMatter:
    try:
        target = MatterStatus(status).value
    except ValueError as exc:
        raise ValidationError(f"不正な Matter ステータス: {status!r}") from exc
    matter = await _fetch_matter(session, matter_id=matter_id)
    if matter.status == target:
        raise ConflictError(f"Matter {matter_id} は既に {target!r} です。")
    if matter.status == MatterStatus.CLOSED.value and target != MatterStatus.OPEN.value:
        raise ConflictError("CLOSED の Matter は OPEN（再開）のみ遷移できます。")
    if target == MatterStatus.CLOSED.value and matter.status not in _ACTIVE_STATUSES:
        raise ConflictError(f"現在の状態 {matter.status!r} から CLOSED には遷移できません。")

    status_from = matter.status
    matter.status = target
    matter.updated_by = actor_id
    if target == MatterStatus.CLOSED.value:
        matter.closed_at = _now()
        matter.close_note = note
    else:
        if status_from == MatterStatus.CLOSED.value:
            matter.closed_at = None
            matter.close_note = None
        note = note or "再開"
    event_type = MatterEventType.STATUS_CHANGED.value
    await _append_event(
        session,
        matter=matter,
        event_type=event_type,
        actor_id=actor_id,
        note=note,
        payload={"status_from": status_from, "status_to": target},
    )
    await session.flush()
    await session.refresh(matter)
    return matter


async def assign_assignee(
    session: AsyncSession,
    *,
    matter_id: int,
    actor_id: int | None,
    assignee_id: int | None,
    note: str | None = None,
) -> LegalMatter:
    matter = await _fetch_matter(session, matter_id=matter_id)
    if matter.status == MatterStatus.CLOSED.value:
        raise ConflictError("CLOSED の Matter は担当変更できません。")
    if assignee_id is not None and matter.assignee_id == assignee_id:
        raise ConflictError(f"担当は既に user {assignee_id} です。")
    await _validate_assignee(session, assignee_id=assignee_id)
    prev = matter.assignee_id
    matter.assignee_id = assignee_id
    matter.updated_by = actor_id
    await _append_event(
        session,
        matter=matter,
        event_type=MatterEventType.ASSIGNED.value,
        actor_id=actor_id,
        note=note,
        payload={"assignee_from": prev, "assignee_to": assignee_id},
    )
    await session.flush()
    await session.refresh(matter)
    return matter


async def link_contract(
    session: AsyncSession,
    *,
    matter_id: int,
    actor_id: int | None,
    contract_id: int,
    note: str | None = None,
) -> LegalMatter:
    matter = await _fetch_matter(session, matter_id=matter_id)
    contract = await session.get(Contract, contract_id)
    if contract is None:
        raise NotFoundError(f"contract {contract_id} not found")
    if contract_id in await matter_contract_ids(session, matter_id=matter.id):
        raise ConflictError(f"契約 {contract_id} は既にリンク済みです。")
    await session.execute(
        insert(matter_contracts_table).values(
            matter_id=matter.id, contract_id=contract_id
        )
    )
    matter.updated_by = actor_id
    await _append_event(
        session,
        matter=matter,
        event_type=MatterEventType.CONTRACT_LINKED.value,
        actor_id=actor_id,
        note=note,
        payload={"contract_id": contract_id},
    )
    await session.flush()
    await session.refresh(matter)
    return matter


async def unlink_contract(
    session: AsyncSession,
    *,
    matter_id: int,
    actor_id: int | None,
    contract_id: int,
) -> LegalMatter:
    matter = await _fetch_matter(session, matter_id=matter_id)
    if contract_id not in await matter_contract_ids(session, matter_id=matter.id):
        raise ConflictError(f"契約 {contract_id} はリンクされていません。")
    await session.execute(
        delete(matter_contracts_table).where(
            matter_contracts_table.c.matter_id == matter.id,
            matter_contracts_table.c.contract_id == contract_id,
        )
    )
    matter.updated_by = actor_id
    await _append_event(
        session,
        matter=matter,
        event_type=MatterEventType.CONTRACT_UNLINKED.value,
        actor_id=actor_id,
        payload={"contract_id": contract_id},
    )
    await session.flush()
    await session.refresh(matter)
    return matter


async def set_legal_hold(
    session: AsyncSession,
    *,
    matter_id: int,
    actor_id: int | None,
    legal_hold_case_id: int | None,
) -> LegalMatter:
    """Legal Hold を連動する（#82・null で解除）."""
    matter = await _fetch_matter(session, matter_id=matter_id)
    prev_hold_id: int | None = matter.legal_hold_case_id
    if legal_hold_case_id is None:
        if prev_hold_id is None:
            raise ConflictError("Legal Hold は設定されていません。")
        matter.legal_hold_case_id = None
        event_type = MatterEventType.LEGAL_HOLD_UNLINKED.value
        payload: dict[str, Any] = {"legal_hold_case_id": prev_hold_id}
    else:
        if prev_hold_id == legal_hold_case_id:
            raise ConflictError(f"Legal Hold {legal_hold_case_id} は既に連動済みです。")
        hold = await session.get(LegalHoldCase, legal_hold_case_id)
        if hold is None:
            raise NotFoundError(f"legal hold case {legal_hold_case_id} not found")
        matter.legal_hold_case_id = legal_hold_case_id
        event_type = MatterEventType.LEGAL_HOLD_LINKED.value
        payload = {"legal_hold_case_id": legal_hold_case_id, "from": prev_hold_id}
    matter.updated_by = actor_id
    await _append_event(
        session, matter=matter, event_type=event_type, actor_id=actor_id, payload=payload
    )
    await session.flush()
    await session.refresh(matter)
    return matter


async def add_note(
    session: AsyncSession,
    *,
    matter_id: int,
    actor_id: int | None,
    note: str,
) -> MatterEvent:
    matter = await _fetch_matter(session, matter_id=matter_id)
    event = MatterEvent(
        matter_id=matter.id,
        event_type=MatterEventType.NOTE.value,
        note=note,
        actor_id=actor_id,
    )
    session.add(event)
    await session.flush()
    await session.refresh(event)
    return event


__all__ = [
    "add_note",
    "assign_assignee",
    "create_matter",
    "get_matter",
    "link_contract",
    "list_events",
    "list_matters",
    "matter_contract_ids",
    "set_legal_hold",
    "set_status",
    "unlink_contract",
]
