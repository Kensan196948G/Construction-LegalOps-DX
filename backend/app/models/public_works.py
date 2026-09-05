"""公共工事特化モデル（ロードマップ #41/#42/#54/#55/#56/#57）.

* ``contracting_agencies`` … 発注機関マスタ（#41）＋発注機関別契約条件（#42）。
  支払日数・前払率・保証期間等を機関ごとに保持し、契約条件の判定に使う。
* ``owner_notifications`` … 発注者への通知と期限（#54）。due_date の
  overdue / within_30 等のバケットは ``app.services.public_works_service``
  が動的に算出する（保存しない）。
* ``public_works_consultations`` … 発注者との協議プロセス（#55 工期延伸 /
  #56 スライド請求 / #57 設計変更）。**台帳は既存 ``change_orders``** が正本で
  あり、本テーブルは「協議の申出〜回答」のプロセス証跡（重複しない役割分担）。

状態遷移・集計は ``app.services.public_works_service`` のルールエンジンが唯一の正
（AI 不使用・決定論的）。
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
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from ._mixins import AuditedByMixin, IntPKMixin, TimestampMixin
from .enums import (
    AgencyType,
    OwnerNotificationStatus,
    OwnerNotificationType,
    PublicWorksConsultationStatus,
    PublicWorksConsultationType,
)

if TYPE_CHECKING:
    from .contract import Contract

_ALLOWED_AGENCY_TYPE = ",".join(f"'{t.value}'" for t in AgencyType)
_ALLOWED_NOTIF_TYPE = ",".join(f"'{t.value}'" for t in OwnerNotificationType)
_ALLOWED_NOTIF_STATUS = ",".join(f"'{s.value}'" for s in OwnerNotificationStatus)
_ALLOWED_CONSULT_TYPE = ",".join(f"'{t.value}'" for t in PublicWorksConsultationType)
_ALLOWED_CONSULT_STATUS = ",".join(f"'{s.value}'" for s in PublicWorksConsultationStatus)


class ContractingAgency(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """発注機関マスタ（#41）＋機関別契約条件（#42）."""

    __tablename__ = "contracting_agencies"

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    agency_type: Mapped[str] = mapped_column(String(32), nullable=False)
    prefecture: Mapped[str | None] = mapped_column(String(16), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # --- #42 発注機関別契約条件 ---
    payment_deadline_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    advance_payment_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    warranty_period_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requires_slide_clause: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    __table_args__ = (
        CheckConstraint(
            f"agency_type IN ({_ALLOWED_AGENCY_TYPE})",
            name="ck_contracting_agencies_type",
        ),
        CheckConstraint(
            "payment_deadline_days IS NULL OR payment_deadline_days > 0",
            name="ck_contracting_agencies_payment_days",
        ),
        CheckConstraint(
            "advance_payment_ratio IS NULL OR "
            "(advance_payment_ratio >= 0 AND advance_payment_ratio <= 1)",
            name="ck_contracting_agencies_advance",
        ),
        Index("ix_contracting_agencies_type", "agency_type"),
        Index("ix_contracting_agencies_active", "is_active"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<ContractingAgency id={self.id} code={self.code!r}>"


class OwnerNotification(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """発注者への通知・期限（#54）."""

    __tablename__ = "owner_notifications"

    notification_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    contract_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("contracts.id", ondelete="SET NULL"),
        nullable=True,
    )
    agency_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("contracting_agencies.id", ondelete="SET NULL"),
        nullable=True,
    )
    notification_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=OwnerNotificationStatus.OPEN.value
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notified_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    contract: Mapped[Contract | None] = relationship("Contract")
    agency: Mapped[ContractingAgency | None] = relationship("ContractingAgency")

    __table_args__ = (
        CheckConstraint(
            f"notification_type IN ({_ALLOWED_NOTIF_TYPE})",
            name="ck_owner_notifications_type",
        ),
        CheckConstraint(
            f"status IN ({_ALLOWED_NOTIF_STATUS})",
            name="ck_owner_notifications_status",
        ),
        Index("ix_owner_notifications_status", "status"),
        Index("ix_owner_notifications_contract", "contract_id"),
        Index("ix_owner_notifications_due", "due_date"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<OwnerNotification id={self.id} no={self.notification_no!r}>"


class PublicWorksConsultation(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """発注者との協議プロセス（#55 工期延伸 / #56 スライド請求 / #57 設計変更）.

    台帳（確定した変更内容）は ``change_orders`` が正本。本テーブルは
    協議の申出・回答・結果のプロセス証跡。
    """

    __tablename__ = "public_works_consultations"

    consultation_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    contract_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("contracts.id", ondelete="SET NULL"),
        nullable=True,
    )
    agency_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("contracting_agencies.id", ondelete="SET NULL"),
        nullable=True,
    )
    consultation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=PublicWorksConsultationStatus.OPEN.value
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # --- 申出内容 ---
    claimed_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    claimed_amount_jpy: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    # --- 結果（responded 時に記録）---
    resolved_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolved_amount_jpy: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    response_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    contract: Mapped[Contract | None] = relationship("Contract")
    agency: Mapped[ContractingAgency | None] = relationship("ContractingAgency")

    __table_args__ = (
        CheckConstraint(
            f"consultation_type IN ({_ALLOWED_CONSULT_TYPE})",
            name="ck_public_works_consultations_type",
        ),
        CheckConstraint(
            f"status IN ({_ALLOWED_CONSULT_STATUS})",
            name="ck_public_works_consultations_status",
        ),
        CheckConstraint(
            "claimed_days IS NULL OR claimed_days > 0",
            name="ck_public_works_consultations_days",
        ),
        CheckConstraint(
            "claimed_amount_jpy IS NULL OR claimed_amount_jpy >= 0",
            name="ck_public_works_consultations_amount",
        ),
        Index("ix_public_works_consultations_status", "status"),
        Index("ix_public_works_consultations_type", "consultation_type"),
        Index("ix_public_works_consultations_contract", "contract_id"),
        Index("ix_public_works_consultations_agency", "agency_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<PublicWorksConsultation id={self.id} no={self.consultation_no!r} "
            f"status={self.status!r}>"
        )


__all__ = ["ContractingAgency", "OwnerNotification", "PublicWorksConsultation"]
