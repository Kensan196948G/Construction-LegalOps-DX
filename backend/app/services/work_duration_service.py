"""標準工期マスタと短工期判定の業務サービス（ロードマップ #22）.

- #22 短工期判定: 工種 × 請負金額帯 × 適用期間の標準工期を解決し、実工期との
  短縮率から none / watch / warning / critical を決定論的に導出する（AI 不使用）。
  基準値は更新型で蓄積する（労務費基準 #16 と同方針・削除せず履歴化）。
"""

from __future__ import annotations

from datetime import date

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.standard_duration import StandardWorkDuration

logger = structlog.get_logger(__name__)

# 短工期判定の深刻度しきい値（短縮率・決定論的）
_WARNING_MIN_SHORTEN = 0.10  # 標準より 10% 以上短い = warning（要確認）
_CRITICAL_MIN_SHORTEN = 0.20  # 標準より 20% 以上短い = critical（無理な工期）


def _derive_severity(status: str, shorten_rate: float) -> str:
    """短縮率から深刻度を決定論的に導出する（#22）."""
    if status == "ok":
        return "none"
    if shorten_rate >= _CRITICAL_MIN_SHORTEN:
        return "critical"
    if shorten_rate >= _WARNING_MIN_SHORTEN:
        return "warning"
    if shorten_rate > 0:
        return "watch"
    return "none"


async def upsert_duration(
    session: AsyncSession,
    *,
    actor_id: int | None,
    work_type: str,
    amount_min_jpy: int,
    standard_days: int,
    prefecture: str | None = None,
    amount_max_jpy: int | None = None,
    effective_from: date,
    effective_to: date | None = None,
    source_ref: str | None = None,
) -> StandardWorkDuration:
    """標準工期 1 行を追加する（既存期間と重複しても履歴として蓄積）."""
    if amount_min_jpy < 0:
        raise ValidationError("請負金額の下限は 0 以上です。")
    if amount_max_jpy is not None and amount_max_jpy < amount_min_jpy:
        raise ValidationError("請負金額の上限は下限以上としてください。")
    if standard_days <= 0:
        raise ValidationError("標準工期は 1 日以上としてください。")
    if effective_to is not None and effective_to < effective_from:
        raise ValidationError("effective_to は effective_from 以上としてください。")

    row = StandardWorkDuration(
        work_type=work_type,
        prefecture=prefecture,
        amount_min_jpy=amount_min_jpy,
        amount_max_jpy=amount_max_jpy,
        standard_days=standard_days,
        effective_from=effective_from,
        effective_to=effective_to,
        source_ref=source_ref,
        created_by=actor_id,
        updated_by=actor_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def list_durations(
    session: AsyncSession,
    *,
    work_type: str | None = None,
    prefecture: str | None = None,
    as_of: date | None = None,
    page: int = 1,
    size: int = 50,
) -> tuple[list[StandardWorkDuration], int]:
    """標準工期マスタ一覧（工種・都道府県・as-of 絞り込み）."""
    stmt = select(StandardWorkDuration)
    if work_type is not None:
        stmt = stmt.where(StandardWorkDuration.work_type == work_type)
    if prefecture is not None:
        stmt = stmt.where(StandardWorkDuration.prefecture == prefecture)
    if as_of is not None:
        stmt = stmt.where(
            StandardWorkDuration.effective_from <= as_of,
            (StandardWorkDuration.effective_to.is_(None))
            | (StandardWorkDuration.effective_to >= as_of),
        )
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = (
        stmt.order_by(
            StandardWorkDuration.work_type,
            StandardWorkDuration.prefecture.asc(),
            StandardWorkDuration.amount_min_jpy,
            StandardWorkDuration.effective_from.desc(),
        )
        .offset((page - 1) * size)
        .limit(size)
    )
    return list((await session.execute(stmt)).scalars().all()), int(total)


async def resolve_standard_duration(
    session: AsyncSession,
    *,
    work_type: str,
    amount_jpy: int,
    prefecture: str | None = None,
    as_of: date | None = None,
) -> StandardWorkDuration:
    """as-of 日時点の標準工期を解決する.

    都道府県指定があれば当該県の帯を優先し、無ければ全国（prefecture NULL）の帯へ
    フォールバックする。金額帯は min <= amount <= max（max NULL = 上限なし）。
    """
    if amount_jpy < 0:
        raise ValidationError("請負金額は 0 以上です。")
    as_of_date = as_of or date.today()
    period = (
        StandardWorkDuration.effective_from <= as_of_date,
        (StandardWorkDuration.effective_to.is_(None))
        | (StandardWorkDuration.effective_to >= as_of_date),
    )
    band = (
        StandardWorkDuration.amount_min_jpy <= amount_jpy,
        (StandardWorkDuration.amount_max_jpy.is_(None))
        | (StandardWorkDuration.amount_max_jpy >= amount_jpy),
    )
    for pref in ([prefecture, None] if prefecture is not None else [None]):
        stmt = (
            select(StandardWorkDuration)
            .where(
                StandardWorkDuration.work_type == work_type,
                *period,
                *band,
            )
            .where(
                StandardWorkDuration.prefecture.is_(None)
                if pref is None
                else StandardWorkDuration.prefecture == pref
            )
            .order_by(StandardWorkDuration.effective_from.desc())
            .limit(1)
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is not None:
            return row
    raise NotFoundError(
        f"該当する標準工期がありません（work_type={work_type}, amount={amount_jpy}, "
        f"prefecture={prefecture}, as_of={as_of_date.isoformat()}）"
    )


async def short_duration_check(
    session: AsyncSession,
    *,
    work_type: str,
    amount_jpy: int,
    planned_days: int,
    prefecture: str | None = None,
    as_of: date | None = None,
) -> dict[str, object]:
    """#22 短工期判定: 実工期と標準工期の短縮率から深刻度を導出する."""
    if planned_days <= 0:
        raise ValidationError("実工期は 1 日以上としてください。")
    standard = await resolve_standard_duration(
        session,
        work_type=work_type,
        amount_jpy=amount_jpy,
        prefecture=prefecture,
        as_of=as_of,
    )
    ratio = planned_days / standard.standard_days
    shorten_rate = max(0.0, 1.0 - ratio)
    status = "ok" if planned_days >= standard.standard_days else "short"
    severity = _derive_severity(status, shorten_rate)
    return {
        "work_type": standard.work_type,
        "prefecture": standard.prefecture,
        "amount_min_jpy": standard.amount_min_jpy,
        "amount_max_jpy": standard.amount_max_jpy,
        "standard_days": standard.standard_days,
        "planned_days": planned_days,
        "ratio": round(ratio, 4),
        "shorten_rate": round(shorten_rate, 4),
        "status": status,
        "severity": severity,
        "effective_from": standard.effective_from,
        "source_ref": standard.source_ref,
    }


__all__ = [
    "list_durations",
    "resolve_standard_duration",
    "short_duration_check",
    "upsert_duration",
]
