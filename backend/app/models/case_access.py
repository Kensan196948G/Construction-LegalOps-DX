"""案件単位 ACL（契約アクセス権限）モデル.

P0-6 対応: 外部顧問弁護士・案件限定アクセスを DB で正本化する。
``ethical_wall`` フラグは人事・談合調査・内部通報案件などの倫理壁対象
アクセスを示し、サービス層で特権ロール以外への公開を遮断する。
"""

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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from ._mixins import IntPKMixin, TimestampMixin

if TYPE_CHECKING:
    from .contract import Contract
    from .user import User


_ALLOWED_LEVELS = ("view", "comment", "edit")


class ContractAccessGrant(IntPKMixin, TimestampMixin, Base):
    """契約単位の利用者アクセス権限.

    - ``view``   : 閲覧のみ
    - ``comment``: 閲覧 + コメント
    - ``edit``   : 閲覧 + 編集（承認ワークフロー外の修正）
    """

    __tablename__ = "contract_access_grants"

    contract_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    access_level: Mapped[str] = mapped_column(String(16), nullable=False, default="view")
    ethical_wall: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    granted_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    contract: Mapped[Contract] = relationship("Contract")
    user: Mapped[User] = relationship("User", foreign_keys=[user_id])
    granter: Mapped[User | None] = relationship(
        "User", foreign_keys=[granted_by]
    )

    __table_args__ = (
        UniqueConstraint("contract_id", "user_id", name="uq_contract_access_grants_pair"),
        CheckConstraint(
            f"access_level IN ({','.join(repr(v) for v in _ALLOWED_LEVELS)})",
            name="ck_contract_access_grants_level",
        ),
        Index("ix_contract_access_grants_user", "user_id"),
        Index("ix_contract_access_grants_contract", "contract_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<ContractAccessGrant contract_id={self.contract_id} "
            f"user_id={self.user_id} level={self.access_level!r}>"
        )
