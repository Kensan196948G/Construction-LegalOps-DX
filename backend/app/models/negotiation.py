"""条項交渉イベント（Redline・交渉履歴）モデル.

ロードマップ #5（Redline 管理）・#6（交渉履歴管理）・#7（条項ステータス）・
#8（条項オーナー管理）の証跡。1 行 = 1 交渉イベント（demand / concession /
comment / redline / status_change / owner_change）であり、追記専用運用とする
（UPDATE / DELETE の API は公開しない）。

ステータス・オーナーの遷移は ``app.services.negotiation_service`` の
ルールエンジンが唯一の正。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from ._mixins import IntPKMixin, TimestampMixin
from .enums import ClauseNegotiationAction, ClauseNegotiationStatus, ClauseOwner

if TYPE_CHECKING:
    from .clause import Clause
    from .contract import Contract
    from .user import User


_ALLOWED_ACTION = ",".join(f"'{a.value}'" for a in ClauseNegotiationAction)
_ALLOWED_NEGO_STATUS = ",".join(f"'{s.value}'" for s in ClauseNegotiationStatus)
_ALLOWED_OWNER = ",".join(f"'{o.value}'" for o in ClauseOwner)


class ClauseNegotiationEvent(IntPKMixin, TimestampMixin, Base):
    """契約（任意で条項）に対する交渉イベント 1 件."""

    __tablename__ = "clause_negotiation_events"

    contract_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("contracts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    clause_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("clauses.id", ondelete="SET NULL"),
        nullable=True,
    )
    round_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    # status_change 用（変更前→変更後）
    status_from: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status_to: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # owner_change 用（変更前→変更後）
    owner_from: Mapped[str | None] = mapped_column(String(32), nullable=True)
    owner_to: Mapped[str | None] = mapped_column(String(32), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # redline: 修正提案テキスト（#5）
    proposed_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )

    contract: Mapped[Contract] = relationship("Contract")
    clause: Mapped[Clause | None] = relationship("Clause")
    actor: Mapped[User | None] = relationship("User")

    __table_args__ = (
        CheckConstraint(
            f"action IN ({_ALLOWED_ACTION})",
            name="ck_clause_negotiation_events_action",
        ),
        CheckConstraint(
            f"status_from IS NULL OR status_from IN ({_ALLOWED_NEGO_STATUS})",
            name="ck_clause_negotiation_events_status_from",
        ),
        CheckConstraint(
            f"status_to IS NULL OR status_to IN ({_ALLOWED_NEGO_STATUS})",
            name="ck_clause_negotiation_events_status_to",
        ),
        CheckConstraint(
            f"owner_from IS NULL OR owner_from IN ({_ALLOWED_OWNER})",
            name="ck_clause_negotiation_events_owner_from",
        ),
        CheckConstraint(
            f"owner_to IS NULL OR owner_to IN ({_ALLOWED_OWNER})",
            name="ck_clause_negotiation_events_owner_to",
        ),
        Index("ix_nego_events_contract", "contract_id"),
        Index("ix_nego_events_clause", "clause_id"),
        Index("ix_nego_events_action", "action"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<ClauseNegotiationEvent id={self.id} contract_id={self.contract_id} "
            f"action={self.action!r}>"
        )


__all__ = ["ClauseNegotiationEvent"]
