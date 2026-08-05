"""リーガルホールド管理サービス."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.legal_hold import LegalHoldCase


class LegalHoldError(RuntimeError):
    """リーガルホールド操作エラー（既存アクティブ等）."""


async def start_legal_hold(
    session: AsyncSession,
    *,
    contract_id: int,
    reason: str,
    requested_by: int | None,
    notes: str | None = None,
) -> LegalHoldCase:
    """アクティブなホールドが無ければ開始する."""
    active = (
        await session.execute(
            select(LegalHoldCase).where(
                LegalHoldCase.contract_id == contract_id,
                LegalHoldCase.ended_at.is_(None),
            )
        )
    ).scalars().all()
    if active:
        raise LegalHoldError("contract already under an active legal hold")
    hold = LegalHoldCase(
        contract_id=contract_id,
        reason=reason,
        requested_by=requested_by,
        started_at=datetime.now(UTC),
        ended_at=None,
        notes=notes,
    )
    session.add(hold)
    await session.flush()
    return hold


async def end_legal_hold(session: AsyncSession, *, hold_id: int, actor_id: int) -> bool:
    """ホールドを終了する。存在しなければ False。"""
    hold = await session.get(LegalHoldCase, hold_id)
    if hold is None or hold.ended_at is not None:
        return False
    hold.ended_at = datetime.now(UTC)
    hold.notes = (hold.notes or "") + (
        f"\n[ended by user {actor_id} at {datetime.now(UTC).isoformat()}]"
    )
    await session.flush()
    return True


async def list_legal_holds(
    session: AsyncSession, *, active_only: bool = False
) -> list[LegalHoldCase]:
    stmt = select(LegalHoldCase).order_by(LegalHoldCase.started_at.desc())
    if active_only:
        stmt = stmt.where(LegalHoldCase.ended_at.is_(None))
    rows = await session.execute(stmt)
    return list(rows.scalars().all())


async def is_under_legal_hold(session: AsyncSession, *, contract_id: int) -> bool:
    row = await session.execute(
        select(LegalHoldCase.id).where(
            LegalHoldCase.contract_id == contract_id,
            LegalHoldCase.ended_at.is_(None),
        ).limit(1)
    )
    return row.scalar_one_or_none() is not None
