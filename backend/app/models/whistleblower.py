"""内部通報・調査管理（Phase3 §5.10 / Issue #123・ロードマップ #125〜#135）.

設計の核心（最重要）: 通報者を特定できる情報（氏名・連絡先等）は
``whistleblower_reports``（通報内容本体）とは別テーブル
``whistleblower_reporter_profiles`` に分離する。両テーブルへのアクセスは
案件単位 ACL（``whistleblower_case_access``）で管理者/監査ロールと調査担当
者のみに限定する（既存 ``case_access`` / ``access_control`` パターンを踏襲）。

* ``whistleblower_reports``          … 通報台帳（本体・非識別情報のみ）
* ``whistleblower_reporter_profiles`` … 通報者識別情報（隔離・1:1）
* ``whistleblower_case_access``       … 調査担当者限定 ACL
* ``whistleblower_evidence``          … 証拠保全（#129）
* ``whistleblower_interviews``        … ヒアリング記録（#130）
* ``whistleblower_timeline_events``   … 調査タイムライン（追記専用・#131）
* ``whistleblower_actions``           … 是正措置・再発防止管理（#132/#133）

匿名通報（``is_anonymous=True``）の場合、``whistleblower_reports`` の
``created_by`` は NULL のまま保持し（サービス層が匿名時に設定しない）、
``whistleblower_reporter_profiles`` 行も作成しない。これにより、DB レベルで
「通報者を特定できる情報がどこにも存在しない」状態を作る。

RLS（PostgreSQL のみ）は migration 024 で本体・識別情報テーブルに適用する。
SQLite / テスト環境ではサービス層（``app.services.whistleblower_service``）
の ACL チェックが同等の隔離を担う。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

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
from .enums import (
    WhistleblowerActionCategory,
    WhistleblowerActionStatus,
    WhistleblowerCaseRole,
    WhistleblowerCategory,
    WhistleblowerEvidenceType,
    WhistleblowerIntervieweeType,
    WhistleblowerReportStatus,
    WhistleblowerSeverity,
    WhistleblowerTimelineEventType,
)

if TYPE_CHECKING:
    from .attachment import Attachment
    from .matter import LegalMatter
    from .user import User


def _allowed(enum_cls: Any) -> str:
    return ",".join(f"'{v.value}'" for v in enum_cls)


_ALLOWED_CATEGORY = _allowed(WhistleblowerCategory)
_ALLOWED_STATUS = _allowed(WhistleblowerReportStatus)
_ALLOWED_SEVERITY = _allowed(WhistleblowerSeverity)
_ALLOWED_CASE_ROLE = _allowed(WhistleblowerCaseRole)
_ALLOWED_EVIDENCE_TYPE = _allowed(WhistleblowerEvidenceType)
_ALLOWED_INTERVIEWEE_TYPE = _allowed(WhistleblowerIntervieweeType)
_ALLOWED_TIMELINE_TYPE = _allowed(WhistleblowerTimelineEventType)
_ALLOWED_ACTION_CATEGORY = _allowed(WhistleblowerActionCategory)
_ALLOWED_ACTION_STATUS = _allowed(WhistleblowerActionStatus)


class WhistleblowerReport(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """内部通報台帳（本体・非識別情報のみ）.

    通報者を特定しうる情報は一切保持しない（別テーブル
    :class:`WhistleblowerReporterProfile` に隔離）。``created_by`` /
    ``updated_by`` も匿名通報時はサービス層が NULL のまま保存する。
    """

    __tablename__ = "whistleblower_reports"

    report_no: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=WhistleblowerReportStatus.RECEIVED.value
    )
    severity: Mapped[str] = mapped_column(
        String(16), nullable=False, default=WhistleblowerSeverity.MEDIUM.value
    )
    is_anonymous: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    occurred_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    matter_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("legal_matters.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    lead_investigator_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    substantiated: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    close_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    matter: Mapped[LegalMatter | None] = relationship("LegalMatter")
    lead_investigator: Mapped[User | None] = relationship(
        "User", foreign_keys=[lead_investigator_id]
    )
    reporter_profile: Mapped[WhistleblowerReporterProfile | None] = relationship(
        "WhistleblowerReporterProfile",
        back_populates="report",
        uselist=False,
        cascade="all, delete-orphan",
    )
    case_access: Mapped[list[WhistleblowerCaseAccess]] = relationship(
        "WhistleblowerCaseAccess", back_populates="report", cascade="all, delete-orphan"
    )
    evidence: Mapped[list[WhistleblowerEvidence]] = relationship(
        "WhistleblowerEvidence", back_populates="report", cascade="all, delete-orphan"
    )
    interviews: Mapped[list[WhistleblowerInterview]] = relationship(
        "WhistleblowerInterview", back_populates="report", cascade="all, delete-orphan"
    )
    timeline: Mapped[list[WhistleblowerTimelineEvent]] = relationship(
        "WhistleblowerTimelineEvent",
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="WhistleblowerTimelineEvent.id",
    )
    actions: Mapped[list[WhistleblowerAction]] = relationship(
        "WhistleblowerAction", back_populates="report", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            f"category IN ({_ALLOWED_CATEGORY})", name="ck_whistleblower_reports_category"
        ),
        CheckConstraint(f"status IN ({_ALLOWED_STATUS})", name="ck_whistleblower_reports_status"),
        CheckConstraint(
            f"severity IN ({_ALLOWED_SEVERITY})", name="ck_whistleblower_reports_severity"
        ),
        Index("ix_whistleblower_reports_status", "status"),
        Index("ix_whistleblower_reports_category", "category"),
        Index("ix_whistleblower_reports_matter", "matter_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<WhistleblowerReport id={self.id} no={self.report_no!r} status={self.status!r}>"


class WhistleblowerReporterProfile(IntPKMixin, TimestampMixin, Base):
    """通報者識別情報（隔離テーブル・1:1・最重要の分離対象）.

    このテーブルへのアクセスは調査担当者 ACL
    （:class:`WhistleblowerCaseAccess`）で ``can_view_reporter_identity``
    が True の付与を持つ者と admin/auditor に限定する。匿名通報では行自体
    を作成しない。
    """

    __tablename__ = "whistleblower_reporter_profiles"

    report_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("whistleblower_reports.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    reporter_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    department: Mapped[str | None] = mapped_column(String(128), nullable=True)
    relationship_to_subject: Mapped[str | None] = mapped_column(String(64), nullable=True)
    consent_identity_disclosure: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    report: Mapped[WhistleblowerReport] = relationship(
        "WhistleblowerReport", back_populates="reporter_profile"
    )

    __table_args__ = (Index("ix_whistleblower_reporter_profiles_report", "report_id"),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<WhistleblowerReporterProfile report_id={self.report_id}>"


class WhistleblowerCaseAccess(IntPKMixin, TimestampMixin, Base):
    """調査担当者限定 ACL（#127・既存 case_access パターン踏襲）."""

    __tablename__ = "whistleblower_case_access"

    report_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("whistleblower_reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_in_case: Mapped[str] = mapped_column(
        String(24), nullable=False, default=WhistleblowerCaseRole.INVESTIGATOR.value
    )
    can_view_reporter_identity: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    granted_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    report: Mapped[WhistleblowerReport] = relationship(
        "WhistleblowerReport", back_populates="case_access"
    )
    user: Mapped[User] = relationship("User", foreign_keys=[user_id])
    granter: Mapped[User | None] = relationship("User", foreign_keys=[granted_by])

    __table_args__ = (
        UniqueConstraint("report_id", "user_id", name="uq_whistleblower_case_access_pair"),
        CheckConstraint(
            f"role_in_case IN ({_ALLOWED_CASE_ROLE})", name="ck_whistleblower_case_access_role"
        ),
        Index("ix_whistleblower_case_access_report", "report_id"),
        Index("ix_whistleblower_case_access_user", "user_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<WhistleblowerCaseAccess report_id={self.report_id} "
            f"user_id={self.user_id} role={self.role_in_case!r}>"
        )


class WhistleblowerEvidence(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """証拠保全（#129）."""

    __tablename__ = "whistleblower_evidence"

    report_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("whistleblower_reports.id", ondelete="CASCADE"),
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
    preserved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    chain_of_custody: Mapped[str | None] = mapped_column(Text, nullable=True)

    report: Mapped[WhistleblowerReport] = relationship(
        "WhistleblowerReport", back_populates="evidence"
    )
    attachment: Mapped[Attachment | None] = relationship("Attachment")

    __table_args__ = (
        CheckConstraint(
            f"evidence_type IN ({_ALLOWED_EVIDENCE_TYPE})",
            name="ck_whistleblower_evidence_type",
        ),
        Index("ix_whistleblower_evidence_report", "report_id"),
    )


class WhistleblowerInterview(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """ヒアリング記録（#130）.

    ``interviewee_type='reporter'`` の場合、氏名等は調査担当者のみが
    アクセスできる本テーブル（ACL 保護下）にのみ記録し、
    :class:`WhistleblowerReporterProfile` と重複入力しないことを運用ルール
    とする（サービス層はこの制約をドキュメントで担保する）。
    """

    __tablename__ = "whistleblower_interviews"

    report_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("whistleblower_reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    interviewee_type: Mapped[str] = mapped_column(String(16), nullable=False)
    interviewee_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    conducted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    conducted_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    report: Mapped[WhistleblowerReport] = relationship(
        "WhistleblowerReport", back_populates="interviews"
    )
    conductor: Mapped[User | None] = relationship("User", foreign_keys=[conducted_by])

    __table_args__ = (
        CheckConstraint(
            f"interviewee_type IN ({_ALLOWED_INTERVIEWEE_TYPE})",
            name="ck_whistleblower_interviews_type",
        ),
        Index("ix_whistleblower_interviews_report", "report_id"),
    )


class WhistleblowerTimelineEvent(IntPKMixin, TimestampMixin, Base):
    """調査タイムライン（#131・追記専用）."""

    __tablename__ = "whistleblower_timeline_events"

    report_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("whistleblower_reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    actor_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )

    report: Mapped[WhistleblowerReport] = relationship(
        "WhistleblowerReport", back_populates="timeline"
    )
    actor: Mapped[User | None] = relationship("User", foreign_keys=[actor_id])

    __table_args__ = (
        CheckConstraint(
            f"event_type IN ({_ALLOWED_TIMELINE_TYPE})", name="ck_whistleblower_timeline_type"
        ),
        Index("ix_whistleblower_timeline_report", "report_id"),
    )


class WhistleblowerAction(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """是正措置・再発防止管理（#132/#133）."""

    __tablename__ = "whistleblower_actions"

    report_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("whistleblower_reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    action_category: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=WhistleblowerActionStatus.OPEN.value
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    report: Mapped[WhistleblowerReport] = relationship(
        "WhistleblowerReport", back_populates="actions"
    )
    owner: Mapped[User | None] = relationship("User", foreign_keys=[owner_id])
    verifier: Mapped[User | None] = relationship("User", foreign_keys=[verified_by])

    __table_args__ = (
        CheckConstraint(
            f"action_category IN ({_ALLOWED_ACTION_CATEGORY})",
            name="ck_whistleblower_actions_category",
        ),
        CheckConstraint(
            f"status IN ({_ALLOWED_ACTION_STATUS})", name="ck_whistleblower_actions_status"
        ),
        Index("ix_whistleblower_actions_report", "report_id"),
        Index("ix_whistleblower_actions_status", "status"),
    )


__all__ = [
    "WhistleblowerAction",
    "WhistleblowerCaseAccess",
    "WhistleblowerEvidence",
    "WhistleblowerInterview",
    "WhistleblowerReport",
    "WhistleblowerReporterProfile",
    "WhistleblowerTimelineEvent",
]
