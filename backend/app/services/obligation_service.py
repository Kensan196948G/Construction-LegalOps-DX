"""契約義務（Obligations）業務サービス.

ロードマップ #9〜#13 / Issue #99:
- #9 契約義務管理: 報告・通知・提出・保険・更新等を登録・状態管理
- #10 Obligations Calendar: due_date ベースの期限バケット（overdue/30日/60日）
- #11 条件成就 / #13 終了チェック: obligation_type=condition / closing として管理
- #12 自動更新判定: contracts.auto_renewal + renewal_notice_days から
  解約通知期限をルールエンジンで導出（AI 不使用・単一の正）
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.contract import Contract
from app.models.enums import ObligationStatus, ObligationType
from app.models.obligation import ContractObligation
from app.models.user import User

logger = structlog.get_logger(__name__)

_OPEN_STATUSES = frozenset({ObligationStatus.OPEN.value, ObligationStatus.IN_PROGRESS.value})
# ステータス更新 API で直接指定可能な状態（完了・放棄は専用エンドポイント）
_PATCHABLE_STATUSES = frozenset({ObligationStatus.OPEN.value, ObligationStatus.IN_PROGRESS.value})


def _today() -> date:
    return datetime.now(UTC).date()


def _days_until(due: date | None) -> int | None:
    if due is None:
        return None
    return (due - _today()).days


def obligation_bucket(due: date | None, *, status: str) -> str | None:
    """期限バケット（未完了・due_date ありのみ）. none/overdue/within_30/within_60/future."""
    if status not in _OPEN_STATUSES or due is None:
        return None
    days = _days_until(due)
    assert days is not None
    if days < 0:
        return "overdue"
    if days <= 30:
        return "within_30"
    if days <= 60:
        return "within_60"
    return "future"


async def _get_contract(session: AsyncSession, *, contract_id: int) -> Contract:
    contract = await session.get(Contract, contract_id)
    if contract is None:
        raise NotFoundError(f"contract {contract_id} not found")
    return contract


async def _validate_assignee(session: AsyncSession, *, assignee_id: int | None) -> None:
    if assignee_id is None:
        return
    user = await session.get(User, assignee_id)
    if user is None:
        raise NotFoundError(f"user {assignee_id} not found")


async def create_obligation(
    session: AsyncSession,
    *,
    contract_id: int,
    actor_id: int | None,
    obligation_type: str,
    title: str,
    description: str | None = None,
    due_date: date | None = None,
    assignee_id: int | None = None,
    status: str = ObligationStatus.OPEN.value,
) -> ContractObligation:
    await _get_contract(session, contract_id=contract_id)
    await _validate_assignee(session, assignee_id=assignee_id)
    try:
        type_value = ObligationType(obligation_type).value
    except ValueError as exc:
        raise ValidationError(f"不正な義務種別: {obligation_type!r}") from exc
    try:
        status_value = ObligationStatus(status).value
    except ValueError as exc:
        raise ValidationError(f"不正な義務ステータス: {status!r}") from exc
    if status_value not in _OPEN_STATUSES:
        raise ValidationError("作成時のステータスは open / in_progress のみです。")

    obligation = ContractObligation(
        contract_id=contract_id,
        obligation_type=type_value,
        title=title,
        description=description,
        due_date=due_date,
        status=status_value,
        assignee_id=assignee_id,
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(obligation)
    await session.flush()
    await session.refresh(obligation)
    return obligation


async def list_obligations(
    session: AsyncSession,
    *,
    contract_id: int | None = None,
    obligation_type: str | None = None,
    status: str | None = None,
    bucket: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    size: int = 50,
) -> tuple[list[ContractObligation], int]:
    stmt = select(ContractObligation)
    if contract_id is not None:
        stmt = stmt.where(ContractObligation.contract_id == contract_id)
    if obligation_type is not None:
        stmt = stmt.where(
            ContractObligation.obligation_type == ObligationType(obligation_type).value
        )
    if status is not None:
        stmt = stmt.where(ContractObligation.status == ObligationStatus(status).value)
    if date_from is not None:
        stmt = stmt.where(ContractObligation.due_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(ContractObligation.due_date <= date_to)
    rows = list(
        (
            await session.execute(
                stmt.order_by(
                    ContractObligation.due_date.is_(None),
                    ContractObligation.due_date.asc(),
                )
            )
        ).scalars()
    )

    if bucket is not None:
        rows = [
            o for o in rows
            if obligation_bucket(o.due_date, status=o.status) == bucket
        ]
    total = len(rows)
    items = rows[(page - 1) * size : page * size]
    return items, total


async def update_obligation(
    session: AsyncSession,
    *,
    obligation_id: int,
    actor_id: int | None,
    title: str | None = None,
    description: str | None = None,
    due_date: date | None = None,
    assignee_id: int | None = None,
    status: str | None = None,
) -> ContractObligation:
    obligation = await session.get(ContractObligation, obligation_id)
    if obligation is None:
        raise NotFoundError(f"obligation {obligation_id} not found")
    if obligation.status in {
        ObligationStatus.COMPLETED.value,
        ObligationStatus.WAIVED.value,
    }:
        raise ConflictError("完了・放棄済みの義務は更新できません。")
    await _validate_assignee(session, assignee_id=assignee_id)

    if title is not None:
        obligation.title = title
    if description is not None:
        obligation.description = description
    if due_date is not None:
        obligation.due_date = due_date
    if assignee_id is not None:
        obligation.assignee_id = assignee_id
    if status is not None:
        status_value = ObligationStatus(status).value
        if status_value not in _PATCHABLE_STATUSES:
            raise ValidationError("この API では open / in_progress のみ指定できます。")
        obligation.status = status_value
    obligation.updated_by = actor_id
    await session.flush()
    await session.refresh(obligation)
    return obligation


async def _transition(
    session: AsyncSession, *, obligation_id: int, actor_id: int | None, target: ObligationStatus
) -> ContractObligation:
    obligation = await session.get(ContractObligation, obligation_id)
    if obligation is None:
        raise NotFoundError(f"obligation {obligation_id} not found")
    if obligation.status == target.value:
        raise ConflictError(f"義務 {obligation_id} は既に {target.value!r} です。")
    obligation.status = target.value
    obligation.updated_by = actor_id
    if target == ObligationStatus.COMPLETED:
        obligation.completed_at = datetime.now(UTC)
    elif obligation.status == ObligationStatus.WAIVED:
        obligation.completed_at = None
    await session.flush()
    await session.refresh(obligation)
    return obligation


async def complete_obligation(
    session: AsyncSession, *, obligation_id: int, actor_id: int | None
) -> ContractObligation:
    return await _transition(
        session, obligation_id=obligation_id, actor_id=actor_id, target=ObligationStatus.COMPLETED
    )


async def waive_obligation(
    session: AsyncSession, *, obligation_id: int, actor_id: int | None
) -> ContractObligation:
    return await _transition(
        session, obligation_id=obligation_id, actor_id=actor_id, target=ObligationStatus.WAIVED
    )


async def renewal_check(
    session: AsyncSession, *, contract_id: int | None = None
) -> list[dict[str, Any]]:
    """自動更新契約の解約通知期限チェック（#12・ルールエンジン）.

    対象: ``auto_renewal = true`` かつ ``end_date`` を持つ契約。
    ``notice_deadline = end_date - renewal_notice_days``、``days_left`` は
    今日からの残日数（負なら通知期限超過）。state: notice_overdue /
    upcoming(30 日以内) / ok / expired(期間満了済み)
    """
    stmt = select(Contract).where(Contract.auto_renewal.is_(True))
    if contract_id is not None:
        stmt = stmt.where(Contract.id == contract_id)
    contracts = list((await session.execute(stmt)).scalars())
    today = _today()
    result: list[dict[str, Any]] = []
    for contract in contracts:
        end_date = contract.end_date
        if end_date is None:
            continue
        notice_deadline = end_date - timedelta(days=contract.renewal_notice_days)
        days_left = (notice_deadline - today).days
        if end_date < today:
            state = "expired"
        elif days_left <= 0:
            state = "notice_overdue"
        elif days_left <= 30:
            state = "upcoming"
        else:
            state = "ok"
        result.append(
            {
                "contract_id": contract.id,
                "contract_no": contract.contract_no,
                "title": contract.title,
                "end_date": end_date,
                "auto_renewal": contract.auto_renewal,
                "renewal_notice_days": contract.renewal_notice_days,
                "notice_deadline": notice_deadline,
                "days_left": days_left,
                "state": state,
            }
        )
    result.sort(key=lambda r: int(r["days_left"]))
    return result


__all__ = [
    "complete_obligation",
    "create_obligation",
    "list_obligations",
    "obligation_bucket",
    "renewal_check",
    "update_obligation",
    "waive_obligation",
]
