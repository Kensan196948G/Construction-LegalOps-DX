"""Reusable contract template model."""

from __future__ import annotations

from sqlalchemy import Boolean, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

from ._mixins import AuditedByMixin, IntPKMixin, TimestampMixin


class ContractTemplate(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """Persistent contract template used by the `/templates` API."""

    __tablename__ = "contract_templates"

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    contract_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __table_args__ = (
        UniqueConstraint("code", name="uq_contract_templates_code"),
        Index(
            "ix_contract_templates_contract_type",
            "contract_type",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_contract_templates_active",
            "is_active",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ContractTemplate id={self.id} code={self.code!r}>"
