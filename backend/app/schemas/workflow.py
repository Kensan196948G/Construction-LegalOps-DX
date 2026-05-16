"""Workflow Pydantic schemas.

Mirrors ``docs/api_design.md`` section 7. The ``definition`` JSON inside a
:class:`WorkflowCreate` body uses :class:`WorkflowStepDefinition` to keep the
template steps strongly typed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import UserRole, WorkflowStepStatus, WorkflowStepType

from .common import ORMModel, TimestampsMixin


class WorkflowStepDefinition(BaseModel):
    """One step inside a workflow template (stored in ``workflows.definition``)."""

    seq: Annotated[int, Field(ge=1)]
    name: Annotated[str, Field(max_length=128)]
    step_type: WorkflowStepType
    assignee_role: Optional[UserRole] = None
    sla_hours: Optional[int] = Field(default=None, ge=0)


class WorkflowDefinition(BaseModel):
    """Root object stored in ``workflows.definition``."""

    steps: List[WorkflowStepDefinition]


class WorkflowCreate(BaseModel):
    code: Annotated[str, Field(max_length=64)]
    name: Annotated[str, Field(max_length=128)]
    description: Optional[str] = None
    contract_type: Optional[str] = Field(default=None, max_length=64)
    is_active: bool = True
    definition: WorkflowDefinition


class WorkflowRead(ORMModel, TimestampsMixin):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    contract_type: Optional[str] = None
    is_active: bool
    definition: dict[str, Any] = Field(default_factory=dict)
    version: int


class WorkflowStepRead(ORMModel, TimestampsMixin):
    id: int
    workflow_id: int
    contract_id: int
    seq: int
    name: str
    step_type: WorkflowStepType
    assignee_id: Optional[int] = None
    assignee_role: Optional[str] = None
    status: WorkflowStepStatus
    due_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    decision_note: Optional[str] = None


class WorkflowAction(BaseModel):
    """Body of approve / reject / send-back / delegate endpoints.

    ``action`` distinguishes the verb so the same schema can be reused by all
    four endpoints, while keeping the OpenAPI definitions explicit per route.
    """

    action: Annotated[str, Field(pattern="^(approve|reject|send_back|delegate)$")]
    comment: Optional[str] = Field(default=None, max_length=2000)
    to_seq: Optional[int] = Field(default=None, ge=1)
    to_user_id: Optional[int] = None


class WorkflowActionResult(BaseModel):
    step_id: int
    status: WorkflowStepStatus
    decided_at: datetime


# ---------------------------------------------------------------------------
# v1 public-API aliases (see ``docs/api_design.md`` section 7)
# ---------------------------------------------------------------------------


class WorkflowDefinitionCreate(WorkflowCreate):
    """Body of ``POST /workflows``."""


class WorkflowDefinitionOut(WorkflowRead):
    """Row schema for ``GET /workflows`` and ``/workflows/{id}``."""


class WorkflowStartRequest(BaseModel):
    """Body of ``POST /contracts/{id}/workflows``."""

    workflow_id: int
    definition_code: Optional[str] = None
    note: Optional[str] = Field(default=None, max_length=2000)


class WorkflowInstanceOut(ORMModel):
    """Read schema for a workflow instance attached to a contract."""

    id: int
    workflow_id: int
    contract_id: int
    status: Annotated[str, Field(pattern="^(pending|in_progress|approved|rejected|cancelled)$")]
    current_seq: Optional[int] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


class WorkflowStepOut(WorkflowStepRead):
    """Step row returned by ``GET /workflows/{id}/steps``."""


class WorkflowActionRequest(WorkflowAction):
    """Body of approve / reject / send-back / delegate endpoints."""


__all__ = [
    "WorkflowAction",
    "WorkflowActionRequest",
    "WorkflowActionResult",
    "WorkflowCreate",
    "WorkflowDefinition",
    "WorkflowDefinitionCreate",
    "WorkflowDefinitionOut",
    "WorkflowInstanceOut",
    "WorkflowRead",
    "WorkflowStartRequest",
    "WorkflowStepDefinition",
    "WorkflowStepOut",
    "WorkflowStepRead",
]
