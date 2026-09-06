"""案件単位 ACL / 倫理壁 / Legal Hold モデル（P0-6 対応）."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JsonType

from ._mixins import IntPKMixin, TimestampMixin

if TYPE_CHECKING:
    from .contract import Contract
    from .user import User


class AccessControlEntry(IntPKMixin, TimestampMixin, Base):
    """案件単位のアクセス許可エントリ（RBAC を補完する ACL）。

    principal_type:
      - user             : users.id（principal_id に数値 ID の文字列）
      - department       : departments.id
      - role             : ロール名（viewer / drafter / reviewer / approver / admin）
      - external_counsel : 外部顧問弁護士の email
    """

    __tablename__ = "access_control_entries"

    contract_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
    )
    principal_type: Mapped[str] = mapped_column(String(16), nullable=False)
    principal_id: Mapped[str] = mapped_column(String(128), nullable=False)
    access_level: Mapped[str] = mapped_column(
        String(16), nullable=False, default="read", server_default="'read'"
    )
    granted_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    contract: Mapped[Contract] = relationship("Contract", back_populates="access_entries")
    grantor: Mapped[User | None] = relationship("User", foreign_keys=[granted_by], viewonly=True)

    __table_args__ = (
        UniqueConstraint(
            "contract_id",
            "principal_type",
            "principal_id",
            name="uq_access_entries_scope",
        ),
        CheckConstraint(
            "principal_type IN ('user', 'department', 'role', 'external_counsel')",
            name="ck_access_entries_principal_type",
        ),
        CheckConstraint(
            "access_level IN ('read', 'write', 'approve', 'admin')",
            name="ck_access_entries_access_level",
        ),
        Index("ix_access_entries_contract", "contract_id"),
        Index("ix_access_entries_principal", "principal_type", "principal_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<AccessControlEntry contract_id={self.contract_id} "
            f"principal={self.principal_type}:{self.principal_id} level={self.access_level}>"
        )


class LegalHold(IntPKMixin, TimestampMixin, Base):
    """Legal Hold — 証拠保全指示。

    active 中は対象データ（契約・添付・AI 入出力・紛争証拠）の自動削除が停止する。
    """

    __tablename__ = "legal_holds"

    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", server_default="'active'"
    )
    started_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    release_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_ids: Mapped[dict[str, object]] = mapped_column(
        JsonType, nullable=False, default=list, server_default="'[]'::jsonb"
    )
    # 人事・談合調査・内部通報など要倫理壁の案件では管理者・監査以外はアクセス不可
    ethical_wall: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    __table_args__ = (
        CheckConstraint("status IN ('active', 'released')", name="ck_legal_holds_status"),
        Index("ix_legal_holds_target", "target_type", "target_id"),
        Index("ix_legal_holds_status", "status"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<LegalHold id={self.id} target={self.target_type}:{self.target_id} "
            f"status={self.status!r}>"
        )


__all__ = ["AccessControlEntry", "LegalHold"]
