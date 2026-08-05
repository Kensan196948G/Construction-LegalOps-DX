"""リーガルホールド（証拠保全）モデル.

P0-6 対応: Legal Hold 中の契約・レビューは自動削除/保持期限パージ対象から除外する。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from ._mixins import IntPKMixin, TimestampMixin

if TYPE_CHECKING:
    from .contract import Contract
    from .user import User


class LegalHoldCase(IntPKMixin, TimestampMixin, Base):
    """契約に対するリーガルホールド.

    ``ended_at`` が NULL の間はアクティブ。同一契約に複数ホールドを
    重ねられるが、アクティブ判定は「ended_at IS NULL が 1 件以上」。
    """

    __tablename__ = "legal_hold_cases"

    contract_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("contracts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    contract: Mapped[Contract] = relationship("Contract")
    requester: Mapped[User | None] = relationship("User")

    __table_args__ = (
        Index("ix_legal_hold_cases_contract", "contract_id"),
        Index("ix_legal_hold_cases_active", "ended_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<LegalHoldCase id={self.id} contract_id={self.contract_id}>"
