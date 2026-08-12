"""Unit tests for workflow_service.py (direct function calls).

Uses AsyncMock sessions to drive coverage of async function bodies
that pytest-cov cannot trace through the HTTP layer alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import WorkflowStepStatus
from app.services import workflow_service
from app.services.workflow_service import (
    _compute_instance,
    _is_full_access,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_step(
    *,
    workflow_id: int = 1,
    contract_id: int = 1,
    seq: int = 1,
    name: str = "承認",
    step_type: str = "manager_approval",
    status: str = WorkflowStepStatus.IN_PROGRESS.value,
    assignee_id: int | None = None,
    assignee_role: str | None = "admin",
    decided_at: datetime | None = None,
    decision_note: str | None = None,
    due_at: datetime | None = None,
    deleted_at: datetime | None = None,
) -> MagicMock:
    step = MagicMock()
    step.workflow_id = workflow_id
    step.contract_id = contract_id
    step.seq = seq
    step.name = name
    step.step_type = step_type
    step.status = status
    step.assignee_id = assignee_id
    step.assignee_role = assignee_role
    step.decided_at = decided_at
    step.decision_note = decision_note
    step.due_at = due_at
    step.deleted_at = deleted_at
    step.created_at = datetime.now(UTC)
    step.updated_at = datetime.now(UTC)
    return step


def _make_workflow(*, code: str = "wf_001", definition: dict | None = None) -> MagicMock:
    wf = MagicMock()
    wf.id = 1
    wf.code = code
    wf.definition = definition or {
        "steps": [
            {"seq": 1, "name": "一次承認", "step_type": "manager_approval",
             "assignee_role": "admin"},
            {"seq": 2, "name": "最終承認", "step_type": "manager_approval",
             "assignee_role": "admin"},
        ]
    }
    return wf


def _make_actor(role: str = "admin", user_id: int = 1) -> MagicMock:
    actor = MagicMock()
    actor.role = role
    actor.id = user_id
    actor.db_id = user_id  # resolved users.id (Issue #45)
    return actor


def _make_async_session() -> AsyncMock:
    """Return a mock AsyncSession with commonly needed async methods."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# _is_full_access
# ---------------------------------------------------------------------------


def test_is_full_access_admin():
    actor = _make_actor(role="admin")
    assert _is_full_access(actor) is True


def test_is_full_access_legal():
    actor = _make_actor(role="legal")
    assert _is_full_access(actor) is True


def test_is_full_access_reviewer():
    actor = _make_actor(role="reviewer")
    assert _is_full_access(actor) is True


def test_is_full_access_approver():
    actor = _make_actor(role="approver")
    assert _is_full_access(actor) is True


def test_is_full_access_auditor():
    actor = _make_actor(role="auditor")
    assert _is_full_access(actor) is True


def test_is_not_full_access_drafter():
    actor = _make_actor(role="drafter")
    assert _is_full_access(actor) is False


def test_is_not_full_access_no_role():
    actor = MagicMock(spec=[])  # no 'role' attribute
    assert _is_full_access(actor) is False


# ---------------------------------------------------------------------------
# _compute_instance
# ---------------------------------------------------------------------------


def test_compute_instance_raises_when_no_steps():
    with pytest.raises(LookupError, match="no steps found"):
        _compute_instance([])


def test_compute_instance_pending_when_all_pending():
    """Line 70: agg_status = 'pending'"""
    step = _make_step(status=WorkflowStepStatus.PENDING.value)
    inst = _compute_instance([step])
    assert inst.status == "pending"


def test_compute_instance_in_progress():
    step = _make_step(status=WorkflowStepStatus.IN_PROGRESS.value)
    inst = _compute_instance([step])
    assert inst.status == "in_progress"
    assert inst.current_seq == 1


def test_compute_instance_approved_when_all_terminal():
    s1 = _make_step(seq=1, status=WorkflowStepStatus.APPROVED.value)
    s2 = _make_step(seq=2, status=WorkflowStepStatus.SKIPPED.value)
    inst = _compute_instance([s1, s2])
    assert inst.status == "approved"
    assert inst.current_seq is None


def test_compute_instance_rejected():
    step = _make_step(
        status=WorkflowStepStatus.REJECTED.value,
        decided_at=datetime.now(UTC),
    )
    inst = _compute_instance([step])
    assert inst.status == "rejected"
    assert inst.completed_at is not None


def test_compute_instance_completed_at_max_of_decided_ats():
    """completed_at is the max of all decided_at values."""
    earlier = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    later = datetime(2026, 6, 1, 0, 0, 0, tzinfo=UTC)
    s1 = _make_step(seq=1, status=WorkflowStepStatus.APPROVED.value, decided_at=earlier)
    s2 = _make_step(seq=2, status=WorkflowStepStatus.APPROVED.value, decided_at=later)
    inst = _compute_instance([s1, s2])
    assert inst.status == "approved"
    # completed_at should equal the later value (timezone stripped)
    assert inst.completed_at == later.replace(tzinfo=None)


def test_compute_instance_id_equals_contract_id():
    step = _make_step(contract_id=42)
    inst = _compute_instance([step])
    assert inst.id == 42
    assert inst.contract_id == 42


# ---------------------------------------------------------------------------
# list_definitions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_definitions_returns_items_and_total():
    """Lines 129-133: list_definitions result tuple."""
    session = _make_async_session()
    mock_wf = _make_workflow()

    # Simulate count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1
    # Simulate rows query
    rows_result = MagicMock()
    rows_result.scalars.return_value = [mock_wf]

    session.execute = AsyncMock(side_effect=[count_result, rows_result])

    items, total = await workflow_service.list_definitions(session)
    assert total == 1
    assert items == [mock_wf]


@pytest.mark.asyncio
async def test_list_definitions_with_contract_type_filter():
    """Line 126: contract_type filter branch."""
    session = _make_async_session()
    count_result = MagicMock()
    count_result.scalar.return_value = 0
    rows_result = MagicMock()
    rows_result.scalars.return_value = []
    session.execute = AsyncMock(side_effect=[count_result, rows_result])

    items, total = await workflow_service.list_definitions(session, contract_type="工事請負契約")
    assert total == 0
    assert items == []


@pytest.mark.asyncio
async def test_list_definitions_total_none_defaults_to_zero():
    """Line 129: scalar() returns None → total defaults to 0."""
    session = _make_async_session()
    count_result = MagicMock()
    count_result.scalar.return_value = None
    rows_result = MagicMock()
    rows_result.scalars.return_value = []
    session.execute = AsyncMock(side_effect=[count_result, rows_result])

    _items, total = await workflow_service.list_definitions(session)
    assert total == 0


# ---------------------------------------------------------------------------
# create_definition
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_definition_returns_workflow():
    """Line 156: return wf."""
    session = _make_async_session()

    @dataclass
    class FakeDefinition:
        steps: list

        def model_dump(self) -> dict:
            return {"steps": self.steps}

    @dataclass
    class FakeData:
        code: str = "test_code"
        name: str = "テストフロー"
        description: str | None = None
        contract_type: str | None = None
        is_active: bool = True
        definition: Any = None

        def __post_init__(self) -> None:
            if self.definition is None:
                self.definition = FakeDefinition(steps=[])

    data = FakeData()
    result = await workflow_service.create_definition(session, data=data)
    session.add.assert_called_once()
    session.flush.assert_awaited_once()
    assert result.code == "test_code"


# ---------------------------------------------------------------------------
# start_workflow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_workflow_with_definition_code():
    """Lines 179-241: start_workflow with definition_code."""
    session = _make_async_session()
    mock_wf = _make_workflow()
    actor = _make_actor()

    # First execute: find workflow by code
    wf_result = MagicMock()
    wf_result.scalar_one_or_none.return_value = mock_wf
    # Second execute: _steps_for_contract (no existing steps)
    steps_result = MagicMock()
    steps_result.scalars.return_value = []

    session.execute = AsyncMock(side_effect=[wf_result, steps_result])

    instance = await workflow_service.start_workflow(
        session,
        contract_id=99,
        definition_code="wf_001",
        actor=actor,
    )
    assert instance.contract_id == 99
    assert instance.status in ("pending", "in_progress")


@pytest.mark.asyncio
async def test_start_workflow_without_definition_code_uses_first_active():
    """Lines 181-186: else branch (no definition_code)."""
    session = _make_async_session()
    mock_wf = _make_workflow()
    actor = _make_actor()

    wf_result = MagicMock()
    wf_result.scalar_one_or_none.return_value = mock_wf
    steps_result = MagicMock()
    steps_result.scalars.return_value = []

    session.execute = AsyncMock(side_effect=[wf_result, steps_result])

    instance = await workflow_service.start_workflow(
        session,
        contract_id=100,
        definition_code=None,
        actor=actor,
    )
    assert instance.contract_id == 100


@pytest.mark.asyncio
async def test_start_workflow_raises_when_definition_not_found():
    """Line 189: LookupError when wf is None."""
    session = _make_async_session()
    actor = _make_actor()

    not_found = MagicMock()
    not_found.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=not_found)

    with pytest.raises(LookupError, match="not found"):
        await workflow_service.start_workflow(
            session,
            contract_id=1,
            definition_code="nonexistent",
            actor=actor,
        )


@pytest.mark.asyncio
async def test_start_workflow_raises_when_already_active():
    """Line 193: ValueError when existing steps."""
    session = _make_async_session()
    mock_wf = _make_workflow()
    actor = _make_actor()
    existing_step = _make_step()

    wf_result = MagicMock()
    wf_result.scalar_one_or_none.return_value = mock_wf
    existing_steps_result = MagicMock()
    existing_steps_result.scalars.return_value = [existing_step]

    session.execute = AsyncMock(side_effect=[wf_result, existing_steps_result])

    with pytest.raises(ValueError, match="already has an active workflow"):
        await workflow_service.start_workflow(
            session,
            contract_id=1,
            definition_code="wf_001",
            actor=actor,
        )


@pytest.mark.asyncio
async def test_start_workflow_fallback_step_when_no_steps_in_definition():
    """Lines 228-238: fallback step created when definition has no steps."""
    session = _make_async_session()
    actor = _make_actor()

    mock_wf = _make_workflow(definition={"steps": []})  # empty steps
    wf_result = MagicMock()
    wf_result.scalar_one_or_none.return_value = mock_wf
    steps_result = MagicMock()
    steps_result.scalars.return_value = []

    session.execute = AsyncMock(side_effect=[wf_result, steps_result])

    instance = await workflow_service.start_workflow(
        session,
        contract_id=50,
        definition_code="wf_empty",
        actor=actor,
    )
    assert instance.status == "in_progress"  # fallback step is in_progress


@pytest.mark.asyncio
async def test_start_workflow_step_with_object_attrs():
    """Lines 207-211: step_def accessed via getattr (non-dict)."""
    session = _make_async_session()
    actor = _make_actor()

    # Step definition as object (not dict)
    step_def_obj = MagicMock()
    step_def_obj.seq = 1
    step_def_obj.name = "承認"
    step_def_obj.step_type = "manager_approval"
    step_def_obj.assignee_role = "admin"
    step_def_obj.sla_hours = 24

    mock_wf = _make_workflow(definition={"steps": [step_def_obj]})
    # Make mock_wf.definition['steps'][0] behave as a non-dict object
    # The service checks isinstance(step_def, dict)
    # Since MagicMock is not a dict, it will go to the else branch
    mock_wf.definition = {"steps": [step_def_obj]}

    wf_result = MagicMock()
    wf_result.scalar_one_or_none.return_value = mock_wf
    steps_result = MagicMock()
    steps_result.scalars.return_value = []

    session.execute = AsyncMock(side_effect=[wf_result, steps_result])

    instance = await workflow_service.start_workflow(
        session,
        contract_id=51,
        definition_code="wf_obj_steps",
        actor=actor,
    )
    assert instance.contract_id == 51


# ---------------------------------------------------------------------------
# get_instance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_instance_returns_none_when_no_steps():
    """Lines 252: returns None when no steps."""
    session = _make_async_session()
    actor = _make_actor(role="admin")

    steps_result = MagicMock()
    steps_result.scalars.return_value = []
    session.execute = AsyncMock(return_value=steps_result)

    result = await workflow_service.get_instance(session, instance_id=999, viewer=actor)
    assert result is None


@pytest.mark.asyncio
async def test_get_instance_full_access_returns_instance():
    """Lines 254-260: admin viewer gets instance."""
    session = _make_async_session()
    actor = _make_actor(role="admin")
    step = _make_step(contract_id=10, workflow_id=1)

    steps_result = MagicMock()
    steps_result.scalars.return_value = [step]
    session.execute = AsyncMock(return_value=steps_result)

    result = await workflow_service.get_instance(session, instance_id=10, viewer=actor)
    assert result is not None
    assert result.contract_id == 10


@pytest.mark.asyncio
async def test_get_instance_limited_access_own_contract():
    """Lines 255-259: drafter can see their own contract's workflow."""
    session = _make_async_session()
    actor = _make_actor(role="drafter", user_id=42)
    step = _make_step(contract_id=10, workflow_id=1)

    steps_result = MagicMock()
    steps_result.scalars.return_value = [step]
    session.execute = AsyncMock(return_value=steps_result)

    mock_contract = MagicMock()
    mock_contract.drafter_id = 42  # Same as actor id
    session.get = AsyncMock(return_value=mock_contract)

    result = await workflow_service.get_instance(session, instance_id=10, viewer=actor)
    assert result is not None


@pytest.mark.asyncio
async def test_get_instance_limited_access_other_contract():
    """Lines 258-259: drafter cannot see another user's contract."""
    session = _make_async_session()
    actor = _make_actor(role="drafter", user_id=42)
    step = _make_step(contract_id=10, workflow_id=1)

    steps_result = MagicMock()
    steps_result.scalars.return_value = [step]
    session.execute = AsyncMock(return_value=steps_result)

    mock_contract = MagicMock()
    mock_contract.drafter_id = 99  # Different user
    session.get = AsyncMock(return_value=mock_contract)

    result = await workflow_service.get_instance(session, instance_id=10, viewer=actor)
    assert result is None


@pytest.mark.asyncio
async def test_get_instance_limited_access_contract_not_found():
    """Lines 257-259: contract not found → returns None."""
    session = _make_async_session()
    actor = _make_actor(role="drafter", user_id=42)
    step = _make_step(contract_id=10, workflow_id=1)

    steps_result = MagicMock()
    steps_result.scalars.return_value = [step]
    session.execute = AsyncMock(return_value=steps_result)
    session.get = AsyncMock(return_value=None)  # contract not found

    result = await workflow_service.get_instance(session, instance_id=10, viewer=actor)
    assert result is None


# ---------------------------------------------------------------------------
# list_steps
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_steps_returns_empty_when_no_steps():
    """Line 272: returns empty list when no steps."""
    session = _make_async_session()
    actor = _make_actor(role="admin")

    steps_result = MagicMock()
    steps_result.scalars.return_value = []
    session.execute = AsyncMock(return_value=steps_result)

    result = await workflow_service.list_steps(session, instance_id=999, viewer=actor)
    assert result == []


@pytest.mark.asyncio
async def test_list_steps_admin_returns_all_steps():
    """Lines 270-279: admin viewer gets all steps."""
    session = _make_async_session()
    actor = _make_actor(role="admin")
    step1 = _make_step(seq=1)
    step2 = _make_step(seq=2, status=WorkflowStepStatus.PENDING.value)

    steps_result = MagicMock()
    steps_result.scalars.return_value = [step1, step2]
    session.execute = AsyncMock(return_value=steps_result)

    result = await workflow_service.list_steps(session, instance_id=1, viewer=actor)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_list_steps_drafter_own_contract():
    """Lines 273-278: drafter sees their own contract's steps."""
    session = _make_async_session()
    actor = _make_actor(role="drafter", user_id=7)
    step = _make_step(contract_id=5)

    steps_result = MagicMock()
    steps_result.scalars.return_value = [step]
    session.execute = AsyncMock(return_value=steps_result)

    mock_contract = MagicMock()
    mock_contract.drafter_id = 7
    session.get = AsyncMock(return_value=mock_contract)

    result = await workflow_service.list_steps(session, instance_id=5, viewer=actor)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_list_steps_drafter_other_contract_returns_empty():
    """Lines 277-278: drafter gets empty list for other's contract."""
    session = _make_async_session()
    actor = _make_actor(role="drafter", user_id=7)
    step = _make_step(contract_id=5)

    steps_result = MagicMock()
    steps_result.scalars.return_value = [step]
    session.execute = AsyncMock(return_value=steps_result)

    mock_contract = MagicMock()
    mock_contract.drafter_id = 99  # different user
    session.get = AsyncMock(return_value=mock_contract)

    result = await workflow_service.list_steps(session, instance_id=5, viewer=actor)
    assert result == []


# ---------------------------------------------------------------------------
# execute_action
# ---------------------------------------------------------------------------


def _setup_execute_action_session(
    *, active_step: Any, all_steps: list[Any]
) -> AsyncMock:
    """Create session mock for execute_action tests."""
    session = _make_async_session()
    # First _steps_for_contract call (initial fetch)
    first_result = MagicMock()
    first_result.scalars.return_value = all_steps
    # Second _steps_for_contract call (after flush, for refresh)
    second_result = MagicMock()
    second_result.scalars.return_value = all_steps
    session.execute = AsyncMock(side_effect=[first_result, second_result])
    return session


@pytest.mark.asyncio
async def test_execute_action_raises_when_no_instance():
    """Lines 291-292: LookupError when no steps."""
    session = _make_async_session()
    empty_result = MagicMock()
    empty_result.scalars.return_value = []
    session.execute = AsyncMock(return_value=empty_result)

    payload = MagicMock(action="approve")
    with pytest.raises(LookupError, match="not found"):
        await workflow_service.execute_action(
            session, instance_id=999, actor=_make_actor(), payload=payload
        )


@pytest.mark.asyncio
async def test_execute_action_raises_when_no_active_step():
    """Lines 299-300: ValueError when no in_progress step."""
    session = _make_async_session()
    step = _make_step(status=WorkflowStepStatus.APPROVED.value)
    result = MagicMock()
    result.scalars.return_value = [step]
    session.execute = AsyncMock(return_value=result)

    payload = MagicMock(action="approve")
    with pytest.raises(ValueError, match="no active step"):
        await workflow_service.execute_action(
            session, instance_id=1, actor=_make_actor(), payload=payload
        )


@pytest.mark.asyncio
async def test_execute_action_approve_single_step():
    """Lines 315-330: approve updates step status."""
    active = _make_step(seq=1, status=WorkflowStepStatus.IN_PROGRESS.value)
    active.assignee_id = None

    session = _setup_execute_action_session(active_step=active, all_steps=[active])
    actor = _make_actor(role="admin")
    payload = MagicMock(action="approve", comment="OK")

    await workflow_service.execute_action(
        session, instance_id=1, actor=actor, payload=payload
    )
    assert active.status == WorkflowStepStatus.APPROVED.value
    session.flush.assert_awaited()


@pytest.mark.asyncio
async def test_execute_action_approve_advances_to_next_step():
    """Lines 320-330: approve sets next pending step to in_progress."""
    step1 = _make_step(seq=1, status=WorkflowStepStatus.IN_PROGRESS.value)
    step1.assignee_id = None
    step2 = _make_step(seq=2, status=WorkflowStepStatus.PENDING.value)
    step2.assignee_id = None

    session = _setup_execute_action_session(active_step=step1, all_steps=[step1, step2])
    actor = _make_actor(role="admin")
    payload = MagicMock(action="approve", comment="step1 OK")

    await workflow_service.execute_action(
        session, instance_id=1, actor=actor, payload=payload
    )
    assert step1.status == WorkflowStepStatus.APPROVED.value
    assert step2.status == WorkflowStepStatus.IN_PROGRESS.value


@pytest.mark.asyncio
async def test_execute_action_reject():
    """Lines 332-336: reject sets step to REJECTED."""
    active = _make_step(seq=1, status=WorkflowStepStatus.IN_PROGRESS.value)
    active.assignee_id = None

    session = _setup_execute_action_session(active_step=active, all_steps=[active])
    actor = _make_actor(role="admin")
    payload = MagicMock(action="reject", comment="NG")

    await workflow_service.execute_action(
        session, instance_id=1, actor=actor, payload=payload
    )
    assert active.status == WorkflowStepStatus.REJECTED.value


@pytest.mark.asyncio
async def test_execute_action_return_alias():
    """Lines 332-336: 'return' is alias for reject."""
    active = _make_step(seq=1, status=WorkflowStepStatus.IN_PROGRESS.value)
    active.assignee_id = None

    session = _setup_execute_action_session(active_step=active, all_steps=[active])
    actor = _make_actor(role="admin")
    payload = MagicMock(action="return", comment="差戻し")

    await workflow_service.execute_action(
        session, instance_id=1, actor=actor, payload=payload
    )
    assert active.status == WorkflowStepStatus.REJECTED.value


@pytest.mark.asyncio
async def test_execute_action_send_back():
    """Lines 338-349: send_back reactivates target step."""
    step1 = _make_step(seq=1, status=WorkflowStepStatus.APPROVED.value)
    step1.assignee_id = None
    step2 = _make_step(seq=2, status=WorkflowStepStatus.IN_PROGRESS.value)
    step2.assignee_id = None

    session = _setup_execute_action_session(active_step=step2, all_steps=[step1, step2])
    actor = _make_actor(role="admin")
    payload = MagicMock(action="send_back", comment="差戻し", to_seq=1)

    await workflow_service.execute_action(
        session, instance_id=1, actor=actor, payload=payload
    )
    assert step2.status == WorkflowStepStatus.SENT_BACK.value
    assert step1.status == WorkflowStepStatus.IN_PROGRESS.value


@pytest.mark.asyncio
async def test_execute_action_send_back_invalid_seq_raises():
    """Lines 341-342: ValueError when to_seq not found."""
    active = _make_step(seq=2, status=WorkflowStepStatus.IN_PROGRESS.value)
    active.assignee_id = None

    session = _setup_execute_action_session(active_step=active, all_steps=[active])
    actor = _make_actor(role="admin")
    payload = MagicMock(action="send_back", comment="差戻し", to_seq=999)

    with pytest.raises(ValueError, match="not found"):
        await workflow_service.execute_action(
            session, instance_id=1, actor=actor, payload=payload
        )


@pytest.mark.asyncio
async def test_execute_action_delegate():
    """Lines 351-356: delegate sets assignee_id."""
    active = _make_step(seq=1, status=WorkflowStepStatus.IN_PROGRESS.value)
    active.assignee_id = None

    session = _setup_execute_action_session(active_step=active, all_steps=[active])
    actor = _make_actor(role="admin")
    payload = MagicMock(action="delegate", to_user_id=99)

    await workflow_service.execute_action(
        session, instance_id=1, actor=actor, payload=payload
    )
    assert active.assignee_id == 99


@pytest.mark.asyncio
async def test_execute_action_delegate_no_user_id_raises():
    """Lines 353-354: ValueError when to_user_id is None for delegate."""
    active = _make_step(seq=1, status=WorkflowStepStatus.IN_PROGRESS.value)
    active.assignee_id = None

    session = _setup_execute_action_session(active_step=active, all_steps=[active])
    actor = _make_actor(role="admin")
    payload = MagicMock(action="delegate", to_user_id=None)

    with pytest.raises(ValueError, match="to_user_id is required"):
        await workflow_service.execute_action(
            session, instance_id=1, actor=actor, payload=payload
        )


@pytest.mark.asyncio
async def test_execute_action_permission_denied_wrong_assignee():
    """Lines 305-306: PermissionError when actor_id != assignee_id."""
    active = _make_step(seq=1, status=WorkflowStepStatus.IN_PROGRESS.value)
    active.assignee_id = 100  # someone else

    session = _setup_execute_action_session(active_step=active, all_steps=[active])
    actor = _make_actor(role="drafter", user_id=99)  # different id, not full-access
    payload = MagicMock(action="approve")

    with pytest.raises(PermissionError, match="not the assignee"):
        await workflow_service.execute_action(
            session, instance_id=1, actor=actor, payload=payload
        )


@pytest.mark.asyncio
async def test_execute_action_permission_denied_wrong_role():
    """Lines 308-310: PermissionError when actor role doesn't match assignee_role."""
    active = _make_step(seq=1, status=WorkflowStepStatus.IN_PROGRESS.value, assignee_role="admin")
    active.assignee_id = None

    session = _setup_execute_action_session(active_step=active, all_steps=[active])
    actor = _make_actor(role="drafter", user_id=99)
    payload = MagicMock(action="approve")

    with pytest.raises(PermissionError, match="not authorised"):
        await workflow_service.execute_action(
            session, instance_id=1, actor=actor, payload=payload
        )


@pytest.mark.asyncio
async def test_execute_action_assignee_can_act():
    """Lines 304-305: assignee_id matches actor → allowed."""
    active = _make_step(seq=1, status=WorkflowStepStatus.IN_PROGRESS.value)
    active.assignee_id = 42

    session = _setup_execute_action_session(active_step=active, all_steps=[active])
    actor = _make_actor(role="drafter", user_id=42)  # matches assignee_id
    payload = MagicMock(action="approve", comment="OK")

    await workflow_service.execute_action(
        session, instance_id=1, actor=actor, payload=payload
    )
    assert active.status == WorkflowStepStatus.APPROVED.value
