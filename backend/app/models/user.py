"""``users`` table model.

Reflects ``docs/database_design.md`` section 4.2. Authentication is delegated
to Microsoft Entra ID; ``entra_oid`` stores the ``oid`` claim from the JWT.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, List, Optional
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from ._mixins import IntPKMixin, TimestampMixin
from .enums import UserRole

if TYPE_CHECKING:
    from .department import Department


_ALLOWED_ROLES = ",".join(f"'{r.value}'" for r in UserRole)


class User(IntPKMixin, TimestampMixin, Base):
    """Application user backed by Entra ID."""

    __tablename__ = "users"

    entra_oid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, unique=True
    )
    email: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    department_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attributes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="'{}'::jsonb"
    )

    department: Mapped[Optional["Department"]] = relationship(
        "Department", back_populates="users"
    )

    __table_args__ = (
        CheckConstraint(
            f"role IN ({_ALLOWED_ROLES})",
            name="ck_users_role",
        ),
        Index(
            "ix_users_department",
            "department_id",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "ix_users_role",
            "role",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "ix_users_active",
            "is_active",
            postgresql_where="deleted_at IS NULL",
        ),
    )

    @property
    def role_enum(self) -> UserRole:
        """Convenience accessor returning the role as an :class:`UserRole`."""
        return UserRole(self.role)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<User id={self.id} email={self.email!r} role={self.role!r}>"


# Backref list typing for Department.users is set in department.py.
User.__annotations__.setdefault("contracts_drafted", "List[Any]")
