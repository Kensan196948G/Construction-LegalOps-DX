"""紛争・事故・債権管理（案件台帳・タイムライン・証拠保全）."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
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
    from .dispute_ext import (
        DisputeArgumentPosition,
        DisputeDelayEvent,
        DisputeProceedingStage,
        DisputeSettlementOption,
    )
    from .user import User


class Dispute(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """紛争・クレーム案件台帳。"""

    __tablename__ = "disputes"

    dispute_no: Mapped[str] = mapped_column(String(32), nullable=False)
    contract_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("contracts.id", ondelete="SET NULL"),
        nullable=True,
    )
    dispute_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="open", server_default="'open'"
    )
    priority: Mapped[str] = mapped_column(
        String(4), nullable=False, default="中", server_default="'中'"
    )
    counterparty: Mapped[str | None] = mapped_column(String(256), nullable=True)
    amount_claimed_jpy: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reserve_amount_jpy: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    assignee_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    statute_limitations_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notice_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    resolution_method: Mapped[str] = mapped_column(
        String(32), nullable=False, default="negotiation", server_default="'negotiation'"
    )
    legal_hold_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("legal_holds.id", ondelete="SET NULL"),
        nullable=True,
    )
    exposure: Mapped[dict[str, object]] = mapped_column(
        JsonType, nullable=False, default=dict, server_default="'{}'::jsonb"
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    contract: Mapped[Contract | None] = relationship("Contract")
    assignee: Mapped[User | None] = relationship("User", foreign_keys=[assignee_id])
    timeline: Mapped[list[DisputeTimelineEvent]] = relationship(
        "DisputeTimelineEvent",
        back_populates="dispute",
        cascade="all, delete-orphan",
    )
    evidence: Mapped[list[DisputeEvidence]] = relationship(
        "DisputeEvidence",
        back_populates="dispute",
        cascade="all, delete-orphan",
    )
    # ロードマップ #97〜#112（紛争・クレーム管理高度化）の拡張リレーション。
    # 実体は app.models.dispute_ext に定義する（循環 import 回避のため文字列参照）。
    delay_events: Mapped[list[DisputeDelayEvent]] = relationship(
        "DisputeDelayEvent",
        back_populates="dispute",
        cascade="all, delete-orphan",
        order_by="DisputeDelayEvent.occurred_from",
    )
    argument_positions: Mapped[list[DisputeArgumentPosition]] = relationship(
        "DisputeArgumentPosition",
        back_populates="dispute",
        cascade="all, delete-orphan",
    )
    settlement_options: Mapped[list[DisputeSettlementOption]] = relationship(
        "DisputeSettlementOption",
        back_populates="dispute",
        cascade="all, delete-orphan",
    )
    proceeding_stages: Mapped[list[DisputeProceedingStage]] = relationship(
        "DisputeProceedingStage",
        back_populates="dispute",
        cascade="all, delete-orphan",
        order_by="DisputeProceedingStage.started_at",
    )

    __table_args__ = (
        UniqueConstraint("dispute_no", name="uq_disputes_no"),
        CheckConstraint(
            "dispute_type IN ('claim', 'defect', 'delay', 'payment', 'labor', 'accident', 'other')",
            name="ck_disputes_type",
        ),
        CheckConstraint(
            "status IN ('open', 'investigating', 'escalated', 'resolved', 'closed')",
            name="ck_disputes_status",
        ),
        CheckConstraint("priority IN ('高', '中', '低')", name="ck_disputes_priority"),
        CheckConstraint(
            "resolution_method IN ('negotiation', 'mediation', 'arbitration', 'lawsuit', "
            "'construction_dispute_review', 'other')",
            name="ck_disputes_resolution",
        ),
        Index("ix_disputes_status", "status"),
        Index("ix_disputes_contract", "contract_id"),
        Index("ix_disputes_deadlines", "statute_limitations_date", "notice_deadline"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Dispute id={self.id} no={self.dispute_no!r} status={self.status!r}>"


class DisputeTimelineEvent(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """紛争の事実経過・通知・聴聞・証拠等のタイムライン。"""

    __tablename__ = "dispute_timeline_events"

    dispute_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("disputes.id", ondelete="CASCADE"),
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    dispute: Mapped[Dispute] = relationship("Dispute", back_populates="timeline")

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('fact', 'notice', 'hearing', 'evidence', 'settlement', "
            "'escalation', 'other')",
            name="ck_dispute_timeline_type",
        ),
        Index("ix_dispute_timeline_dispute", "dispute_id", "occurred_at"),
    )


class DisputeEvidence(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """紛争証拠（保全フラグ付き）。"""

    __tablename__ = "dispute_evidence"

    dispute_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("disputes.id", ondelete="CASCADE"),
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
    preserved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    dispute: Mapped[Dispute] = relationship("Dispute", back_populates="evidence")
    attachment: Mapped[Attachment | None] = relationship("Attachment")

    __table_args__ = (
        CheckConstraint(
            "evidence_type IN ('contract', 'email', 'photo', 'daily_report', 'minutes', 'other')",
            name="ck_dispute_evidence_type",
        ),
        Index("ix_dispute_evidence_dispute", "dispute_id"),
    )


__all__ = ["Dispute", "DisputeEvidence", "DisputeTimelineEvent"]
