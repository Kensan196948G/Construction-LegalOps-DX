"""労務費価格協議・乖離確認の業務サービス（ロードマップ #21/#23/#24）.

- #24 価格協議履歴: 申出（open）→ 回答（responded）／取下げ（cancelled）を証跡化。
  記録時点で「基準日 as-of の最新値」を解決し、乖離率（ratio）・不足率
  （shortage_rate）・深刻度（severity）を決定論的に算出・保存する（AI 不使用）。
- #21 ダンピング警告: 判定は ``labor_wage_service.discrepancy`` に集約（重複しない）。
- #23 見積変更要求監視: 未回答（open）の協議を一覧化し、warning 以上の深刻度を
  フィルタ可能にする。
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.enums import ConsultationDirection, ConsultationStatus
from app.models.price_consultation import PriceConsultationLog
from app.services import labor_wage_service

logger = structlog.get_logger(__name__)


async def _resolve_snapshot(
    session: AsyncSession,
    *,
    work_type: str,
    prefecture: str | None,
    quote_day_jpy: int | None,
) -> dict[str, object]:
    """記録時点の基準値スナップショットを解決する（基準未登録時は None 許容）."""
    if quote_day_jpy is None:
        return {
            "standard_day_jpy": None,
            "effective_from": None,
            "source_ref": None,
            "ratio": None,
            "shortage_rate": None,
            "severity": None,
        }
    try:
        result = await labor_wage_service.discrepancy(
            session, work_type=work_type, prefecture=prefecture, quote_day_jpy=quote_day_jpy
        )
    except NotFoundError:
        # 基準未登録の工種はスナップショット無しで記録する（後から基準追加可能）
        return {
            "standard_day_jpy": None,
            "effective_from": None,
            "source_ref": None,
            "ratio": None,
            "shortage_rate": None,
            "severity": None,
        }
    return {
        "standard_day_jpy": result["standard_day_jpy"],
        "effective_from": result["effective_from"],
        "source_ref": result["source_ref"],
        "ratio": result["ratio"],
        "shortage_rate": result["shortage_rate"],
        "severity": result["severity"],
    }


async def _build_log_no(session: AsyncSession) -> str:
    """協議ログ番号の採番: LC-YYYY-NNNNNN（Matter 採番と同方針・flush 後確定）."""
    year = datetime.now(UTC).strftime("%Y")
    prefix = f"LC-{year}-"
    last = (
        await session.execute(
            select(PriceConsultationLog.log_no)
            .where(PriceConsultationLog.log_no.like(f"{prefix}%"))
            .order_by(PriceConsultationLog.id.desc())
            .limit(1)
        )
    ).scalars().first()
    next_seq = int(last.split("-")[-1]) + 1 if last else 1
    return f"{prefix}{next_seq:06d}"


async def create_log(
    session: AsyncSession,
    *,
    actor_id: int | None,
    direction: str,
    work_type: str,
    summary: str,
    contract_id: int | None = None,
    prefecture: str | None = None,
    quote_day_jpy: int | None = None,
    request_detail: str | None = None,
    requested_at: date | None = None,
) -> PriceConsultationLog:
    """#24 価格協議の申出を記録する（open・乖離スナップショット付き）."""
    try:
        direction_value = ConsultationDirection(direction).value
    except ValueError as exc:
        raise ValidationError(f"不正な協議方向: {direction!r}") from exc
    if quote_day_jpy is not None and quote_day_jpy < 0:
        raise ValidationError("協議対象単価は 0 以上です。")

    snapshot = await _resolve_snapshot(
        session,
        work_type=work_type,
        prefecture=prefecture,
        quote_day_jpy=quote_day_jpy,
    )
    row = PriceConsultationLog(
        log_no="",  # flush 後に採番（LC-YYYY-NNNNNN）
        direction=direction_value,
        status=ConsultationStatus.OPEN.value,
        contract_id=contract_id,
        work_type=work_type,
        prefecture=prefecture,
        quote_day_jpy=quote_day_jpy,
        summary=summary,
        request_detail=request_detail,
        requested_at=requested_at or date.today(),
        standard_day_jpy=snapshot["standard_day_jpy"],
        ratio=snapshot["ratio"],
        shortage_rate=snapshot["shortage_rate"],
        severity=snapshot["severity"],
        effective_from=snapshot["effective_from"],
        source_ref=snapshot["source_ref"],
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    row.log_no = await _build_log_no(session)
    await session.flush()
    await session.refresh(row)
    return row


async def list_logs(
    session: AsyncSession,
    *,
    status: str | None = None,
    direction: str | None = None,
    severity: str | None = None,
    contract_id: int | None = None,
    page: int = 1,
    size: int = 50,
) -> tuple[list[PriceConsultationLog], int]:
    """#24/#23 価格協議ログ一覧（状態・方向・深刻度・契約で絞り込み）."""
    stmt = select(PriceConsultationLog)
    if status is not None:
        try:
            stmt = stmt.where(
                PriceConsultationLog.status == ConsultationStatus(status).value
            )
        except ValueError as exc:
            raise ValidationError(f"不正な状態: {status!r}") from exc
    if direction is not None:
        stmt = stmt.where(PriceConsultationLog.direction == direction)
    if severity is not None:
        stmt = stmt.where(PriceConsultationLog.severity == severity)
    if contract_id is not None:
        stmt = stmt.where(PriceConsultationLog.contract_id == contract_id)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = (
        stmt.order_by(PriceConsultationLog.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    return list((await session.execute(stmt)).scalars().all()), int(total)


async def list_open_monitor(
    session: AsyncSession,
    *,
    severity: str | None = None,
    page: int = 1,
    size: int = 50,
) -> tuple[list[PriceConsultationLog], int]:
    """#23 見積変更要求監視: 未回答（open）の協議を一覧化する."""
    stmt = select(PriceConsultationLog).where(
        PriceConsultationLog.status == ConsultationStatus.OPEN.value
    )
    if severity is not None:
        stmt = stmt.where(PriceConsultationLog.severity == severity)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = (
        stmt.order_by(PriceConsultationLog.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    return list((await session.execute(stmt)).scalars().all()), int(total)


async def get_log(session: AsyncSession, *, log_id: int) -> PriceConsultationLog:
    row = await session.get(PriceConsultationLog, log_id)
    if row is None:
        raise NotFoundError(f"価格協議ログが見つかりません（id={log_id}）")
    return row


async def respond_log(
    session: AsyncSession,
    *,
    log_id: int,
    actor_id: int | None,
    response_summary: str,
) -> PriceConsultationLog:
    """#24 回答を記録して responded へ遷移する（open のみ）."""
    row = await get_log(session, log_id=log_id)
    if row.status != ConsultationStatus.OPEN.value:
        raise ConflictError("回答できるのは open（回答待ち）の協議のみです。")
    row.status = ConsultationStatus.RESPONDED.value
    row.response_summary = response_summary
    row.responded_at = datetime.now(UTC)
    row.responded_by = actor_id
    row.updated_by = actor_id
    await session.flush()
    await session.refresh(row)
    return row


async def cancel_log(
    session: AsyncSession,
    *,
    log_id: int,
    actor_id: int | None,
    reason: str,
) -> PriceConsultationLog:
    """#24 取下げ（open → cancelled）."""
    row = await get_log(session, log_id=log_id)
    if row.status != ConsultationStatus.OPEN.value:
        raise ConflictError("取消できるのは open（回答待ち）の協議のみです。")
    row.status = ConsultationStatus.CANCELLED.value
    row.cancel_reason = reason
    row.updated_by = actor_id
    await session.flush()
    await session.refresh(row)
    return row


__all__ = [
    "cancel_log",
    "create_log",
    "get_log",
    "list_logs",
    "list_open_monitor",
    "respond_log",
]
