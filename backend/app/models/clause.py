"""``clauses`` and ``clause_library`` table models.

Reflects ``docs/database_design.md`` sections 4.5 and 4.6.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import ArrayTextType, Base, JsonType

from ._mixins import AuditedByMixin, IntPKMixin, TimestampMixin
from .enums import ClauseRecommendation, RiskLevel

if TYPE_CHECKING:
    from .contract import Contract


_ALLOWED_RISK = ",".join(f"'{r.value}'" for r in RiskLevel)
_ALLOWED_RECOM = ",".join(f"'{r.value}'" for r in ClauseRecommendation)


class ClauseLibrary(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """Reusable / canonical clause repository.

    Defined first so that ``clauses.library_clause_id`` can FK into it.
    """

    __tablename__ = "clause_library"

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="recommended",
        server_default="'recommended'",
    )
    tags: Mapped[list[str]] = mapped_column(
        ArrayTextType, nullable=False, default=list, server_default="'{}'"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    clauses: Mapped[list[Clause]] = relationship("Clause", back_populates="library_clause")

    __table_args__ = (
        CheckConstraint(
            f"recommendation IN ({_ALLOWED_RECOM})",
            name="ck_library_recommendation",
        ),
        Index(
            "ix_library_category",
            "category",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "ix_library_recom",
            "recommendation",
            postgresql_where="deleted_at IS NULL",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ClauseLibrary id={self.id} code={self.code!r}>"


class Clause(IntPKMixin, TimestampMixin, Base):
    """A clause extracted (or drafted) inside a specific contract."""

    __tablename__ = "clauses"

    contract_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("contracts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    library_clause_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("clause_library.id", ondelete="RESTRICT"),
        nullable=True,
    )
    risk_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ai_findings: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=dict, server_default="'{}'::jsonb"
    )

    contract: Mapped[Contract] = relationship("Contract", back_populates="clauses")
    library_clause: Mapped[ClauseLibrary | None] = relationship(
        "ClauseLibrary", back_populates="clauses"
    )

    __table_args__ = (
        UniqueConstraint("contract_id", "seq", name="uq_clauses_contract_seq"),
        CheckConstraint(
            f"risk_level IS NULL OR risk_level IN ({_ALLOWED_RISK})",
            name="ck_clauses_risk_level",
        ),
        Index(
            "ix_clauses_contract",
            "contract_id",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "ix_clauses_risk",
            "risk_level",
            postgresql_where="deleted_at IS NULL",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Clause id={self.id} contract_id={self.contract_id} seq={self.seq}>"
