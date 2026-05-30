"""``knowledge_articles`` table model.

Stores internally authored legal-knowledge articles (case summaries,
contract clause guidance, law citations). Searchable by keyword and
optionally by contract type.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

from ._mixins import AuditedByMixin, IntPKMixin, TimestampMixin


class KnowledgeArticle(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """A single legal-knowledge article authored by legal staff."""

    __tablename__ = "knowledge_articles"

    title: Mapped[str] = mapped_column(String(256), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    contract_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # tags stored as a JSONB array for PostgreSQL; SQLite fallback via test_session shim
    tags: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    citations: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    author_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", use_alter=True),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_knowledge_title", "title"),
        Index("ix_knowledge_contract_type", "contract_type"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<KnowledgeArticle id={self.id} title={self.title!r}>"
