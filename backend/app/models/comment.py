"""``comments`` table model.

Reflects ``docs/database_design.md`` section 4.10.
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
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from ._mixins import IntPKMixin, TimestampMixin
from .enums import CommentVisibility

if TYPE_CHECKING:
    from .clause import Clause
    from .contract import Contract
    from .user import User


_ALLOWED_VIS = ",".join(f"'{v.value}'" for v in CommentVisibility)


class Comment(IntPKMixin, TimestampMixin, Base):
    """Discussion thread entry against a contract or specific clause.

    The team contract refers to a generic ``(target_type, target_id)`` pair;
    the canonical schema instead stores explicit FKs to ``contracts`` and
    optionally ``clauses``. ``target_type`` / ``target_id`` are provided as
    Python properties for callers that expect the abstract shape.
    """

    __tablename__ = "comments"

    contract_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("contracts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    clause_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("clauses.id", ondelete="RESTRICT"),
        nullable=True,
    )
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("comments.id", ondelete="RESTRICT"),
        nullable=True,
    )
    author_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", use_alter=True),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="internal",
        server_default="internal",
    )
    resolved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    contract: Mapped[Contract] = relationship("Contract", back_populates="comments")
    clause: Mapped[Clause | None] = relationship("Clause")
    author: Mapped[User] = relationship("User", foreign_keys=[author_id])
    parent: Mapped[Comment | None] = relationship(
        "Comment", remote_side="Comment.id"
    )

    __table_args__ = (
        CheckConstraint(
            f"visibility IN ({_ALLOWED_VIS})",
            name="ck_comments_visibility",
        ),
        Index(
            "ix_comments_contract",
            "contract_id",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "ix_comments_clause",
            "clause_id",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "ix_comments_author",
            "author_id",
            postgresql_where="deleted_at IS NULL",
        ),
    )

    @property
    def target_type(self) -> str:
        """Synthetic ``target_type`` field — ``clauses`` if scoped, else ``contracts``."""
        return "clauses" if self.clause_id is not None else "contracts"

    @property
    def target_id(self) -> int:
        return self.clause_id if self.clause_id is not None else self.contract_id

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Comment id={self.id} contract_id={self.contract_id} "
            f"author_id={self.author_id}>"
        )
