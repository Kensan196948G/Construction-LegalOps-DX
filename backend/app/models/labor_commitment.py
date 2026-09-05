"""労務費コミットメント（表明）モデル.

ロードマップ #28（コミットメント条項管理・労務費・賃金関連の表明管理）/ Phase 2。

契約ごとに「賃金支払確約」「労務費の適正配分」「一括下請負の禁止遵守」等の
表明を記録し、履行確認（fulfilled）/違反確認（violated）へ状態遷移する。
2025-12 改正の標準請負契約約款で強化された労務費関連の表明・コミットメントを
契約単位で一元管理する。判定は ``app.services.labor_commitment_service``
のルールエンジンで行う（AI 不使用）。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from ._mixins import AuditedByMixin, IntPKMixin, TimestampMixin
from .enums import LaborCommitmentStatus, LaborCommitmentType

if TYPE_CHECKING:
    from .contract import Contract

_ALLOWED_TYPE = ",".join(f"'{t.value}'" for t in LaborCommitmentType)
_ALLOWED_STATUS = ",".join(f"'{s.value}'" for s in LaborCommitmentStatus)


class LaborCommitment(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """契約 1 件に紐づく労務費関連の表明（#28）."""

    __tablename__ = "labor_commitments"

    contract_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
    )
    commitment_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=LaborCommitmentStatus.ACTIVE.value
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    statement: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    # 履行確認・違反確認の記録
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verified_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    verify_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    contract: Mapped[Contract] = relationship("Contract")

    __table_args__ = (
        CheckConstraint(f"commitment_type IN ({_ALLOWED_TYPE})", name="ck_labor_commitments_type"),
        CheckConstraint(f"status IN ({_ALLOWED_STATUS})", name="ck_labor_commitments_status"),
        Index("ix_labor_commitments_contract", "contract_id"),
        Index("ix_labor_commitments_status", "status"),
        Index("ix_labor_commitments_type", "commitment_type"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<LaborCommitment id={self.id} contract={self.contract_id} "
            f"type={self.commitment_type!r} status={self.status!r}>"
        )


__all__ = ["LaborCommitment"]
