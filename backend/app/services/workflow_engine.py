"""Approval workflow engine.

Implements the amount × risk matrix and route definitions
(A1, A2, B1, B2, C1, C2, D1) from
``docs/approval_workflow_policy.md``. The engine is intentionally
in-memory for Loop 2 — persistence is wired through optional callbacks
so the API layer can plug in repositories later without altering the
domain logic.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Final
from uuid import UUID, uuid4

import structlog

from app.models.enums import RiskLevel, WorkflowStepStatus, WorkflowStepType

logger = structlog.get_logger(__name__)


class WorkflowError(RuntimeError):
    """Raised on illegal workflow transitions or unknown IDs."""


class WorkflowAction(StrEnum):
    """User action issued against the *current* step."""

    APPROVE = "approve"
    CONDITIONAL_APPROVE = "conditional_approve"
    REJECT = "reject"
    SEND_BACK = "send_back"
    HOLD = "hold"


@dataclass(slots=True)
class WorkflowStep:
    id: UUID
    workflow_id: UUID
    sequence: int
    type: WorkflowStepType
    role: str  # display label (法務担当 / 法務課長 / 管理本部長 ...)
    status: WorkflowStepStatus = WorkflowStepStatus.PENDING
    actor_user_id: UUID | None = None
    decided_at: datetime | None = None
    comment: str | None = None


@dataclass(slots=True)
class Workflow:
    id: UUID
    contract_id: UUID
    route_code: str  # A1 / A2 / B1 ...
    risk_level: RiskLevel
    amount_jpy: int
    contract_type: str
    steps: list[WorkflowStep]
    current_index: int = 0
    is_completed: bool = False
    outside_counsel_flag: bool = False
    outside_counsel_reason: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Route definitions
# ---------------------------------------------------------------------------

# Each route is an ordered list of (step_type, display_role).
_ROUTE_DEFINITIONS: Final[dict[str, tuple[tuple[WorkflowStepType, str], ...]]] = {
    "A1": (
        (WorkflowStepType.LEGAL_REVIEW, "法務担当"),
    ),
    "A2": (
        (WorkflowStepType.LEGAL_REVIEW, "法務担当"),
        (WorkflowStepType.LEGAL_REVIEW, "法務課長"),
    ),
    "B1": (
        (WorkflowStepType.LEGAL_REVIEW, "法務担当"),
        (WorkflowStepType.LEGAL_REVIEW, "法務課長"),
        (WorkflowStepType.MANAGER_APPROVAL, "事業本部長"),
    ),
    "B2": (
        (WorkflowStepType.LEGAL_REVIEW, "法務担当"),
        (WorkflowStepType.LEGAL_REVIEW, "法務課長"),
        (WorkflowStepType.MANAGER_APPROVAL, "管理本部長"),
    ),
    "C1": (
        (WorkflowStepType.LEGAL_REVIEW, "法務担当"),
        (WorkflowStepType.LEGAL_REVIEW, "法務課長"),
        (WorkflowStepType.MANAGER_APPROVAL, "管理本部長"),
        (WorkflowStepType.EXEC_APPROVAL, "担当役員"),
    ),
    "C2": (
        (WorkflowStepType.LEGAL_REVIEW, "法務担当"),
        (WorkflowStepType.LEGAL_REVIEW, "法務課長"),
        (WorkflowStepType.CUSTOM, "顧問弁護士確認"),
        (WorkflowStepType.MANAGER_APPROVAL, "管理本部長"),
        (WorkflowStepType.EXEC_APPROVAL, "担当役員"),
    ),
    "D1": (
        (WorkflowStepType.LEGAL_REVIEW, "法務担当"),
        (WorkflowStepType.LEGAL_REVIEW, "法務課長"),
        (WorkflowStepType.CUSTOM, "顧問弁護士確認"),
        (WorkflowStepType.MANAGER_APPROVAL, "管理本部長"),
        (WorkflowStepType.EXEC_APPROVAL, "代表取締役"),
        (WorkflowStepType.CUSTOM, "取締役会報告"),
    ),
}

# Matrix rows are amount ceilings (inclusive); the final row is "over".
# Each column maps a RiskLevel to the route code.
_MATRIX: Final[tuple[tuple[int | None, dict[RiskLevel, str]], ...]] = (
    (5_000_000, {RiskLevel.LOW: "A1", RiskLevel.MEDIUM: "A2",
                 RiskLevel.HIGH: "B1", RiskLevel.CRITICAL: "C1"}),
    (30_000_000, {RiskLevel.LOW: "A2", RiskLevel.MEDIUM: "B1",
                  RiskLevel.HIGH: "B2", RiskLevel.CRITICAL: "C1"}),
    (100_000_000, {RiskLevel.LOW: "B1", RiskLevel.MEDIUM: "B2",
                   RiskLevel.HIGH: "C1", RiskLevel.CRITICAL: "C2"}),
    (500_000_000, {RiskLevel.LOW: "B2", RiskLevel.MEDIUM: "C1",
                   RiskLevel.HIGH: "C2", RiskLevel.CRITICAL: "D1"}),
    (None, {RiskLevel.LOW: "C1", RiskLevel.MEDIUM: "C2",
            RiskLevel.HIGH: "D1", RiskLevel.CRITICAL: "D1"}),
)


def select_route(amount_jpy: int, risk: RiskLevel) -> str:
    """Return the route code for the given amount × risk pair."""
    for ceiling, mapping in _MATRIX:
        if ceiling is None or amount_jpy <= ceiling:
            return mapping[risk]
    return "D1"  # defensive — unreachable due to None sentinel


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


@dataclass
class WorkflowEngine:
    """Workflow lifecycle service.

    The repository hooks are optional; in Loop 2 the engine keeps state
    in ``self._workflows``. Loop 3+ can pass ``loader`` / ``saver``
    coroutines that read/write the SQLAlchemy models.
    """

    loader: Callable[[UUID], Awaitable[Workflow | None]] | None = None
    saver: Callable[[Workflow], Awaitable[None]] | None = None
    notifier: Callable[[Workflow, WorkflowStep, str], Awaitable[None]] | None = None
    _workflows: dict[UUID, Workflow] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_workflow(
        self,
        contract_id: UUID,
        *,
        amount_jpy: int,
        risk_level: RiskLevel,
        risk_score: int = 0,
        contract_type: str = "その他",
        outside_counsel_triggers: dict[str, Any] | None = None,
    ) -> Workflow:
        """Create and persist a new :class:`Workflow` for ``contract_id``."""
        route_code = select_route(amount_jpy, risk_level)
        steps = self._build_steps(route_code)

        outside_flag, outside_reason = self._evaluate_outside_counsel(
            amount_jpy=amount_jpy,
            risk_score=risk_score,
            risk_level=risk_level,
            triggers=outside_counsel_triggers or {},
        )

        # If the outside-counsel flag is required but the chosen route does
        # not include a 顧問弁護士確認 step, upgrade the route.
        if outside_flag and not any(
            s.role == "顧問弁護士確認" for s in steps
        ):
            route_code = "C2" if route_code in {"A1", "A2", "B1", "B2", "C1"} else "D1"
            steps = self._build_steps(route_code)

        workflow = Workflow(
            id=uuid4(),
            contract_id=contract_id,
            route_code=route_code,
            risk_level=risk_level,
            amount_jpy=amount_jpy,
            contract_type=contract_type,
            steps=steps,
            outside_counsel_flag=outside_flag,
            outside_counsel_reason=outside_reason,
        )
        # First step becomes in-progress immediately.
        if workflow.steps:
            workflow.steps[0].status = WorkflowStepStatus.IN_PROGRESS

        await self._persist(workflow)
        logger.info(
            "workflow.started",
            workflow_id=str(workflow.id),
            contract_id=str(contract_id),
            route=route_code,
            risk=risk_level.value,
            amount=amount_jpy,
            outside_counsel=outside_flag,
        )
        return workflow

    async def transition(
        self,
        workflow_id: UUID,
        action: WorkflowAction | str,
        user_id: UUID,
        *,
        comment: str | None = None,
    ) -> WorkflowStep:
        """Apply ``action`` to the current step and return that step."""
        workflow = await self._load(workflow_id)
        if workflow.is_completed:
            raise WorkflowError("workflow already completed")
        if not workflow.steps:
            raise WorkflowError("workflow has no steps")

        action_enum = action if isinstance(action, WorkflowAction) else WorkflowAction(action)
        step = workflow.steps[workflow.current_index]

        if step.status not in (
            WorkflowStepStatus.PENDING,
            WorkflowStepStatus.IN_PROGRESS,
        ):
            raise WorkflowError(
                f"current step is already in terminal status {step.status.value}"
            )

        now = datetime.now(UTC)
        step.actor_user_id = user_id
        step.decided_at = now
        step.comment = comment

        if action_enum is WorkflowAction.APPROVE:
            step.status = WorkflowStepStatus.APPROVED
            await self._advance(workflow)
        elif action_enum is WorkflowAction.CONDITIONAL_APPROVE:
            if not comment:
                raise WorkflowError("conditional approve requires a condition comment")
            step.status = WorkflowStepStatus.APPROVED
            await self._advance(workflow)
        elif action_enum is WorkflowAction.REJECT:
            step.status = WorkflowStepStatus.REJECTED
            workflow.is_completed = True
        elif action_enum is WorkflowAction.SEND_BACK:
            step.status = WorkflowStepStatus.SENT_BACK
            await self._send_back(workflow)
        elif action_enum is WorkflowAction.HOLD:
            step.status = WorkflowStepStatus.PENDING
            step.decided_at = None
        else:  # pragma: no cover - exhaustive
            raise WorkflowError(f"unsupported action: {action_enum}")

        workflow.updated_at = now
        await self._persist(workflow)
        if self.notifier:
            await self.notifier(workflow, step, action_enum.value)
        logger.info(
            "workflow.transition",
            workflow_id=str(workflow.id),
            step_seq=step.sequence,
            action=action_enum.value,
            status=step.status.value,
        )
        return step

    async def escalate(self, workflow_id: UUID) -> Workflow:
        """Escalate the workflow: mark current step as delegated and add an
        upper-tier step, plus auto-attach the outside-counsel flag.
        """
        workflow = await self._load(workflow_id)
        if workflow.is_completed:
            raise WorkflowError("workflow already completed")

        workflow.outside_counsel_flag = True
        if not workflow.outside_counsel_reason:
            workflow.outside_counsel_reason = "manual_escalation"

        # Insert 顧問弁護士確認 immediately after the current step if absent.
        if not any(s.role == "顧問弁護士確認" for s in workflow.steps):
            idx = workflow.current_index + 1
            inserted = WorkflowStep(
                id=uuid4(),
                workflow_id=workflow.id,
                sequence=idx,
                type=WorkflowStepType.CUSTOM,
                role="顧問弁護士確認",
            )
            workflow.steps.insert(idx, inserted)
            # Renumber subsequent sequences.
            for i, s in enumerate(workflow.steps):
                s.sequence = i

        workflow.updated_at = datetime.now(UTC)
        await self._persist(workflow)
        logger.info(
            "workflow.escalated",
            workflow_id=str(workflow.id),
            outside_counsel=True,
        )
        return workflow

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_steps(self, route_code: str) -> list[WorkflowStep]:
        spec = _ROUTE_DEFINITIONS.get(route_code)
        if not spec:
            raise WorkflowError(f"unknown route code: {route_code}")
        wf_id = uuid4()  # placeholder; replaced when Workflow.id is set
        return [
            WorkflowStep(
                id=uuid4(),
                workflow_id=wf_id,
                sequence=i,
                type=step_type,
                role=role,
            )
            for i, (step_type, role) in enumerate(spec)
        ]

    def _evaluate_outside_counsel(
        self,
        *,
        amount_jpy: int,
        risk_score: int,
        risk_level: RiskLevel,
        triggers: dict[str, Any],
    ) -> tuple[bool, str | None]:
        """Apply the 10 outside-counsel auto-attach rules (policy §4)."""
        reasons: list[str] = []
        if risk_score >= 80 or risk_level == RiskLevel.CRITICAL:
            reasons.append("risk_score_80_plus")
        if triggers.get("no_liability_cap"):
            reasons.append("no_liability_cap")
        if amount_jpy >= 500_000_000:
            reasons.append("amount_500m_plus")
        if triggers.get("foreign_jurisdiction"):
            reasons.append("foreign_jurisdiction")
        if triggers.get("litigation_signal"):
            reasons.append("litigation_signal")
        if triggers.get("antisocial_concern"):
            reasons.append("antisocial_concern")
        if triggers.get("novel_contract_type"):
            reasons.append("novel_contract_type")
        if triggers.get("public_bid_qualification_impact"):
            reasons.append("public_bid_qualification_impact")
        if triggers.get("major_ip_transfer"):
            reasons.append("major_ip_transfer")
        if triggers.get("cross_border_personal_data"):
            reasons.append("cross_border_personal_data")
        if not reasons:
            return False, None
        return True, ",".join(reasons)

    async def _advance(self, workflow: Workflow) -> None:
        workflow.current_index += 1
        if workflow.current_index >= len(workflow.steps):
            workflow.is_completed = True
            return
        workflow.steps[workflow.current_index].status = (
            WorkflowStepStatus.IN_PROGRESS
        )

    async def _send_back(self, workflow: Workflow) -> None:
        """Reopen the previous step (or the drafter) for revision."""
        if workflow.current_index == 0:
            return
        workflow.current_index -= 1
        prev = workflow.steps[workflow.current_index]
        prev.status = WorkflowStepStatus.IN_PROGRESS
        prev.decided_at = None
        prev.actor_user_id = None
        prev.comment = None

    async def _load(self, workflow_id: UUID) -> Workflow:
        if workflow_id in self._workflows:
            return self._workflows[workflow_id]
        if self.loader:
            wf = await self.loader(workflow_id)
            if wf is not None:
                self._workflows[workflow_id] = wf
                return wf
        raise WorkflowError(f"workflow not found: {workflow_id}")

    async def _persist(self, workflow: Workflow) -> None:
        self._workflows[workflow.id] = workflow
        if self.saver:
            await self.saver(workflow)
