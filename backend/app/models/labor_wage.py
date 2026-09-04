"""労務費基準マスタ（更新型 Compliance Engine）モデル.

ロードマップ #16〜#20 / Issue #111。国交省の労務費基準は更新が継続するため、
適用開始日（effective_from/to）を持つ行を蓄積し、「基準日時点の最新値」を
サービス層のルールエンジンで解決する（#16 データ更新・#17 工種別・#18 都道府県別）。

* ``amount_jpy`` … 基準単価（円）
* ``amount_unit`` … 単位（既定 ``日``。時間・月等の拡張を許容）
* ``effective_from`` / ``effective_to`` … 適用期間（to が NULL = 現行）
* ``source_ref`` … 出典（ポータル URL・通達番号等）
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    pass


class LaborWageStandard(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """労務費基準の基準単価 1 行（工種 × 都道府県 × 適用期間）."""

    __tablename__ = "labor_wage_standards"

    work_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # None = 全国一律（都道府県別基準なしの職種向け）
    prefecture: Mapped[str | None] = mapped_column(String(16), nullable=True)
    amount_jpy: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_unit: Mapped[str] = mapped_column(String(16), nullable=False, default="日")
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "amount_jpy >= 0",
            name="ck_labor_wage_standards_amount",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_labor_wage_standards_period",
        ),
        Index("ix_labor_wage_work_type", "work_type"),
        Index("ix_labor_wage_pref", "prefecture"),
        Index("ix_labor_wage_effective", "effective_from", "effective_to"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<LaborWageStandard id={self.id} type={self.work_type!r} "
            f"pref={self.prefecture!r} amount={self.amount_jpy}>"
        )


__all__ = ["LaborWageStandard"]
