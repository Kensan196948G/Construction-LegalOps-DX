"""紛争・クレーム管理高度化（ロードマップ #97〜#112）モデル.

Issue #121 / Phase 3 §5.8。既存 ``Dispute`` 台帳を拡張し、以下を管理する。

* ``dispute_delay_events``      … 遅延事象台帳（#100）。原因分類（#101）・
  追加費用積上げ（#102）・損害額（#103）・EOT／工期延長判定（#104）を含む。
* ``dispute_argument_positions`` … 主張・反論マトリクス（#109）。
* ``dispute_settlement_options`` … 和解案比較（#110）。
* ``dispute_proceeding_stages``  … 訴訟・ADR ステージ管理（#111）。

Claim Notice Generator（#97）・通知期限自動判定（#98）・Time Bar 警告／消滅時効
タイマー（#99・#112）・証拠充足度スコア／AI 証拠不足検知（#105・#106）・
Claim Chronology 自動生成（#107・#108）は新規テーブルを持たず、
``app.services.dispute_ext_service`` が既存データ（``Dispute`` /
``DisputeTimelineEvent`` / ``DisputeEvidence`` / 本ファイルの遅延事象）を
決定論的なルールエンジンで集計・生成する（AI 不使用・最終法的判断は行わない）。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JsonType

from ._mixins import AuditedByMixin, IntPKMixin, TimestampMixin
from .enums import (
    DisputeArgumentParty,
    DisputeArgumentStance,
    DisputeDelayCauseCategory,
    DisputeEotStatus,
    DisputeProceedingStageStatus,
    DisputeProceedingStageType,
    DisputeSettlementStatus,
)

if TYPE_CHECKING:
    from .dispute import Dispute
    from .user import User

_ALLOWED_CAUSE = ",".join(f"'{c.value}'" for c in DisputeDelayCauseCategory)
_ALLOWED_EOT_STATUS = ",".join(f"'{s.value}'" for s in DisputeEotStatus)
_ALLOWED_ARG_PARTY = ",".join(f"'{p.value}'" for p in DisputeArgumentParty)
_ALLOWED_ARG_STANCE = ",".join(f"'{s.value}'" for s in DisputeArgumentStance)
_ALLOWED_SETTLEMENT_STATUS = ",".join(f"'{s.value}'" for s in DisputeSettlementStatus)
_ALLOWED_STAGE_TYPE = ",".join(f"'{t.value}'" for t in DisputeProceedingStageType)
_ALLOWED_STAGE_STATUS = ",".join(f"'{s.value}'" for s in DisputeProceedingStageStatus)


class DisputeDelayEvent(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """遅延事象台帳（#100）。原因分類・追加費用・損害額・EOT 判定を含む。"""

    __tablename__ = "dispute_delay_events"

    dispute_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("disputes.id", ondelete="CASCADE"),
        nullable=False,
    )
    cause_category: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_from: Mapped[date] = mapped_column(Date, nullable=False)
    occurred_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    delay_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    responsible_party: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # #102 追加費用積上げ
    additional_cost_jpy: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # #103 損害額計算（決定論的算定。積上げ値の上書きも許容する）
    damage_amount_jpy: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # #104 EOT／工期延長管理
    eot_days_requested: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eot_days_granted: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eot_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=DisputeEotStatus.PENDING.value
    )
    eot_decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    eot_decided_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    eot_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    dispute: Mapped[Dispute] = relationship("Dispute", back_populates="delay_events")
    eot_decided_by_user: Mapped[User | None] = relationship("User", foreign_keys=[eot_decided_by])

    __table_args__ = (
        CheckConstraint(f"cause_category IN ({_ALLOWED_CAUSE})", name="ck_dispute_delay_cause"),
        CheckConstraint(
            f"eot_status IN ({_ALLOWED_EOT_STATUS})", name="ck_dispute_delay_eot_status"
        ),
        CheckConstraint("delay_days >= 0", name="ck_dispute_delay_days_nonneg"),
        Index("ix_dispute_delay_events_dispute", "dispute_id"),
        Index("ix_dispute_delay_events_cause", "cause_category"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<DisputeDelayEvent id={self.id} dispute={self.dispute_id} "
            f"cause={self.cause_category!r} days={self.delay_days}>"
        )


class DisputeArgumentPosition(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """主張・反論マトリクス（#109）。争点ごとに当事者・立場・内容を記録する。"""

    __tablename__ = "dispute_argument_positions"

    dispute_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("disputes.id", ondelete="CASCADE"),
        nullable=False,
    )
    issue_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    issue_title: Mapped[str] = mapped_column(String(256), nullable=False)
    party: Mapped[str] = mapped_column(String(16), nullable=False)
    stance: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_refs: Mapped[list[int]] = mapped_column(JsonType, nullable=False, default=list)

    dispute: Mapped[Dispute] = relationship("Dispute", back_populates="argument_positions")

    __table_args__ = (
        CheckConstraint(f"party IN ({_ALLOWED_ARG_PARTY})", name="ck_dispute_argument_party"),
        CheckConstraint(f"stance IN ({_ALLOWED_ARG_STANCE})", name="ck_dispute_argument_stance"),
        Index("ix_dispute_argument_positions_dispute", "dispute_id", "issue_no"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<DisputeArgumentPosition id={self.id} dispute={self.dispute_id} "
            f"issue={self.issue_no} party={self.party!r}>"
        )


class DisputeSettlementOption(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """和解案比較（#110）。案ごとの金額・確度スコアから期待値を算出する。"""

    __tablename__ = "dispute_settlement_options"

    dispute_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("disputes.id", ondelete="CASCADE"),
        nullable=False,
    )
    option_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    settlement_amount_jpy: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    pros: Mapped[str | None] = mapped_column(Text, nullable=True)
    cons: Mapped[str | None] = mapped_column(Text, nullable=True)
    probability_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_value_jpy: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=DisputeSettlementStatus.DRAFT.value
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    dispute: Mapped[Dispute] = relationship("Dispute", back_populates="settlement_options")

    __table_args__ = (
        CheckConstraint(
            f"status IN ({_ALLOWED_SETTLEMENT_STATUS})", name="ck_dispute_settlement_status"
        ),
        CheckConstraint(
            "probability_score IS NULL OR (probability_score >= 0 AND probability_score <= 100)",
            name="ck_dispute_settlement_probability",
        ),
        Index("ix_dispute_settlement_options_dispute", "dispute_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<DisputeSettlementOption id={self.id} dispute={self.dispute_id} "
            f"status={self.status!r}>"
        )


class DisputeProceedingStage(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """訴訟・ADR ステージ管理（#111）。交渉〜確定判決/和解成立の履歴を記録する。"""

    __tablename__ = "dispute_proceeding_stages"

    dispute_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("disputes.id", ondelete="CASCADE"),
        nullable=False,
    )
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=DisputeProceedingStageStatus.ACTIVE.value
    )
    started_at: Mapped[date] = mapped_column(Date, nullable=False)
    ended_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    forum: Mapped[str | None] = mapped_column(String(256), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_data: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False, default=dict)

    dispute: Mapped[Dispute] = relationship("Dispute", back_populates="proceeding_stages")

    __table_args__ = (
        CheckConstraint(f"stage IN ({_ALLOWED_STAGE_TYPE})", name="ck_dispute_stage_type"),
        CheckConstraint(f"status IN ({_ALLOWED_STAGE_STATUS})", name="ck_dispute_stage_status"),
        Index("ix_dispute_proceeding_stages_dispute", "dispute_id", "started_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<DisputeProceedingStage id={self.id} dispute={self.dispute_id} "
            f"stage={self.stage!r} status={self.status!r}>"
        )


__all__ = [
    "DisputeArgumentPosition",
    "DisputeDelayEvent",
    "DisputeProceedingStage",
    "DisputeSettlementOption",
]
