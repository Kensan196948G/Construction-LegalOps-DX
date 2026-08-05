"""契約文書パッケージの整合性チェック結果（金額・工期・日付の矛盾検出）."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JsonType

from ._mixins import IntPKMixin, TimestampMixin

if TYPE_CHECKING:
    from .contract import Contract
    from .user import User


class DocumentConsistencyResult(IntPKMixin, TimestampMixin, Base):
    """1 契約パッケージ全体の整合チェック結果の保存。"""

    __tablename__ = "document_consistency_results"

    contract_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="needs_review", server_default="'needs_review'"
    )
    findings: Mapped[list[dict[str, Any]]] = mapped_column(
        JsonType, nullable=False, default=list, server_default="'[]'::jsonb"
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    checked_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )

    contract: Mapped[Contract] = relationship("Contract")
    checker: Mapped[User | None] = relationship("User", foreign_keys=[checked_by])

    __table_args__ = (
        CheckConstraint(
            "status IN ('consistent', 'inconsistent', 'needs_review')",
            name="ck_consistency_status",
        ),
        Index("ix_consistency_contract", "contract_id", "checked_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<DocumentConsistencyResult id={self.id} contract_id={self.contract_id} "
            f"status={self.status!r}>"
        )


__all__ = ["DocumentConsistencyResult"]
