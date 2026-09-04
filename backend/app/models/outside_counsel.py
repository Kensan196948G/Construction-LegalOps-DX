"""顧問弁護士・外部法律事務所管理モデル.

ロードマップ #85〜#96 / Issue #102。
* ``law_firms`` … 法律事務所台帳（#86）
* ``counsel_lawyers`` … 担当弁護士台帳（#87）
* ``legal_engagements`` … 依頼・質問/回答管理（#85/#88/#89/#90/#91/#92/#93）

状態遷移（open → answered → confirmed / cancel）と回答期限の運用は
``app.services.outside_counsel_service`` が唯一の正。
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
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from ._mixins import AuditedByMixin, IntPKMixin, TimestampMixin
from .enums import EngagementStatus

if TYPE_CHECKING:
    from .matter import LegalMatter
    from .user import User


_ALLOWED_STATUS = ",".join(f"'{s.value}'" for s in EngagementStatus)


class LawFirm(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """法律事務所台帳（#86）."""

    __tablename__ = "law_firms"

    firm_name: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    contact_email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    lawyers: Mapped[list[CounselLawyer]] = relationship("CounselLawyer", back_populates="firm")

    __table_args__ = (Index("ix_law_firms_active", "is_active"),)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<LawFirm id={self.id} name={self.firm_name!r}>"


class CounselLawyer(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """担当弁護士台帳（#87）."""

    __tablename__ = "counsel_lawyers"

    firm_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("law_firms.id", ondelete="RESTRICT"),
        nullable=False,
    )
    lawyer_name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    bar_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    specialties: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    firm: Mapped[LawFirm] = relationship("LawFirm", back_populates="lawyers")

    __table_args__ = (
        Index("ix_counsel_lawyers_firm", "firm_id"),
        Index("ix_counsel_lawyers_active", "is_active"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<CounselLawyer id={self.id} name={self.lawyer_name!r}>"


class LegalEngagement(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """外部弁護士への依頼（質問・回答）."""

    __tablename__ = "legal_engagements"

    engagement_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    firm_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("law_firms.id", ondelete="RESTRICT"),
        nullable=False,
    )
    lawyer_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("counsel_lawyers.id", ondelete="SET NULL"),
        nullable=True,
    )
    matter_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("legal_matters.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=EngagementStatus.OPEN.value
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    answered_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    # 利益相反（#91）・Confidential 分類（#92）
    conflict_of_interest: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    conflict_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidential: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # 費用（#93・見込み）
    fee_estimate_jpy: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    firm: Mapped[LawFirm] = relationship("LawFirm")
    lawyer: Mapped[CounselLawyer | None] = relationship("CounselLawyer")
    matter: Mapped[LegalMatter | None] = relationship("LegalMatter")
    answerer: Mapped[User | None] = relationship("User", foreign_keys=[answered_by])

    __table_args__ = (
        CheckConstraint(f"status IN ({_ALLOWED_STATUS})", name="ck_legal_engagements_status"),
        Index("ix_legal_engagements_firm", "firm_id"),
        Index("ix_legal_engagements_status", "status"),
        Index("ix_legal_engagements_matter", "matter_id"),
        Index("ix_legal_engagements_due", "due_date"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<LegalEngagement id={self.id} status={self.status!r}>"


__all__ = ["CounselLawyer", "LawFirm", "LegalEngagement"]
