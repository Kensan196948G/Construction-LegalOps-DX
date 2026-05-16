"""``risk_items`` table model.

Reflects ``docs/database_design.md`` section 4.7.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from ._mixins import IntPKMixin, TimestampMixin
from .enums import RiskImpact, RiskItemStatus, RiskLevel, RiskProbability

if TYPE_CHECKING:
    from .clause import Clause
    from .contract import Contract
    from .legal_review import LegalReview
    from .user import User


_ALLOWED_SEVERITY = ",".join(f"'{r.value}'" for r in RiskLevel)
_ALLOWED_PROB = ",".join(f"'{r.value}'" for r in RiskProbability)
_ALLOWED_IMPACT = ",".join(f"'{r.value}'" for r in RiskImpact)
_ALLOWED_STATUS = ",".join(f"'{s.value}'" for s in RiskItemStatus)


class RiskItem(IntPKMixin, TimestampMixin, Base):
    """A single risk register entry tied to a contract / clause / review."""

    __tablename__ = "risk_items"

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
    legal_review_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("legal_reviews.id", ondelete="RESTRICT"),
        nullable=True,
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    probability: Mapped[str] = mapped_column(
        String(16), nullable=False, default="medium", server_default="medium"
    )
    impact: Mapped[str] = mapped_column(
        String(16), nullable=False, default="medium", server_default="medium"
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    mitigation: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ``recommendation`` aliased term in the team contract; kept as Text and
    # populated by the service layer when AI suggests an action.
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="open", server_default="open"
    )
    owner_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", use_alter=True),
        nullable=True,
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    contract: Mapped[Contract] = relationship(
        "Contract", back_populates="risk_items"
    )
    clause: Mapped[Clause | None] = relationship("Clause")
    legal_review: Mapped[LegalReview | None] = relationship(
        "LegalReview", back_populates="risk_items"
    )
    owner: Mapped[User | None] = relationship("User", foreign_keys=[owner_id])

    __table_args__ = (
        CheckConstraint(
            f"severity IN ({_ALLOWED_SEVERITY})",
            name="ck_risk_severity",
        ),
        CheckConstraint(
            f"probability IN ({_ALLOWED_PROB})",
            name="ck_risk_probability",
        ),
        CheckConstraint(
            f"impact IN ({_ALLOWED_IMPACT})",
            name="ck_risk_impact",
        ),
        CheckConstraint(
            f"status IN ({_ALLOWED_STATUS})",
            name="ck_risk_status",
        ),
        Index(
            "ix_risk_contract",
            "contract_id",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "ix_risk_severity",
            "severity",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "ix_risk_status",
            "status",
            postgresql_where="deleted_at IS NULL",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<RiskItem id={self.id} contract_id={self.contract_id} "
            f"severity={self.severity!r}>"
        )
