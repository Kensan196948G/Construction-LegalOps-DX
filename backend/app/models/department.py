"""``departments`` table model.

Reflects ``docs/database_design.md`` section 4.1. Departments form a tree
through the self-referential ``parent_id`` FK and are used as the unit of
RLS isolation for ``contracts``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from ._mixins import IntPKMixin, TimestampMixin

if TYPE_CHECKING:
    from .user import User


class Department(IntPKMixin, TimestampMixin, Base):
    """Organisational department / division."""

    __tablename__ = "departments"

    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=True,
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    parent: Mapped[Optional["Department"]] = relationship(
        "Department",
        remote_side="Department.id",
        back_populates="children",
    )
    children: Mapped[List["Department"]] = relationship(
        "Department",
        back_populates="parent",
    )
    users: Mapped[List["User"]] = relationship("User", back_populates="department")

    __table_args__ = (
        Index(
            "ix_departments_parent",
            "parent_id",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "ix_departments_active",
            "is_active",
            postgresql_where="deleted_at IS NULL",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Department id={self.id} code={self.code!r}>"
