"""労務費コミットメント（表明）管理の業務サービス（ロードマップ #28）.

契約ごとに労務費・賃金関連の表明（賃金支払確約・労務費適正配分・一括下請負禁止
遵守等）を登録し、履行確認（fulfilled）/違反確認（violated）へ遷移させる。
状態遷移はルールエンジンで決定論的に管理する（AI 不使用）。
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.contract import Contract
from app.models.enums import LaborCommitmentStatus, LaborCommitmentType
from app.models.labor_commitment import LaborCommitment

logger = structlog.get_logger(__name__)

_VERIFIABLE = {
    LaborCommitmentStatus.ACTIVE.value: {
        LaborCommitmentStatus.FULFILLED.value,
        LaborCommitmentStatus.VIOLATED.value,
    },
    LaborCommitmentStatus.FULFILLED.value: set(),
    LaborCommitmentStatus.VIOLATED.value: set(),
}


async def get_commitment(
    session: AsyncSession, *, commitment_id: int
) -> LaborCommitment:
    row = await session.get(LaborCommitment, commitment_id)
    if row is None:
        raise NotFoundError(f"表明が見つかりません（id={commitment_id}）")
    return row


async def list_commitments(
    session: AsyncSession,
    *,
    contract_id: int | None = None,
    status: str | None = None,
    commitment_type: str | None = None,
    page: int = 1,
    size: int = 50,
) -> tuple[list[LaborCommitment], int]:
    stmt = select(LaborCommitment)
    if contract_id is not None:
        stmt = stmt.where(LaborCommitment.contract_id == contract_id)
    if status is not None:
        try:
            stmt = stmt.where(
                LaborCommitment.status == LaborCommitmentStatus(status).value
            )
        except ValueError as exc:
            raise ValidationError(f"不正な状態: {status!r}") from exc
    if commitment_type is not None:
        stmt = stmt.where(LaborCommitment.commitment_type == commitment_type)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(LaborCommitment.id.desc()).offset((page - 1) * size).limit(size)
    return list((await session.execute(stmt)).scalars().all()), int(total)


async def create_commitment(
    session: AsyncSession,
    *,
    actor_id: int | None,
    contract_id: int,
    commitment_type: str,
    title: str,
    statement: str | None = None,
    confirmed_at: date | None = None,
) -> LaborCommitment:
    """#28 表明を登録する（active）."""
    if await session.get(Contract, contract_id) is None:
        raise NotFoundError(f"契約が見つかりません（id={contract_id}）")
    try:
        ctype_value = LaborCommitmentType(commitment_type).value
    except ValueError as exc:
        raise ValidationError(f"不正な表明種別: {commitment_type!r}") from exc

    row = LaborCommitment(
        contract_id=contract_id,
        commitment_type=ctype_value,
        status=LaborCommitmentStatus.ACTIVE.value,
        title=title,
        statement=statement,
        confirmed_at=confirmed_at or date.today(),
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def verify_commitment(
    session: AsyncSession,
    *,
    commitment_id: int,
    actor_id: int | None,
    outcome: str,
    verify_note: str | None = None,
) -> LaborCommitment:
    """#28 表明の履行確認（fulfilled）/違反確認（violated）へ遷移する（active のみ）."""
    row = await get_commitment(session, commitment_id=commitment_id)
    try:
        outcome_value = LaborCommitmentStatus(outcome).value
    except ValueError as exc:
        raise ValidationError(f"不正な確認結果: {outcome!r}") from exc
    if outcome_value not in (
        LaborCommitmentStatus.FULFILLED.value,
        LaborCommitmentStatus.VIOLATED.value,
    ):
        raise ValidationError("確認結果は fulfilled / violated のみです。")
    if outcome_value not in _VERIFIABLE.get(row.status, set()):
        raise ConflictError("確認できるのは active（表明中）のみです。")
    row.status = outcome_value
    row.verified_at = datetime.now(UTC)
    row.verified_by = actor_id
    row.verify_note = verify_note
    row.updated_by = actor_id
    await session.flush()
    await session.refresh(row)
    return row


__all__ = ["create_commitment", "get_commitment", "list_commitments", "verify_commitment"]
