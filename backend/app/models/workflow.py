"""``workflows`` and ``workflow_steps`` table models.

Reflects ``docs/database_design.md`` sections 4.8 / 4.9.

Note:
    ``WorkflowTemplate`` is exposed as an alias of :class:`Workflow` to
    satisfy the team contract; the design doc keeps templates and definitions
    co-located in a single ``workflows`` table where ``definition`` JSONB
    stores the template steps.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from ._mixins import IntPKMixin, TimestampMixin
from .enums import WorkflowStepStatus, WorkflowStepType

if TYPE_CHECKING:
    from .contract import Contract
    from .user import User


_ALLOWED_STEP_TYPE = ",".join(f"'{t.value}'" for t in WorkflowStepType)
_ALLOWED_STEP_STATUS = ",".join(f"'{s.value}'" for s in WorkflowStepStatus)


class Workflow(IntPKMixin, TimestampMixin, Base):
    """Reusable workflow definition (a.k.a. template)."""

    __tablename__ = "workflows"

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contract_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    definition: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="'{}'::jsonb"
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )

    steps: Mapped[List["WorkflowStep"]] = relationship(
        "WorkflowStep", back_populates="workflow"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Workflow id={self.id} code={self.code!r}>"


# Alias to honour the team-contract name. Both names refer to the same ORM
# class so ``from app.models import WorkflowTemplate`` keeps working.
WorkflowTemplate = Workflow


class WorkflowStep(IntPKMixin, TimestampMixin, Base):
    """Per-contract execution of one workflow step."""

    __tablename__ = "workflow_steps"

    workflow_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("workflows.id", ondelete="RESTRICT"),
        nullable=False,
    )
    contract_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("contracts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    step_type: Mapped[str] = mapped_column(String(32), nullable=False)
    assignee_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", use_alter=True),
        nullable=True,
    )
    assignee_role: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decision_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="steps")
    contract: Mapped["Contract"] = relationship(
        "Contract", back_populates="workflow_steps"
    )
    assignee: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[assignee_id]
    )

    __table_args__ = (
        UniqueConstraint(
            "contract_id", "seq", name="uq_wfsteps_contract_seq"
        ),
        CheckConstraint(
            f"step_type IN ({_ALLOWED_STEP_TYPE})",
            name="ck_wfsteps_step_type",
        ),
        CheckConstraint(
            f"status IN ({_ALLOWED_STEP_STATUS})",
            name="ck_wfsteps_status",
        ),
        Index(
            "ix_wfsteps_contract",
            "contract_id",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "ix_wfsteps_assignee",
            "assignee_id",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "ix_wfsteps_status",
            "status",
            postgresql_where="deleted_at IS NULL",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<WorkflowStep id={self.id} contract_id={self.contract_id} "
            f"seq={self.seq} status={self.status!r}>"
        )
