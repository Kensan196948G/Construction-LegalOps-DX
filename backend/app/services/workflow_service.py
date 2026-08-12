"""Workflow service — definition CRUD + contract instance lifecycle.

Design note: there is no ``workflow_instances`` table.  A "workflow instance"
for a contract is the aggregate of its ``WorkflowStep`` rows.  The
``instance_id`` used by the v1 API is the ``contract_id`` (one active
workflow per contract at a time).  The computed
:class:`WorkflowInstance` dataclass satisfies ``WorkflowInstanceOut``
because ``WorkflowInstanceOut`` inherits ``ORMModel`` with
``from_attributes=True``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract
from app.models.enums import WorkflowStepStatus
from app.models.user import User
from app.models.workflow import Workflow, WorkflowStep
from app.schemas.workflow import WorkflowApplicationOut
from app.services.contract_type import normalize_contract_type

_FULL_ACCESS_ROLES = {"admin", "legal", "auditor", "reviewer", "approver"}

_TERMINAL_STEP_STATUSES = {
    WorkflowStepStatus.APPROVED.value,
    WorkflowStepStatus.SKIPPED.value,
}


def _is_full_access(viewer: Any) -> bool:
    return getattr(viewer, "role", None) in _FULL_ACCESS_ROLES


# ---------------------------------------------------------------------------
# Synthetic instance type (no ORM table needed)
# ---------------------------------------------------------------------------


@dataclass
class WorkflowInstance:
    """Aggregate view of workflow execution for a single contract."""

    id: int  # == contract_id — stable instance identifier
    workflow_id: int
    contract_id: int
    status: str  # pending | in_progress | approved | rejected | cancelled
    current_seq: int | None
    started_at: datetime
    completed_at: datetime | None


def _compute_instance(steps: list[WorkflowStep]) -> WorkflowInstance:
    if not steps:
        raise LookupError("no steps found for this workflow instance")

    ordered = sorted(steps, key=lambda s: s.seq)
    first = ordered[0]

    statuses = {s.status for s in steps}

    if WorkflowStepStatus.REJECTED.value in statuses:
        agg_status = "rejected"
    elif all(s.status in _TERMINAL_STEP_STATUSES for s in steps):
        agg_status = "approved"
    elif WorkflowStepStatus.IN_PROGRESS.value in statuses:
        agg_status = "in_progress"
    else:
        agg_status = "pending"

    active_step = next(
        (
            s
            for s in ordered
            if s.status in (WorkflowStepStatus.PENDING.value, WorkflowStepStatus.IN_PROGRESS.value)
        ),
        None,
    )

    completed_at: datetime | None = None
    if agg_status in ("approved", "rejected"):
        def _to_naive(dt: datetime) -> datetime:
            return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt

        decided_ats = [_to_naive(s.decided_at) for s in steps if s.decided_at is not None]
        completed_at = max(decided_ats) if decided_ats else None

    return WorkflowInstance(
        id=first.contract_id,
        workflow_id=first.workflow_id,
        contract_id=first.contract_id,
        status=agg_status,
        current_seq=active_step.seq if active_step else None,
        started_at=first.created_at,
        completed_at=completed_at,
    )


async def _steps_for_contract(session: AsyncSession, contract_id: int) -> list[WorkflowStep]:
    result = await session.execute(
        select(WorkflowStep)
        .where(
            WorkflowStep.contract_id == contract_id,
            WorkflowStep.deleted_at.is_(None),
        )
        .order_by(WorkflowStep.seq)
    )
    return list(result.scalars())


# ---------------------------------------------------------------------------
# Definition CRUD
# ---------------------------------------------------------------------------


async def list_definitions(
    session: AsyncSession,
    *,
    contract_type: str | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[Workflow], int]:
    stmt = select(Workflow).where(Workflow.deleted_at.is_(None))
    if contract_type is not None:
        stmt = stmt.where(Workflow.contract_type == contract_type)

    count_q = await session.execute(stmt.with_only_columns(func.count(Workflow.id)).order_by(None))
    total = count_q.scalar() or 0

    stmt = stmt.order_by(Workflow.id.asc()).offset((page - 1) * size).limit(size)
    rows = await session.execute(stmt)
    return list(rows.scalars()), total


async def create_definition(
    session: AsyncSession,
    *,
    data: Any,
) -> Workflow:
    definition_dict = (
        data.definition.model_dump()
        if hasattr(data.definition, "model_dump")
        else dict(data.definition)
    )
    wf = Workflow(
        code=data.code,
        name=data.name,
        description=getattr(data, "description", None),
        contract_type=normalize_contract_type(getattr(data, "contract_type", None)),
        is_active=getattr(data, "is_active", True),
        definition=definition_dict,
    )
    session.add(wf)
    await session.flush()
    return wf


# ---------------------------------------------------------------------------
# Instance lifecycle
# ---------------------------------------------------------------------------


async def start_workflow(
    session: AsyncSession,
    *,
    contract_id: int,
    definition_code: str | None,
    actor: Any,
) -> WorkflowInstance:
    """Create WorkflowStep rows from the named definition; activate step 1."""
    if definition_code:
        result = await session.execute(
            select(Workflow).where(
                Workflow.code == definition_code,
                Workflow.deleted_at.is_(None),
            )
        )
        wf = result.scalar_one_or_none()
    else:
        result = await session.execute(
            select(Workflow)
            .where(Workflow.is_active.is_(True), Workflow.deleted_at.is_(None))
            .limit(1)
        )
        wf = result.scalar_one_or_none()

    if wf is None:
        raise LookupError(f"workflow definition '{definition_code}' not found")

    existing = await _steps_for_contract(session, contract_id)
    if existing:
        raise ValueError(f"contract {contract_id} already has an active workflow")

    now = datetime.now(UTC)
    step_defs = (wf.definition or {}).get("steps", [])
    steps: list[WorkflowStep] = []

    for i, step_def in enumerate(step_defs):
        if isinstance(step_def, dict):
            sla_hours = step_def.get("sla_hours")
            name = step_def.get("name", f"Step {i + 1}")
            step_type = step_def.get("step_type", "approval")
            seq = step_def.get("seq", i + 1)
            assignee_role = step_def.get("assignee_role")
        else:
            sla_hours = getattr(step_def, "sla_hours", None)
            name = getattr(step_def, "name", f"Step {i + 1}")
            step_type = getattr(step_def, "step_type", "approval")
            seq = getattr(step_def, "seq", i + 1)
            assignee_role = getattr(step_def, "assignee_role", None)

        step = WorkflowStep(
            workflow_id=wf.id,
            contract_id=contract_id,
            seq=seq,
            name=name,
            step_type=step_type,
            assignee_role=assignee_role,
            status=(
                WorkflowStepStatus.IN_PROGRESS.value if i == 0 else WorkflowStepStatus.PENDING.value
            ),
            due_at=(now + timedelta(hours=sla_hours)) if sla_hours else None,
        )
        session.add(step)
        steps.append(step)

    if not steps:
        fallback = WorkflowStep(
            workflow_id=wf.id,
            contract_id=contract_id,
            seq=1,
            name="承認",
            step_type="approval",
            status=WorkflowStepStatus.IN_PROGRESS.value,
        )
        session.add(fallback)
        steps.append(fallback)

    await session.flush()
    return _compute_instance(steps)


async def get_instance(
    session: AsyncSession,
    *,
    instance_id: int,
    viewer: Any,
) -> WorkflowInstance | None:
    """Return the workflow instance for a contract (instance_id == contract_id)."""
    steps = await _steps_for_contract(session, instance_id)
    if not steps:
        return None
    if not _is_full_access(viewer):
        from app.models.contract import Contract

        contract = await session.get(Contract, instance_id)
        if contract is None or contract.drafter_id != viewer.db_id:
            return None
    return _compute_instance(steps)


async def list_applications(
    session: AsyncSession,
    *,
    viewer: Any,
    status: str | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[WorkflowApplicationOut], int]:
    """稟議一覧（workflow_step × contract × drafter の結合ビュー）."""
    stmt = (
        select(WorkflowStep, Contract, User)
        .join(Contract, Contract.id == WorkflowStep.contract_id)
        .outerjoin(User, User.id == Contract.drafter_id)
        .where(
            WorkflowStep.deleted_at.is_(None),
            Contract.deleted_at.is_(None),
        )
    )
    if not _is_full_access(viewer):
        stmt = stmt.where(Contract.drafter_id == viewer.db_id)
    if status:
        stmt = stmt.where(WorkflowStep.status == status)

    count_stmt = stmt.with_only_columns(func.count(WorkflowStep.id)).order_by(None)
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = (
        stmt.order_by(WorkflowStep.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = (await session.execute(stmt)).all()

    items: list[WorkflowApplicationOut] = []
    for step, contract, drafter in rows:
        items.append(
            WorkflowApplicationOut(
                step_id=step.id,
                contract_id=contract.id,
                contract_no=contract.contract_no,
                title=contract.title,
                contract_type=contract.contract_type,
                counterparty=contract.counterparty,
                amount=(
                    Decimal(str(contract.amount)) if contract.amount is not None else None
                ),
                applicant=drafter.display_name if drafter is not None else None,
                step_name=step.name,
                step_type=step.step_type,
                status=step.status,
                due_at=step.due_at,
                submitted_at=step.created_at,
            )
        )
    return items, total


async def list_steps(
    session: AsyncSession,
    *,
    instance_id: int,
    viewer: Any,
) -> list[WorkflowStep]:
    """Return ordered steps for a contract's workflow."""
    steps = await _steps_for_contract(session, instance_id)
    if not steps:
        return []
    if not _is_full_access(viewer):
        from app.models.contract import Contract

        contract = await session.get(Contract, instance_id)
        if contract is None or contract.drafter_id != viewer.db_id:
            return []
    return steps


async def execute_action(
    session: AsyncSession,
    *,
    instance_id: int,
    actor: Any,
    payload: Any,
) -> WorkflowInstance:
    """Apply approve / reject / send_back / delegate to the active step."""
    steps = await _steps_for_contract(session, instance_id)
    if not steps:
        raise LookupError(f"workflow instance {instance_id} not found")

    ordered = sorted(steps, key=lambda s: s.seq)
    active_step = next(
        (s for s in ordered if s.status == WorkflowStepStatus.IN_PROGRESS.value),
        None,
    )
    if active_step is None:
        raise ValueError("no active step available for this action")

    # Authorise: assignee or full-access role. assignee_id holds a real
    # users.id, so compare the resolved db identity (Issue #45) — the raw
    # token subject would never match and silently locked assignees out.
    actor_id = actor.db_id
    if active_step.assignee_id is not None:
        if actor_id != active_step.assignee_id and not _is_full_access(actor):
            raise PermissionError("you are not the assignee for this step")
    elif not _is_full_access(actor):
        required_role = active_step.assignee_role
        if required_role and getattr(actor, "role", None) != required_role:
            raise PermissionError("your role is not authorised for this step")

    now = datetime.now(UTC)
    action: str = payload.action

    if action == "approve":
        active_step.status = WorkflowStepStatus.APPROVED.value
        active_step.decided_at = now
        active_step.decision_note = getattr(payload, "comment", None)
        active_step.updated_at = now
        next_step = next(
            (
                s
                for s in ordered
                if s.seq > active_step.seq and s.status == WorkflowStepStatus.PENDING.value
            ),
            None,
        )
        if next_step:
            next_step.status = WorkflowStepStatus.IN_PROGRESS.value
            next_step.updated_at = now

    elif action in ("reject", "return"):
        active_step.status = WorkflowStepStatus.REJECTED.value
        active_step.decided_at = now
        active_step.decision_note = getattr(payload, "comment", None)
        active_step.updated_at = now

    elif action == "send_back":
        to_seq: int = getattr(payload, "to_seq", None) or 1
        target = next((s for s in ordered if s.seq == to_seq), None)
        if target is None:
            raise ValueError(f"step seq={to_seq} not found")
        active_step.status = WorkflowStepStatus.SENT_BACK.value
        active_step.decided_at = now
        active_step.decision_note = getattr(payload, "comment", None)
        active_step.updated_at = now
        target.status = WorkflowStepStatus.IN_PROGRESS.value
        target.decided_at = None
        target.updated_at = now

    elif action == "delegate":
        to_user_id: int | None = getattr(payload, "to_user_id", None)
        if to_user_id is None:
            raise ValueError("to_user_id is required for delegate action")
        active_step.assignee_id = to_user_id
        active_step.updated_at = now

    await session.flush()
    refreshed = await _steps_for_contract(session, instance_id)
    return _compute_instance(refreshed)
