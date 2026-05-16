"""Shared SQLAlchemy column / mixin definitions.

These mixins enforce the conventions documented in
``docs/database_design.md`` section 2:

* ``id``        BIGSERIAL PRIMARY KEY
* ``created_at``/``updated_at`` TIMESTAMPTZ NOT NULL DEFAULT now()
* ``deleted_at`` TIMESTAMPTZ NULL (soft delete)
* ``version``   INTEGER (optimistic lock) - opt-in via :class:`VersionedMixin`
* ``created_by``/``updated_by`` BIGINT REFERENCES users(id) - opt-in via
  :class:`AuditedByMixin`

Models import :class:`Base` from ``app.db.base`` (provided by the DB / Infra
team). If that module is not yet available the import will raise at runtime
during Loop convergence; the Models team writes the import unconditionally
per the team contract.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


class TimestampMixin:
    """``created_at`` / ``updated_at`` / ``deleted_at`` columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class VersionedMixin:
    """Optimistic locking via integer ``version`` column."""

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )


class AuditedByMixin:
    """``created_by`` / ``updated_by`` FK to ``users.id``.

    Implemented with ``declared_attr`` so the FK is materialised on each
    concrete subclass and ``use_alter=True`` to break the circular dependency
    with the ``users`` table during migration creation order.
    """

    @declared_attr
    @classmethod
    def created_by(cls) -> Mapped[int | None]:
        return mapped_column(
            BigInteger,
            ForeignKey("users.id", ondelete="RESTRICT", use_alter=True),
            nullable=True,
        )

    @declared_attr
    @classmethod
    def updated_by(cls) -> Mapped[int | None]:
        return mapped_column(
            BigInteger,
            ForeignKey("users.id", ondelete="RESTRICT", use_alter=True),
            nullable=True,
        )


class IntPKMixin:
    """``id BIGSERIAL PRIMARY KEY`` column."""

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
