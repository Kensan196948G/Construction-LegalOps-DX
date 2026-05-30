"""Extended unit tests for app.services.workflow_engine.

Covers lines previously uncovered (81% -> 90%+):
  lines 138, 190-191, 231, 233, 242, 255-258, 265-267, 274, 290, 327, 353,
  357, 359, 361, 363, 365, 367, 369, 377-378, 386, 397-402, 407

Test categories (15 tests):
  - WorkflowError on unknown workflow_id
  - WorkflowError on already-completed workflow (transition + escalate)
  - WorkflowAction.CONDITIONAL_APPROVE with / without comment
  - WorkflowAction.HOLD sets pending + clears decided_at
  - WorkflowAction.SEND_BACK at index 0 (no prior step)
  - Approve all steps to completion (is_completed via _advance)
  - Outside-counsel trigger flags (no_liability_cap, foreign_jurisdiction, etc.)
  - Route upgrade when outside_counsel needed but route lacks counsel step
  - _build_steps with unknown route code
  - Notifier callback invoked after transition
  - Saver callback invoked on persist
  - Loader callback used when workflow not in memory
  - Escalate inserts 顧問弁護士確認 step; second escalate does not duplicate
  - select_route matrix boundary values
"""

from __future__ import annotations

from uuid import uuid4

import pytest

we = pytest.importorskip(
    "app.services.workflow_engine",
    reason="workflow engine implemented in Loop 3",
)

from app.models.enums import RiskLevel, WorkflowStepStatus  # noqa: E402
from app.services.workflow_engine import (  # noqa: E402
    WorkflowAction,
    WorkflowEngine,
    WorkflowError,
    select_route,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _start_a1() -> tuple[WorkflowEngine, we.Workflow]:  # type: ignore[name-defined]
    """Return (engine, workflow) for route A1 (single-step, LOW risk, 1M JPY)."""
    engine = WorkflowEngine()
    wf = await engine.start_workflow(uuid4(), amount_jpy=1_000_000, risk_level=RiskLevel.LOW)
    return engine, wf


async def _start_b1() -> tuple[WorkflowEngine, we.Workflow]:  # type: ignore[name-defined]
    """Return (engine, workflow) for route B1 (3 steps, MEDIUM risk, 10M JPY)."""
    engine = WorkflowEngine()
    wf = await engine.start_workflow(uuid4(), amount_jpy=10_000_000, risk_level=RiskLevel.MEDIUM)
    return engine, wf


# ---------------------------------------------------------------------------
# select_route — boundary values
# ---------------------------------------------------------------------------


def test_select_route_boundary_exactly_5m_low():
    """Arrange: amount == 5_000_000, LOW risk. Assert: A1 (first row ceiling)."""
    assert select_route(5_000_000, RiskLevel.LOW) == "A1"


def test_select_route_boundary_over_5m_low():
    """Arrange: amount == 5_000_001, LOW risk. Assert: A2 (second row)."""
    assert select_route(5_000_001, RiskLevel.LOW) == "A2"


def test_select_route_very_large_amount_critical():
    """Arrange: amount > 500M, CRITICAL risk. Assert: D1."""
    assert select_route(600_000_000, RiskLevel.CRITICAL) == "D1"


# ---------------------------------------------------------------------------
# WorkflowEngine._load — unknown workflow raises WorkflowError
# ---------------------------------------------------------------------------


async def test_load_unknown_workflow_raises():
    """Arrange: fresh engine, unknown UUID. Act: _load. Assert: WorkflowError (line 397-402)."""
    engine = WorkflowEngine()
    with pytest.raises(WorkflowError, match="workflow not found"):
        await engine._load(uuid4())


async def test_load_uses_loader_callback_when_not_in_memory():
    """Arrange: engine with loader; wf not in _workflows. Assert: loader called (line 397-402)."""
    # Create a workflow in a *different* engine so we can pass it via loader
    src_engine = WorkflowEngine()
    cached_wf = await src_engine.start_workflow(
        uuid4(), amount_jpy=1_000_000, risk_level=RiskLevel.LOW
    )

    async def loader(wf_id):
        if wf_id == cached_wf.id:
            return cached_wf
        return None

    engine = WorkflowEngine(loader=loader)
    loaded = await engine._load(cached_wf.id)
    assert loaded.id == cached_wf.id


async def test_load_raises_when_loader_returns_none():
    """Arrange: loader always returns None. Assert: WorkflowError (line 407)."""

    async def loader(_wf_id):
        return None

    engine = WorkflowEngine(loader=loader)
    with pytest.raises(WorkflowError):
        await engine._load(uuid4())


# ---------------------------------------------------------------------------
# transition — CONDITIONAL_APPROVE
# ---------------------------------------------------------------------------


async def test_transition_conditional_approve_requires_comment():
    """Arrange: workflow. Act: CONDITIONAL_APPROVE without comment. Assert: WorkflowError."""
    engine, wf = await _start_a1()
    with pytest.raises(WorkflowError, match="condition comment"):
        await engine.transition(wf.id, WorkflowAction.CONDITIONAL_APPROVE, user_id=uuid4())


async def test_transition_conditional_approve_with_comment_advances():
    """Arrange: A1 workflow. Act: CONDITIONAL_APPROVE + comment. Assert: completed (line 233)."""
    engine, wf = await _start_a1()
    step = await engine.transition(
        wf.id,
        WorkflowAction.CONDITIONAL_APPROVE,
        user_id=uuid4(),
        comment="条件付き承認: 契約書修正後に再提出",
    )
    assert step.status == WorkflowStepStatus.APPROVED
    assert engine._workflows[wf.id].is_completed is True


# ---------------------------------------------------------------------------
# transition — HOLD
# ---------------------------------------------------------------------------


async def test_transition_hold_sets_pending_and_clears_decided_at():
    """Arrange: A1 workflow. Act: HOLD. Assert: status=PENDING, decided_at=None (line 242)."""
    engine, wf = await _start_a1()
    step = await engine.transition(wf.id, WorkflowAction.HOLD, user_id=uuid4())
    assert step.status == WorkflowStepStatus.PENDING
    assert step.decided_at is None


# ---------------------------------------------------------------------------
# transition — completed / terminal guards
# ---------------------------------------------------------------------------


async def test_transition_on_completed_workflow_raises():
    """Arrange: approve A1 (completes it). Act: transition again. Assert: WorkflowError."""
    engine, wf = await _start_a1()
    await engine.transition(wf.id, WorkflowAction.APPROVE, user_id=uuid4())
    assert engine._workflows[wf.id].is_completed is True
    with pytest.raises(WorkflowError, match="already completed"):
        await engine.transition(wf.id, WorkflowAction.APPROVE, user_id=uuid4())


async def test_transition_on_step_in_terminal_status_raises():
    """Arrange: reject workflow (step in REJECTED terminal). Act: transition completed wf.
    Assert: WorkflowError 'already completed' (line 190-191).
    """
    engine, wf = await _start_a1()
    await engine.transition(wf.id, WorkflowAction.REJECT, user_id=uuid4())
    with pytest.raises(WorkflowError, match="already completed"):
        await engine.transition(wf.id, WorkflowAction.APPROVE, user_id=uuid4())


# ---------------------------------------------------------------------------
# _advance — workflow completion when all steps approved
# ---------------------------------------------------------------------------


async def test_approve_all_steps_sets_is_completed():
    """Arrange: A1 workflow (1 step). Act: approve. Assert: is_completed=True (lines 255-258)."""
    engine, wf = await _start_a1()
    await engine.transition(wf.id, WorkflowAction.APPROVE, user_id=uuid4())
    assert engine._workflows[wf.id].is_completed is True


# ---------------------------------------------------------------------------
# _send_back — at index 0
# ---------------------------------------------------------------------------


async def test_send_back_at_first_step_does_not_go_negative():
    """Arrange: A1 at index 0. Act: SEND_BACK. Assert: current_index stays 0 (lines 265-267)."""
    engine, wf = await _start_a1()
    step = await engine.transition(wf.id, WorkflowAction.SEND_BACK, user_id=uuid4())
    assert step.status == WorkflowStepStatus.SENT_BACK
    assert engine._workflows[wf.id].current_index == 0


async def test_send_back_from_second_step_resets_previous():
    """Arrange: B1, approve step 0. Act: SEND_BACK step 1. Assert: idx=0, prev IN_PROGRESS (274)."""
    engine, wf = await _start_b1()
    assert len(wf.steps) >= 2
    # Advance to step 1
    await engine.transition(wf.id, WorkflowAction.APPROVE, user_id=uuid4())
    wf_mid = engine._workflows[wf.id]
    assert wf_mid.current_index == 1
    # Send back
    await engine.transition(wf.id, WorkflowAction.SEND_BACK, user_id=uuid4())
    wf_after = engine._workflows[wf.id]
    assert wf_after.current_index == 0
    assert wf_after.steps[0].status == WorkflowStepStatus.IN_PROGRESS


# ---------------------------------------------------------------------------
# _build_steps — unknown route code
# ---------------------------------------------------------------------------


def test_build_steps_unknown_route_raises():
    """Arrange: engine. Act: _build_steps with unknown code. Assert: WorkflowError (line 327)."""
    engine = WorkflowEngine()
    with pytest.raises(WorkflowError, match="unknown route code"):
        engine._build_steps("ZZ99")


# ---------------------------------------------------------------------------
# outside-counsel triggers
# ---------------------------------------------------------------------------


async def test_outside_counsel_triggered_by_no_liability_cap():
    """Arrange: no_liability_cap trigger. Assert: flag=True + route has counsel step (line 353)."""
    engine = WorkflowEngine()
    wf = await engine.start_workflow(
        uuid4(),
        amount_jpy=1_000_000,
        risk_level=RiskLevel.LOW,
        outside_counsel_triggers={"no_liability_cap": True},
    )
    assert wf.outside_counsel_flag is True
    assert any(s.role == "顧問弁護士確認" for s in wf.steps)


async def test_outside_counsel_triggered_by_multiple_flags():
    """Arrange: foreign_jurisdiction + litigation_signal. Assert: both in reason (lines 357-369)."""
    engine = WorkflowEngine()
    wf = await engine.start_workflow(
        uuid4(),
        amount_jpy=100_000,
        risk_level=RiskLevel.LOW,
        outside_counsel_triggers={"foreign_jurisdiction": True, "litigation_signal": True},
    )
    assert wf.outside_counsel_flag is True
    assert "foreign_jurisdiction" in (wf.outside_counsel_reason or "")
    assert "litigation_signal" in (wf.outside_counsel_reason or "")


async def test_outside_counsel_not_triggered_without_flags():
    """Arrange: no triggers, low risk, small amount. Assert: flag=False (line 377-378)."""
    engine = WorkflowEngine()
    wf = await engine.start_workflow(uuid4(), amount_jpy=1_000_000, risk_level=RiskLevel.LOW)
    assert wf.outside_counsel_flag is False
    assert wf.outside_counsel_reason is None


# ---------------------------------------------------------------------------
# Notifier callback
# ---------------------------------------------------------------------------


async def test_notifier_called_after_transition():
    """Arrange: engine with notifier callback. Act: approve. Assert: notifier invoked (line 290)."""
    notifications: list[tuple[str, str]] = []

    async def notifier(wf, step, action):
        notifications.append((str(wf.id), action))

    engine = WorkflowEngine(notifier=notifier)
    wf = await engine.start_workflow(uuid4(), amount_jpy=1_000_000, risk_level=RiskLevel.LOW)
    await engine.transition(wf.id, WorkflowAction.APPROVE, user_id=uuid4())
    assert len(notifications) == 1
    assert notifications[0][1] == "approve"


# ---------------------------------------------------------------------------
# Saver callback
# ---------------------------------------------------------------------------


async def test_saver_called_on_start_workflow():
    """Arrange: engine with saver. Act: start_workflow. Assert: saver called (line 386)."""
    saved_ids: list = []

    async def saver(wf):
        saved_ids.append(wf.id)

    engine = WorkflowEngine(saver=saver)
    wf = await engine.start_workflow(uuid4(), amount_jpy=1_000_000, risk_level=RiskLevel.LOW)
    assert wf.id in saved_ids


# ---------------------------------------------------------------------------
# Escalate
# ---------------------------------------------------------------------------


async def test_escalate_inserts_counsel_step_and_sets_flag():
    """Arrange: A1 (no counsel step). Act: escalate. Assert: step inserted + flag (line 138)."""
    engine, wf = await _start_a1()
    roles_before = [s.role for s in wf.steps]
    assert "顧問弁護士確認" not in roles_before

    result = await engine.escalate(wf.id)

    roles_after = [s.role for s in result.steps]
    assert "顧問弁護士確認" in roles_after
    assert result.outside_counsel_flag is True
    assert result.outside_counsel_reason == "manual_escalation"


async def test_escalate_does_not_duplicate_counsel_step():
    """Arrange: A1 after first escalate. Act: escalate again. Assert: exactly one counsel step."""
    engine, wf = await _start_a1()
    await engine.escalate(wf.id)
    result = await engine.escalate(wf.id)
    counsel_steps = [s for s in result.steps if s.role == "顧問弁護士確認"]
    assert len(counsel_steps) == 1


async def test_escalate_on_completed_workflow_raises():
    """Arrange: completed (rejected) workflow. Act: escalate. Assert: WorkflowError."""
    engine, wf = await _start_a1()
    await engine.transition(wf.id, WorkflowAction.REJECT, user_id=uuid4())
    with pytest.raises(WorkflowError, match="already completed"):
        await engine.escalate(wf.id)
