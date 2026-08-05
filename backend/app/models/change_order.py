"""変更契約・追加工事・クレーム（設計変更指示 / 工期延長 / スライド請求等）."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JsonType

from ._mixins import AuditedByMixin, IntPKMixin, TimestampMixin

if TYPE_CHECKING:
    from .attachment import Attachment
    from .contract import Contract


class ChangeOrder(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """原契約に対する変更・追加・クレームの一件記録。"""

    __tablename__ = "change_orders"

    contract_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("contracts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    change_no: Mapped[str] = mapped_column(String(32), nullable=False)
    change_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    requested_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    # 通知期限（自動計算 + 手動上書き）
    response_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="registered", server_default="'registered'"
    )
    amount_jpy: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    schedule_impact_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    forfeiture_warning: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_summary: Mapped[dict[str, object]] = mapped_column(
        JsonType, nullable=False, default=dict, server_default="'{}'::jsonb"
    )
    original_amount_jpy: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cumulative_after_jpy: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    contract: Mapped[Contract] = relationship("Contract", back_populates="change_orders")
    evidence: Mapped[list[ChangeOrderEvidence]] = relationship(
        "ChangeOrderEvidence",
        back_populates="change_order",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("contract_id", "change_no", name="uq_change_orders_no"),
        CheckConstraint(
            "change_type IN ('design_change', 'additional_work', 'verbal_direction', "
            "'schedule_extension', 'price_slide', 'claim', 'other')",
            name="ck_change_orders_type",
        ),
        CheckConstraint(
            "status IN ('registered', 'notice_sent', 'in_consultation', 'approved', "
            "'rejected', 'forfeited')",
            name="ck_change_orders_status",
        ),
        Index("ix_change_orders_contract", "contract_id"),
        Index("ix_change_orders_status", "status"),
        Index("ix_change_orders_deadline", "response_deadline"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ChangeOrder id={self.id} no={self.change_no!r} status={self.status!r}>"


class ChangeOrderEvidence(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """変更・クレームの証拠（日報・写真・メール・議事録・指示書）."""

    __tablename__ = "change_order_evidence"

    change_order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("change_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    evidence_type: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    attachment_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("attachments.id", ondelete="SET NULL"),
        nullable=True,
    )

    change_order: Mapped[ChangeOrder] = relationship(
        "ChangeOrder", back_populates="evidence"
    )
    attachment: Mapped[Attachment | None] = relationship("Attachment")

    __table_args__ = (
        CheckConstraint(
            "evidence_type IN ('daily_report', 'photo', 'email', 'minutes', "
            "'instruction', 'other')",
            name="ck_change_order_evidence_type",
        ),
        Index("ix_change_order_evidence_order", "change_order_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ChangeOrderEvidence id={self.id} type={self.evidence_type!r} "
            f"order_id={self.change_order_id}>"
        )


__all__ = ["ChangeOrder", "ChangeOrderEvidence"]
