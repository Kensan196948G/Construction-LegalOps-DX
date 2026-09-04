"""Legal Matter Management（法務案件）モデル.

ロードマップ #71〜#84 / Issue #101。契約を越えた「法務案件そのもの」を管理する。

* ``legal_matters`` … Matter 台帳（matter_no 採番・状態・担当・Legal Hold 連動）
* ``matter_contracts`` … 関係契約リンク（#79・M2M）
* ``matter_events`` … 案件タイムライン（#78・追記専用・INSERT のみ）

状態遷移・イベント記録の正は ``app.services.matter_service``（ルールエンジン・
AI 不使用）。案件 ACL との統合（RLS）は既存 ``access_control`` 流用で後続。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JsonType

from ._mixins import AuditedByMixin, IntPKMixin, TimestampMixin
from .enums import MatterEventType, MatterPriority, MatterStatus, MatterType

if TYPE_CHECKING:
    from .contract import Contract
    from .legal_hold import LegalHoldCase
    from .user import User


_ALLOWED_TYPE = ",".join(f"'{t.value}'" for t in MatterType)
_ALLOWED_STATUS = ",".join(f"'{s.value}'" for s in MatterStatus)
_ALLOWED_PRIORITY = ",".join(f"'{p.value}'" for p in MatterPriority)
_ALLOWED_EVENT = ",".join(f"'{e.value}'" for e in MatterEventType)


class LegalMatter(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """法務案件（Matter）."""

    __tablename__ = "legal_matters"

    matter_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    matter_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=MatterStatus.OPEN.value)
    priority: Mapped[str] = mapped_column(
        String(16), nullable=False, default=MatterPriority.MEDIUM.value
    )
    assignee_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    # 昇格元（#73）: 現状は dispute 等の内部 id を汎用に記録
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    legal_hold_case_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("legal_hold_cases.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    close_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    assignee: Mapped[User | None] = relationship("User", foreign_keys=[assignee_id])
    legal_hold_case: Mapped[LegalHoldCase | None] = relationship("LegalHoldCase")
    contracts: Mapped[list[Contract]] = relationship("Contract", secondary="matter_contracts")
    events: Mapped[list[MatterEvent]] = relationship(
        "MatterEvent",
        back_populates="matter",
        cascade="all, delete-orphan",
        order_by="MatterEvent.id",
    )

    __table_args__ = (
        CheckConstraint(f"matter_type IN ({_ALLOWED_TYPE})", name="ck_legal_matters_type"),
        CheckConstraint(f"status IN ({_ALLOWED_STATUS})", name="ck_legal_matters_status"),
        CheckConstraint(f"priority IN ({_ALLOWED_PRIORITY})", name="ck_legal_matters_priority"),
        Index("ix_legal_matters_status", "status"),
        Index("ix_legal_matters_assignee", "assignee_id"),
        Index("ix_legal_matters_type", "matter_type"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<LegalMatter id={self.id} matter_no={self.matter_no!r} status={self.status!r}>"


class MatterEvent(IntPKMixin, TimestampMixin, Base):
    """Matter タイムラインイベント（追記専用・INSERT のみ）."""

    __tablename__ = "matter_events"

    matter_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("legal_matters.id", ondelete="CASCADE"),
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

    matter: Mapped[LegalMatter] = relationship("LegalMatter", back_populates="events")
    actor: Mapped[User | None] = relationship("User", foreign_keys=[actor_id])

    __table_args__ = (
        CheckConstraint(f"event_type IN ({_ALLOWED_EVENT})", name="ck_matter_events_type"),
        Index("ix_matter_events_matter", "matter_id"),
        Index("ix_matter_events_type", "event_type"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<MatterEvent id={self.id} matter_id={self.matter_id} type={self.event_type!r}>"


# Matter と契約の多対多リンク（#79 関係契約リンク）。クラスは持たず
# 純粋な association table として扱う（LegalMatter.contracts の secondary）。
matter_contracts_table = Table(
    "matter_contracts",
    Base.metadata,
    Column(
        "matter_id",
        BigInteger,
        ForeignKey("legal_matters.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "contract_id",
        BigInteger,
        ForeignKey("contracts.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    UniqueConstraint("matter_id", "contract_id", name="uq_matter_contracts_pair"),
)


__all__ = ["LegalMatter", "MatterEvent", "matter_contracts_table"]
