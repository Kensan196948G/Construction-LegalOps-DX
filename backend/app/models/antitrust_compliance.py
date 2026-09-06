"""独禁法・入札談合コンプライアンス（antitrust_compliance）.

ロードマップ #113〜#124（Issue #122）/ Phase 3 §5.9。

* ``antitrust_checks`` … #113 独禁法チェック・#114 入札談合リスクチェック・
  #117 価格情報交換禁止チェック・#118 JV 形成時競争法チェック・#119 競合との
  共同研究チェックを ``check_type`` で区分する決定論的ルールベース判定結果。
  ルールエンジンは ``app.services.antitrust_checker`` が唯一の正（AI 不使用）。
* ``antitrust_prior_applications`` … #115 競合他社接触記録・#116 会合・懇親会
  事前申請・#121 贈収賄・接待管理・#122 公務員接触記録・#123 寄付・協賛審査を
  ``application_type`` で区分する「事前申請 → 承認 → 記録」ワークフロー。
* ``antitrust_consultations`` … #120 競争法 AI 相談（一次情報引用付きの参考回答。
  最終法的判断は法務担当者・顧問弁護士が行う）。
* ``compliance_trainings`` … #124 コンプライアンス研修履歴（単純な履歴テーブル）。
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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JsonType

from ._mixins import AuditedByMixin, IntPKMixin, TimestampMixin
from .enums import (
    AntitrustApplicationStatus,
    AntitrustApplicationType,
    AntitrustCheckSeverity,
    AntitrustCheckType,
)

if TYPE_CHECKING:
    from .contract import Contract
    from .joint_venture import JointVenture
    from .user import User

_ALLOWED_CHECK_TYPE = ",".join(f"'{t.value}'" for t in AntitrustCheckType)
_ALLOWED_CHECK_SEVERITY = ",".join(f"'{s.value}'" for s in AntitrustCheckSeverity)
_ALLOWED_APPLICATION_TYPE = ",".join(f"'{t.value}'" for t in AntitrustApplicationType)
_ALLOWED_APPLICATION_STATUS = ",".join(f"'{s.value}'" for s in AntitrustApplicationStatus)


class AntitrustCheck(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """独禁法・入札談合等の決定論的ルールベースチェック結果（#113/#114/#117/#118/#119）."""

    __tablename__ = "antitrust_checks"

    check_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    check_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # 最終判定の重大度（全 finding 中の最悪値: info < warn < block）
    severity: Mapped[str] = mapped_column(
        String(16), nullable=False, default=AntitrustCheckSeverity.INFO.value
    )
    subject: Mapped[str] = mapped_column(String(256), nullable=False)
    contract_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True
    )
    jv_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("joint_ventures.id", ondelete="SET NULL"), nullable=True
    )
    # ルールエンジンへの入力コンテキスト（check_type ごとに項目が異なるため JSON で保持）
    input_context: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=dict, server_default="'{}'::jsonb"
    )
    # ComplianceFinding 相当のリスト（code/title/severity/description/citation/suggestion）
    findings: Mapped[list[dict[str, Any]]] = mapped_column(
        JsonType, nullable=False, default=list, server_default="'[]'::jsonb"
    )
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    contract: Mapped[Contract | None] = relationship("Contract")
    joint_venture: Mapped[JointVenture | None] = relationship("JointVenture")

    __table_args__ = (
        CheckConstraint(f"check_type IN ({_ALLOWED_CHECK_TYPE})", name="ck_antitrust_checks_type"),
        CheckConstraint(
            f"severity IN ({_ALLOWED_CHECK_SEVERITY})", name="ck_antitrust_checks_severity"
        ),
        Index("ix_antitrust_checks_type", "check_type"),
        Index("ix_antitrust_checks_severity", "severity"),
        Index("ix_antitrust_checks_contract", "contract_id"),
        Index("ix_antitrust_checks_jv", "jv_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AntitrustCheck id={self.id} no={self.check_no!r} type={self.check_type!r}>"


class AntitrustPriorApplication(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """事前申請 → 承認 → 記録ワークフロー（#115/#116/#121/#122/#123）."""

    __tablename__ = "antitrust_prior_applications"

    application_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    application_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=AntitrustApplicationStatus.SUBMITTED.value
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    counterparty_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    counterparty_organization: Mapped[str | None] = mapped_column(String(256), nullable=True)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    location: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # 接待・贈答・寄付協賛の金額（円）。対象外の申請種別では NULL。
    amount_jpy: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    attendees: Mapped[list[str] | None] = mapped_column(JsonType, nullable=True)
    contract_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True
    )
    jv_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("joint_ventures.id", ondelete="SET NULL"), nullable=True
    )
    approved_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL", use_alter=True), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 実施後の記録（#115〜#123 は事後の実施記録・議事メモが独禁法上の証跡として重要）
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    contract: Mapped[Contract | None] = relationship("Contract")
    joint_venture: Mapped[JointVenture | None] = relationship("JointVenture")
    approver: Mapped[User | None] = relationship("User", foreign_keys=[approved_by])

    __table_args__ = (
        CheckConstraint(
            f"application_type IN ({_ALLOWED_APPLICATION_TYPE})",
            name="ck_antitrust_applications_type",
        ),
        CheckConstraint(
            f"status IN ({_ALLOWED_APPLICATION_STATUS})",
            name="ck_antitrust_applications_status",
        ),
        CheckConstraint(
            "amount_jpy IS NULL OR amount_jpy >= 0", name="ck_antitrust_applications_amount"
        ),
        Index("ix_antitrust_applications_type", "application_type"),
        Index("ix_antitrust_applications_status", "status"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<AntitrustPriorApplication id={self.id} no={self.application_no!r} "
            f"status={self.status!r}>"
        )


class AntitrustConsultation(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """競争法 AI 相談（#120）— 一次情報引用付きの参考回答（法的助言の断定はしない）."""

    __tablename__ = "antitrust_consultations"

    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    # evidence_lookup.EvidenceHit.to_dict() 相当のリスト（一次情報の引用元）
    citations: Mapped[list[dict[str, Any]]] = mapped_column(
        JsonType, nullable=False, default=list, server_default="'[]'::jsonb"
    )
    contract_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True
    )

    contract: Mapped[Contract | None] = relationship("Contract")

    __table_args__ = (Index("ix_antitrust_consultations_contract", "contract_id"),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AntitrustConsultation id={self.id}>"


class ComplianceTraining(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """コンプライアンス研修履歴（#124）— 単純な履歴テーブル."""

    __tablename__ = "compliance_trainings"

    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL", use_alter=True), nullable=True
    )
    # 社外・退職者等 users 未登録者向けの表示名（user_id が NULL の場合に使用）
    attendee_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    training_title: Mapped[str] = mapped_column(String(256), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="antitrust")
    completed_at: Mapped[date] = mapped_column(Date, nullable=False)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    certificate_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User | None] = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 100)",
            name="ck_compliance_trainings_score",
        ),
        Index("ix_compliance_trainings_user", "user_id"),
        Index("ix_compliance_trainings_category", "category"),
        Index("ix_compliance_trainings_completed", "completed_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<ComplianceTraining id={self.id} title={self.training_title!r}>"


__all__ = [
    "AntitrustCheck",
    "AntitrustConsultation",
    "AntitrustPriorApplication",
    "ComplianceTraining",
]
