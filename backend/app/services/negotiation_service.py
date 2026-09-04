"""契約交渉・Redline 管理の業務サービス（ロードマップ #5〜#8 / Issue #98）.

- #5 Redline 管理: ``proposed_text`` を持つ ``redline`` イベント＋条項の
  ``negotiated_text`` に最新修正案を保持（履歴はイベント列で再構成可能）
- #6 交渉履歴管理: demand / concession / comment をタイムラインとして記録
- #7 条項ステータス: accepted / rejected / negotiating をサービスが唯一管理
- #8 条項オーナー: 法務・工事・営業・購買 等を割当・変更履歴を証跡化

ステータス・オーナーの最終判断は人間（AI 不使用）。イベントは追記専用。
"""

from __future__ import annotations

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.clause import Clause
from app.models.enums import (
    ClauseNegotiationAction,
    ClauseNegotiationStatus,
    ClauseOwner,
)
from app.models.negotiation import ClauseNegotiationEvent

logger = structlog.get_logger(__name__)

_EVENT_ACTIONS = frozenset(
    {
        ClauseNegotiationAction.DEMAND.value,
        ClauseNegotiationAction.CONCESSION.value,
        ClauseNegotiationAction.COMMENT.value,
        ClauseNegotiationAction.REDLINE.value,
    }
)


async def _fetch_contract_clause(
    session: AsyncSession, *, contract_id: int, clause_id: int
) -> Clause:
    clause = await session.get(Clause, clause_id)
    if clause is None or clause.contract_id != contract_id:
        raise NotFoundError(
            f"clause {clause_id} not found in contract {contract_id}"
        )
    return clause


async def add_event(
    session: AsyncSession,
    *,
    contract_id: int,
    actor_id: int | None,
    action: str,
    clause_id: int | None = None,
    round_no: int | None = None,
    note: str | None = None,
    proposed_text: str | None = None,
) -> ClauseNegotiationEvent:
    """交渉イベント（redline / demand / concession / comment）を記録する.

    clause_id 指定時は契約帰属を検証し、redline の修正案は
    条項の ``negotiated_text``（最新修正案）へ反映する。
    """
    try:
        action_value = ClauseNegotiationAction(action).value
    except ValueError as exc:
        raise ValidationError(f"不正な交渉アクション: {action!r}") from exc
    if action_value not in _EVENT_ACTIONS:
        raise ValidationError(
            "この API で記録できるのは redline / demand / concession / comment のみです。"
            f"（{action_value!r} は状態遷移専用）"
        )

    clause: Clause | None = None
    if clause_id is not None:
        clause = await _fetch_contract_clause(session, contract_id=contract_id, clause_id=clause_id)
        if action_value == ClauseNegotiationAction.REDLINE.value and proposed_text is not None:
            clause.negotiated_text = proposed_text

    event = ClauseNegotiationEvent(
        contract_id=contract_id,
        clause_id=clause.id if clause is not None else None,
        round_no=round_no,
        action=action_value,
        note=note,
        proposed_text=proposed_text,
        actor_id=actor_id,
    )
    session.add(event)
    await session.flush()
    await session.refresh(event)
    return event


async def set_clause_status(
    session: AsyncSession,
    *,
    contract_id: int,
    clause_id: int,
    actor_id: int | None,
    status: str,
    note: str | None = None,
) -> Clause:
    """条項ステータスを更新する（#7 Accepted / Rejected / Negotiating）."""
    try:
        status_value = ClauseNegotiationStatus(status).value
    except ValueError as exc:
        raise ValidationError(f"不正な条項ステータス: {status!r}") from exc

    clause = await _fetch_contract_clause(session, contract_id=contract_id, clause_id=clause_id)
    status_from = clause.negotiation_status
    if status_from == status_value:
        raise ConflictError(f"条項 {clause_id} は既に {status_value!r} です。")

    clause.negotiation_status = status_value
    session.add(
        ClauseNegotiationEvent(
            contract_id=contract_id,
            clause_id=clause.id,
            action=ClauseNegotiationAction.STATUS_CHANGE.value,
            status_from=status_from,
            status_to=status_value,
            note=note,
            actor_id=actor_id,
        )
    )
    await session.flush()
    await session.refresh(clause)
    return clause


async def assign_owner(
    session: AsyncSession,
    *,
    contract_id: int,
    clause_id: int,
    actor_id: int | None,
    owner: str,
    note: str | None = None,
) -> Clause:
    """条項オーナーを割当・変更する（#8 法務・工事・営業・購買 等）."""
    try:
        owner_value = ClauseOwner(owner).value
    except ValueError as exc:
        raise ValidationError(f"不正な条項オーナー: {owner!r}") from exc

    clause = await _fetch_contract_clause(session, contract_id=contract_id, clause_id=clause_id)
    owner_from = clause.clause_owner
    if owner_from == owner_value:
        raise ConflictError(f"条項 {clause_id} のオーナーは既に {owner_value!r} です。")

    clause.clause_owner = owner_value
    session.add(
        ClauseNegotiationEvent(
            contract_id=contract_id,
            clause_id=clause.id,
            action=ClauseNegotiationAction.OWNER_CHANGE.value,
            owner_from=owner_from,
            owner_to=owner_value,
            note=note,
            actor_id=actor_id,
        )
    )
    await session.flush()
    await session.refresh(clause)
    return clause


async def list_events(
    session: AsyncSession,
    *,
    contract_id: int,
    clause_id: int | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[ClauseNegotiationEvent], int]:
    """交渉履歴タイムライン（新しい順）."""
    stmt = select(ClauseNegotiationEvent).where(
        ClauseNegotiationEvent.contract_id == contract_id
    )
    if clause_id is not None:
        stmt = stmt.where(ClauseNegotiationEvent.clause_id == clause_id)
    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    stmt = (
        stmt.order_by(ClauseNegotiationEvent.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows), int(total)


__all__ = [
    "add_event",
    "assign_owner",
    "list_events",
    "set_clause_status",
]
