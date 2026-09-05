"""JV（共同企業体）管理モデル.

ロードマップ #61〜#70（JV 台帳・協定書・構成員・出資比率・損益分担・
役割権限マトリクス・JV 内紛争・終了清算）/ Phase 2。

* ``joint_ventures`` … #61 JV 台帳（JV 名・代表会社・状態・期間）
* ``jv_members`` … #63 代表会社・構成員管理（#64 出資比率・#65 損益分担率）
* ``jv_agreements`` … #62 JV 協定書管理（締結・終了）
* ``jv_disputes`` … #69 JV 内紛争・請求（JV 内での清算請求等の証跡）
* ``jv_settlements`` … #70 終了・清算管理（精算内容の記録）

状態遷移・整合チェックは ``app.services.jv_service`` のルールエンジンが唯一の正
（AI 不使用・決定論的）。#67 JV 承認ルートは既存 workflow_engine を流用し、
#68 JV 契約差分 AI レビューは契約レビュー基盤（reviews）で対応するため
本モデルでは扱わない（重複しない役割分担）。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from ._mixins import AuditedByMixin, IntPKMixin, TimestampMixin
from .enums import JvAgreementStatus, JvDisputeStatus, JvMemberRole, JvSettlementStatus, JvStatus

if TYPE_CHECKING:
    from .contract import Contract

_ALLOWED_JV_STATUS = ",".join(f"'{s.value}'" for s in JvStatus)
_ALLOWED_MEMBER_ROLE = ",".join(f"'{r.value}'" for r in JvMemberRole)
_ALLOWED_AGREEMENT_STATUS = ",".join(f"'{s.value}'" for s in JvAgreementStatus)
_ALLOWED_DISPUTE_STATUS = ",".join(f"'{s.value}'" for s in JvDisputeStatus)
_ALLOWED_SETTLEMENT_STATUS = ",".join(f"'{s.value}'" for s in JvSettlementStatus)


class JointVenture(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """JV 台帳（#61）."""

    __tablename__ = "joint_ventures"

    jv_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=JvStatus.PROSPECTING.value
    )
    # 代表会社名（#63・jv_members の representative と整合をサービス層で検証）
    representative_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    works_title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # 対象工事の契約（任意で紐づけ）
    contract_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("contracts.id", ondelete="SET NULL"),
        nullable=True,
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    dissolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    contract: Mapped[Contract | None] = relationship("Contract")
    members: Mapped[list[JvMember]] = relationship(
        "JvMember", back_populates="joint_venture", order_by="JvMember.id"
    )
    agreements: Mapped[list[JvAgreement]] = relationship(
        "JvAgreement", back_populates="joint_venture", order_by="JvAgreement.id"
    )
    disputes: Mapped[list[JvDispute]] = relationship(
        "JvDispute", back_populates="joint_venture", order_by="JvDispute.id"
    )
    settlements: Mapped[list[JvSettlement]] = relationship(
        "JvSettlement", back_populates="joint_venture", order_by="JvSettlement.id"
    )

    __table_args__ = (
        CheckConstraint(f"status IN ({_ALLOWED_JV_STATUS})", name="ck_joint_ventures_status"),
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_joint_ventures_period",
        ),
        Index("ix_joint_ventures_status", "status"),
        Index("ix_joint_ventures_contract", "contract_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<JointVenture id={self.id} no={self.jv_no!r} status={self.status!r}>"


class JvMember(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """JV 構成員（#63 代表会社・構成員 / #64 出資比率 / #65 損益分担）."""

    __tablename__ = "jv_members"

    jv_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("joint_ventures.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, default=JvMemberRole.MEMBER.value
    )
    company_name: Mapped[str] = mapped_column(String(256), nullable=False)
    # #64 出資比率（%・0〜100）
    equity_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    # #65 損益分担率（%・0〜100・NULL は出資比率に連動）
    profit_share_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    joint_venture: Mapped[JointVenture] = relationship("JointVenture", back_populates="members")

    __table_args__ = (
        CheckConstraint(
            f"role IN ({_ALLOWED_MEMBER_ROLE})",
            name="ck_jv_members_role",
        ),
        CheckConstraint(
            "equity_ratio IS NULL OR (equity_ratio >= 0 AND equity_ratio <= 100)",
            name="ck_jv_members_equity",
        ),
        CheckConstraint(
            "profit_share_ratio IS NULL OR (profit_share_ratio >= 0 AND profit_share_ratio <= 100)",
            name="ck_jv_members_profit",
        ),
        Index("ix_jv_members_jv", "jv_id"),
        Index("ix_jv_members_role", "role"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<JvMember id={self.id} jv={self.jv_id} role={self.role!r}>"


class JvAgreement(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """JV 協定書（#62）."""

    __tablename__ = "jv_agreements"

    jv_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("joint_ventures.id", ondelete="CASCADE"),
        nullable=False,
    )
    agreement_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=JvAgreementStatus.DRAFT.value
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    signed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    terminated_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    document_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    joint_venture: Mapped[JointVenture] = relationship(
        "JointVenture", back_populates="agreements"
    )

    __table_args__ = (
        CheckConstraint(
            f"status IN ({_ALLOWED_AGREEMENT_STATUS})",
            name="ck_jv_agreements_status",
        ),
        Index("ix_jv_agreements_jv", "jv_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<JvAgreement id={self.id} no={self.agreement_no!r}>"


class JvDispute(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """JV 内紛争・請求（#69）."""

    __tablename__ = "jv_disputes"

    jv_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("joint_ventures.id", ondelete="CASCADE"),
        nullable=False,
    )
    dispute_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=JvDisputeStatus.OPEN.value
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    claimant_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    respondent_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    amount_claimed_jpy: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    raised_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    response_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    joint_venture: Mapped[JointVenture] = relationship(
        "JointVenture", back_populates="disputes"
    )

    __table_args__ = (
        CheckConstraint(
            f"status IN ({_ALLOWED_DISPUTE_STATUS})",
            name="ck_jv_disputes_status",
        ),
        CheckConstraint(
            "amount_claimed_jpy IS NULL OR amount_claimed_jpy >= 0",
            name="ck_jv_disputes_amount",
        ),
        Index("ix_jv_disputes_jv", "jv_id"),
        Index("ix_jv_disputes_status", "status"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<JvDispute id={self.id} no={self.dispute_no!r} status={self.status!r}>"


class JvSettlement(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """JV 終了・清算（#70）."""

    __tablename__ = "jv_settlements"

    jv_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("joint_ventures.id", ondelete="CASCADE"),
        nullable=False,
    )
    settlement_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=JvSettlementStatus.PENDING.value
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    settled_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    # 清算金額（構成員配分額の合計）
    settlement_amount_jpy: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )

    joint_venture: Mapped[JointVenture] = relationship(
        "JointVenture", back_populates="settlements"
    )

    __table_args__ = (
        CheckConstraint(
            f"status IN ({_ALLOWED_SETTLEMENT_STATUS})",
            name="ck_jv_settlements_status",
        ),
        CheckConstraint(
            "settlement_amount_jpy IS NULL OR settlement_amount_jpy >= 0",
            name="ck_jv_settlements_amount",
        ),
        Index("ix_jv_settlements_jv", "jv_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<JvSettlement id={self.id} no={self.settlement_no!r} status={self.status!r}>"


__all__ = [
    "JointVenture",
    "JvAgreement",
    "JvDispute",
    "JvMember",
    "JvSettlement",
]
