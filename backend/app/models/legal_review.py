"""``legal_reviews`` table model + related issue/action ORM helpers.

Reflects ``docs/database_design.md`` section 4.4. AI-generated findings are
stored in the ``result`` JSONB column; the ``ReviewIssue`` and
``SuggestedAction`` classes below are Pydantic-friendly *structural* helpers
exposed via ``app.schemas.legal_review`` — they are not separate tables
because the data lives within the JSONB blob per the design doc.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from ._mixins import AuditedByMixin, IntPKMixin, TimestampMixin
from .enums import ReviewStatus, ReviewType, RiskLevel

if TYPE_CHECKING:
    from .contract import Contract
    from .risk_item import RiskItem
    from .user import User


_ALLOWED_TYPE = ",".join(f"'{r.value}'" for r in ReviewType)
_ALLOWED_STATUS = ",".join(f"'{s.value}'" for s in ReviewStatus)
_ALLOWED_RISK = ",".join(f"'{r.value}'" for r in RiskLevel)


class LegalReview(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """A single review pass over a contract (AI / human / hybrid)."""

    __tablename__ = "legal_reviews"

    contract_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("contracts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    review_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    ai_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ai_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    overall_risk: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Risk score 0-100; not in the raw DDL but required by the team contract.
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="'{}'::jsonb"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reviewer_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", use_alter=True),
        nullable=True,
    )

    contract: Mapped[Contract] = relationship(
        "Contract", back_populates="legal_reviews"
    )
    reviewer: Mapped[User | None] = relationship("User", foreign_keys=[reviewer_id])
    risk_items: Mapped[list[RiskItem]] = relationship(
        "RiskItem", back_populates="legal_review"
    )

    __table_args__ = (
        CheckConstraint(
            f"review_type IN ({_ALLOWED_TYPE})",
            name="ck_reviews_type",
        ),
        CheckConstraint(
            f"status IN ({_ALLOWED_STATUS})",
            name="ck_reviews_status",
        ),
        CheckConstraint(
            f"overall_risk IS NULL OR overall_risk IN ({_ALLOWED_RISK})",
            name="ck_reviews_overall_risk",
        ),
        CheckConstraint(
            "risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)",
            name="ck_reviews_risk_score_range",
        ),
        Index(
            "ix_reviews_contract",
            "contract_id",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "ix_reviews_status",
            "status",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "ix_reviews_overall",
            "overall_risk",
            postgresql_where="deleted_at IS NULL",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<LegalReview id={self.id} contract_id={self.contract_id} "
            f"status={self.status!r}>"
        )
