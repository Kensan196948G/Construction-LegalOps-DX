"""``audit_logs`` table model with tamper-evident hash chain.

Reflects ``docs/database_design.md`` section 4.13 / 4.14.

Partitioning:
    This table is intended to be partitioned by month on ``occurred_at`` in
    production (see design doc section 7). For the MVP migration we ship a
    single non-partitioned table; the partitioning DDL will be introduced in
    a later Alembic revision.

Append-only:
    A trigger ``trg_audit_logs_no_update`` is installed in the migration to
    forbid UPDATE/DELETE. The ORM layer must always INSERT — never call
    ``session.merge`` or ``session.delete`` on instances of this model.
"""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    CHAR,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, InetType, JsonType, UuidType

from ._mixins import IntPKMixin

if TYPE_CHECKING:
    from .user import User


_ZERO_HASH = "0" * 64


class AuditLog(IntPKMixin, Base):
    """Append-only audit log entry with SHA-256 hash chain.

    The chain is computed as ::

        hash_chain = sha256(
            (previous_hash or "0"*64)
            + canonical_json(payload)
        ).hexdigest()

    Verification re-walks the table in ``id`` order and recomputes each row.
    """

    __tablename__ = "audit_logs"

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    actor_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    actor_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    request_id: Mapped[UUID | None] = mapped_column(
        UuidType, nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(InetType, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ``payload`` stores the canonical ``{"before": ..., "after": ...}`` dict.
    payload: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=dict, server_default="'{}'::jsonb"
    )
    previous_hash: Mapped[str | None] = mapped_column(CHAR(64), nullable=True)
    hash_chain: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    actor: Mapped[User | None] = relationship("User", foreign_keys=[actor_id])

    __table_args__ = (
        Index("ix_audit_logs_target", "target_type", "target_id"),
        Index("ix_audit_logs_actor", "actor_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_time", "occurred_at"),
    )

    # ---- Helpers ----------------------------------------------------------
    @staticmethod
    def compute_hash(previous_hash: str | None, canonical_payload: str) -> str:
        """Compute the SHA-256 link for a new audit-log row.

        :param previous_hash: hash_chain of the immediately preceding row;
            ``None`` for the genesis row (treated as 64 zeros).
        :param canonical_payload: deterministic JSON serialisation of the
            ``payload`` field (callers must ensure key-sorted output).
        """

        raw = (previous_hash or _ZERO_HASH) + canonical_payload
        return sha256(raw.encode("utf-8")).hexdigest()

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<AuditLog id={self.id} action={self.action!r} "
            f"target={self.target_type}:{self.target_id}>"
        )
