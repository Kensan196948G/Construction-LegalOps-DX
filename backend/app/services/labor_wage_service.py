"""労務費基準マスタの業務サービス（ロードマップ #16〜#21 / Issue #111）.

- #16 データ更新: 基準値を有効期間付きで蓄積（削除せず更新）
- #17 工種別・#18 都道府県別: 一覧・絞り込み
- #20 労務費乖離率: 「基準日 as-of 時点の最新値」を解決し、見積単価との
  乖離率（基準を下回る場合の不足率）を決定論的に判定する（AI 不使用）
- #21 ダンピング警告: 乖離率から none / watch / warning / critical を導出
  （不足率 10% 以上 = warning・20% 以上 = critical・要ダンピング確認）
"""

from __future__ import annotations

from datetime import date
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.enums import LaborWorkType
from app.models.labor_wage import LaborWageStandard

logger = structlog.get_logger(__name__)

# #21 ダンピング警告の深刻度しきい値（不足率・決定論的）
_WATCH_MIN_SHORTAGE = 0.0  # 0% 超 = watch（基準未満は軽微でも注視）
_WARNING_MIN_SHORTAGE = 0.10  # 不足率 10% 以上 = warning（要確認）
_CRITICAL_MIN_SHORTAGE = 0.20  # 不足率 20% 以上 = critical（著しい低見積り）


def _derive_severity(status: str, shortage_rate: float) -> str:
    """乖離率からダンピング深刻度を決定論的に導出する（#21）."""
    if status == "ok":
        return "none"
    if shortage_rate >= _CRITICAL_MIN_SHORTAGE:
        return "critical"
    if shortage_rate >= _WARNING_MIN_SHORTAGE:
        return "warning"
    if shortage_rate > _WATCH_MIN_SHORTAGE:
        return "watch"
    return "none"


async def upsert_standard(
    session: AsyncSession,
    *,
    actor_id: int | None,
    work_type: str,
    amount_jpy: int,
    prefecture: str | None = None,
    effective_from: date,
    effective_to: date | None = None,
    amount_unit: str = "日",
    source_ref: str | None = None,
) -> LaborWageStandard:
    """基準値 1 行を追加する（既存期間と重複しても履歴として蓄積）."""
    try:
        work_type_value = LaborWorkType(work_type).value
    except ValueError as exc:
        raise ValidationError(f"不正な工種: {work_type!r}") from exc
    if amount_jpy < 0:
        raise ValidationError("基準単価は 0 以上です。")
    if effective_to is not None and effective_to < effective_from:
        raise ValidationError("effective_to は effective_from 以上としてください。")

    row = LaborWageStandard(
        work_type=work_type_value,
        prefecture=prefecture,
        amount_jpy=amount_jpy,
        amount_unit=amount_unit,
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


async def list_standards(
    session: AsyncSession,
    *,
    work_type: str | None = None,
    prefecture: str | None = None,
    as_of: date | None = None,
    page: int = 1,
    size: int = 50,
) -> tuple[list[LaborWageStandard], int]:
    stmt = select(LaborWageStandard)
    if work_type is not None:
        stmt = stmt.where(LaborWageStandard.work_type == LaborWorkType(work_type).value)
    if prefecture is not None:
        stmt = stmt.where(LaborWageStandard.prefecture == prefecture)
    if as_of is not None:
        stmt = stmt.where(
            LaborWageStandard.effective_from <= as_of,
            (LaborWageStandard.effective_to.is_(None)) | (LaborWageStandard.effective_to >= as_of),
        )
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = (
        stmt.order_by(
            LaborWageStandard.work_type,
            LaborWageStandard.prefecture.asc(),
            LaborWageStandard.effective_from.desc(),
        )
        .offset((page - 1) * size)
        .limit(size)
    )
    return list((await session.execute(stmt)).scalars().all()), int(total)


async def resolve_latest(
    session: AsyncSession,
    *,
    work_type: str,
    prefecture: str | None = None,
    as_of: date | None = None,
) -> LaborWageStandard:
    """基準日 as-of 時点の最新（適用開始日が最大）の基準値を返す."""
    try:
        work_type_value = LaborWorkType(work_type).value
    except ValueError as exc:
        raise ValidationError(f"不正な工種: {work_type!r}") from exc

    as_of_date = as_of or date.today()
    stmt = select(LaborWageStandard).where(
        LaborWageStandard.work_type == work_type_value,
        LaborWageStandard.effective_from <= as_of_date,
        (LaborWageStandard.effective_to.is_(None)) | (LaborWageStandard.effective_to >= as_of_date),
    )
    if prefecture is not None:
        stmt = stmt.where(LaborWageStandard.prefecture == prefecture)
    stmt = stmt.order_by(LaborWageStandard.effective_from.desc()).limit(1)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise NotFoundError(
            f"該当する労務費基準がありません（work_type={work_type_value}, "
            f"prefecture={prefecture}, as_of={as_of_date.isoformat()}）"
        )
    return row


def _validate_quote(quote_day_jpy: int) -> None:
    if quote_day_jpy < 0:
        raise ValidationError("見積単価は 0 以上です。")


async def discrepancy(
    session: AsyncSession,
    *,
    work_type: str,
    quote_day_jpy: int,
    prefecture: str | None = None,
    as_of: date | None = None,
) -> dict[str, Any]:
    """#20 労務費乖離率 + #21 ダンピング警告: 見積単価と基準値の乖離を判定する.

    返却: {work_type, prefecture, standard_day_jpy, quote_day_jpy,
    ratio, shortage_rate, status, severity, dumping}。
    status: ok（基準以上）/ below（基準を下回る・要ダンピング確認 #21 の入力）
    severity: none / watch / warning / critical（#21・不足率から導出）
    dumping: severity が warning 以上 = True（要ダンピング確認）
    """
    _validate_quote(quote_day_jpy)
    standard = await resolve_latest(
        session, work_type=work_type, prefecture=prefecture, as_of=as_of
    )
    ratio = quote_day_jpy / standard.amount_jpy
    shortage_rate = max(0.0, 1.0 - ratio)
    status = "ok" if quote_day_jpy >= standard.amount_jpy else "below"
    severity = _derive_severity(status, shortage_rate)
    return {
        "work_type": standard.work_type,
        "prefecture": standard.prefecture,
        "standard_day_jpy": standard.amount_jpy,
        "amount_unit": standard.amount_unit,
        "effective_from": standard.effective_from,
        "source_ref": standard.source_ref,
        "quote_day_jpy": quote_day_jpy,
        "ratio": round(ratio, 4),
        "shortage_rate": round(shortage_rate, 4),
        "status": status,
        "severity": severity,
        "dumping": severity in ("warning", "critical"),
    }


__all__ = ["discrepancy", "list_standards", "resolve_latest", "upsert_standard"]
