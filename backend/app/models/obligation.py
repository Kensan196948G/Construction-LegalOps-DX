"""契約義務（Obligations）モデル.

ロードマップ #9（契約義務管理）・#10（Obligations Calendar）・#11（条件成就）・
#13（契約終了チェック）の永続化。期限の「今日基準」の状態（overdue /
30 日以内 / 60 日以内）は保存せず、``app.services.obligation_service`` の
ルールエンジンが動的に算出する（#12 自動更新判定は contracts の
``auto_renewal`` 列 + ``renewal_notice_days`` から導出）。
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
from .enums import ObligationStatus, ObligationType

if TYPE_CHECKING:
    from .contract import Contract
    from .user import User


_ALLOWED_TYPE = ",".join(f"'{t.value}'" for t in ObligationType)
_ALLOWED_STATUS = ",".join(f"'{s.value}'" for s in ObligationStatus)


class ContractObligation(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """契約 1 件に紐づく履行義務（報告・通知・提出・保険・更新・条件等）."""

    __tablename__ = "contract_obligations"

    contract_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
    )
    obligation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ObligationStatus.OPEN.value
    )
    assignee_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    contract: Mapped[Contract] = relationship("Contract")
    assignee: Mapped[User | None] = relationship("User", foreign_keys=[assignee_id])

    __table_args__ = (
        CheckConstraint(
            f"obligation_type IN ({_ALLOWED_TYPE})",
            name="ck_contract_obligations_type",
        ),
        CheckConstraint(
            f"status IN ({_ALLOWED_STATUS})",
            name="ck_contract_obligations_status",
        ),
        Index("ix_obligations_contract", "contract_id"),
        Index("ix_obligations_due_date", "due_date"),
        Index("ix_obligations_status", "status"),
        Index("ix_obligations_type", "obligation_type"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<ContractObligation id={self.id} contract_id={self.contract_id} "
            f"type={self.obligation_type!r} status={self.status!r}>"
        )


__all__ = ["ContractObligation"]
