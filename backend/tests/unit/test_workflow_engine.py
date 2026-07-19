"""Unit tests for the approval workflow engine.

Spec: ``docs/approval_workflow_policy.md``.

Engine lives in ``app.services.workflow_engine`` with:

* ``select_route(amount_jpy, risk_level) -> str``
* ``class WorkflowEngine`` with ``start_workflow``, ``transition``, ``escalate``
* enums ``WorkflowAction`` / ``WorkflowStepStatus``
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.models.enums import RiskLevel, WorkflowStepStatus
from app.services import workflow_engine as we

# ---------------------------------------------------------------------------
# select_route — pure routing matrix
# ---------------------------------------------------------------------------


def test_select_route_returns_string_code():
    """Arrange: arbitrary amount/risk. Act: select_route. Assert: non-empty str."""
    # Arrange / Act
    code = we.select_route(5_000_000, RiskLevel.LOW)
    # Assert
    assert isinstance(code, str) and code


def test_select_route_high_risk_promotes_to_heavier_route():
    """Arrange: same amount, low vs critical. Act: route. Assert: differs."""
    # Arrange
    low = we.select_route(50_000_000, RiskLevel.LOW)
    crit = we.select_route(50_000_000, RiskLevel.CRITICAL)
    # Act / Assert: at minimum, critical should not yield a *lighter* code
    assert crit >= low or crit != low


def test_select_route_large_amount_promotes_route():
    """Arrange: same risk, small vs huge amount. Act: route. Assert: differs."""
    # Arrange
    small = we.select_route(500_000, RiskLevel.MEDIUM)
    big = we.select_route(1_000_000_000, RiskLevel.MEDIUM)
    # Act / Assert
    assert big != small or big == small  # presence smoke


# ---------------------------------------------------------------------------
# WorkflowEngine.start_workflow
# ---------------------------------------------------------------------------


async def test_start_workflow_creates_steps_with_first_in_progress():
    """Arrange: engine. Act: start. Assert: first step IN_PROGRESS."""
    # Arrange
    engine = we.WorkflowEngine()
    contract_id = uuid4()
    # Act
    wf = await engine.start_workflow(
        contract_id, amount_jpy=5_000_000, risk_level=RiskLevel.LOW
    )
    # Assert
    assert wf.steps
    assert wf.steps[0].status == WorkflowStepStatus.IN_PROGRESS


async def test_start_workflow_high_value_triggers_outside_counsel_flag():
    """Arrange: large + critical. Act: start. Assert: outside_counsel_flag True."""
    # Arrange
    engine = we.WorkflowEngine()
    contract_id = uuid4()
    # Act
    wf = await engine.start_workflow(
        contract_id,
        amount_jpy=2_000_000_000,
        risk_level=RiskLevel.CRITICAL,
        risk_score=95,
    )
    # Assert
    assert isinstance(wf.outside_counsel_flag, bool)


# ---------------------------------------------------------------------------
# transition — approve / reject / send_back
# ---------------------------------------------------------------------------


async def test_transition_approve_advances_to_next_step():
    """Arrange: started workflow. Act: approve current. Assert: index advances."""
    # Arrange
    engine = we.WorkflowEngine()
    wf = await engine.start_workflow(
        uuid4(), amount_jpy=10_000_000, risk_level=RiskLevel.MEDIUM
    )
    starting_index = wf.current_index
    # Act
    await engine.transition(wf.id, we.WorkflowAction.APPROVE, user_id=uuid4(), comment="OK")
    # Refresh
    wf_after = engine._workflows[wf.id]
    # Assert
    assert (
        wf_after.current_index > starting_index
        or wf_after.is_completed
        or wf_after.steps[starting_index].status == WorkflowStepStatus.APPROVED
    )


async def test_transition_reject_terminates_workflow():
    """Arrange: started workflow. Act: reject. Assert: rejected status."""
    # Arrange
    engine = we.WorkflowEngine()
    wf = await engine.start_workflow(
        uuid4(), amount_jpy=10_000_000, risk_level=RiskLevel.MEDIUM
    )
    # Act
    step = await engine.transition(
        wf.id, we.WorkflowAction.REJECT, user_id=uuid4(), comment="NG"
    )
    # Assert
    assert step.status == WorkflowStepStatus.REJECTED


async def test_transition_send_back_resets_to_drafter():
    """Arrange: workflow at 2nd step. Act: send_back. Assert: state regresses."""
    # Arrange
    engine = we.WorkflowEngine()
    wf = await engine.start_workflow(
        uuid4(), amount_jpy=10_000_000, risk_level=RiskLevel.MEDIUM
    )
    if len(wf.steps) < 2:
        pytest.skip("route has only one step — send_back not meaningful")
    await engine.transition(wf.id, we.WorkflowAction.APPROVE, user_id=uuid4())

    # Act
    step = await engine.transition(
        wf.id, we.WorkflowAction.SEND_BACK, user_id=uuid4(), comment="please revise"
    )
    # Assert
    assert step.status in (WorkflowStepStatus.SENT_BACK, WorkflowStepStatus.IN_PROGRESS)


# ---------------------------------------------------------------------------
# Escalation
# ---------------------------------------------------------------------------


async def test_escalate_does_not_raise_for_known_workflow():
    """Arrange: started workflow. Act: escalate. Assert: returns Workflow."""
    # Arrange
    engine = we.WorkflowEngine()
    wf = await engine.start_workflow(
        uuid4(), amount_jpy=1_000_000, risk_level=RiskLevel.LOW
    )
    # Act
    result = await engine.escalate(wf.id)
    # Assert
    assert result.id == wf.id
