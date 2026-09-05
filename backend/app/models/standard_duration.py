"""標準工期マスタ（短工期判定用）モデル.

ロードマップ #22（短工期判定・標準的工期との差を警告）/ Phase 2。

* ``standard_work_durations`` … 工種 × 請負金額帯 × 適用期間ごとの標準工期（日数）。
  国交省の標準工期設定要領等の基準値を**更新型**で蓄積する（労務費基準 #16 と同方針）。
  判定は ``app.services.work_duration_service`` のルールエンジンが決定論的に行う
  （AI 不使用）: 実工期が標準工期を下回る割合（短縮率）から
  none / watch / warning / critical を導出する。
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import (
    CheckConstraint,
    Date,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

from ._mixins import AuditedByMixin, IntPKMixin, TimestampMixin


class StandardWorkDuration(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """標準工期 1 行（工種 × 請負金額帯 × 適用期間）."""

    __tablename__ = "standard_work_durations"

    work_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # None = 全国一律（都道府県別基準なし向け）
    prefecture: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # 請負金額帯（min <= amount <= max・max NULL は上限なし）
    amount_min_jpy: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_max_jpy: Mapped[int | None] = mapped_column(Integer, nullable=True)
    standard_days: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "amount_min_jpy >= 0",
            name="ck_standard_durations_amount_min",
        ),
        CheckConstraint(
            "amount_max_jpy IS NULL OR amount_max_jpy >= amount_min_jpy",
            name="ck_standard_durations_amount_max",
        ),
        CheckConstraint(
            "standard_days > 0",
            name="ck_standard_durations_days",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_standard_durations_period",
        ),
        Index("ix_standard_durations_work_type", "work_type"),
        Index("ix_standard_durations_pref", "prefecture"),
        Index(
            "ix_standard_durations_effective",
            "effective_from",
            "effective_to",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<StandardWorkDuration id={self.id} type={self.work_type!r} "
            f"days={self.standard_days}>"
        )


__all__ = ["StandardWorkDuration"]
