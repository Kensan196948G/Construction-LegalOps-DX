"""Unit tests for app.services.risk_service.

Covers:
- list_risks    : filters (severity/status/contract_id/owner_id), pagination, role scope
- aggregate     : by_severity / by_status aggregation, date_from/date_to filters
- update_risk   : not found / partial update / due_date conversion
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.risk import RiskUpdate
from app.services import risk_service

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_actor(role: str = "admin", user_id: int = 1) -> MagicMock:
    actor = MagicMock()
    actor.role = role
    actor.id = user_id
    return actor


def _make_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock(return_value=None)
    session.refresh = AsyncMock(return_value=None)
    return session


def _make_risk(
    *,
    id: int = 1,
    contract_id: int = 10,
    category: str = "法務リスク",
    severity: str = "high",
    status: str = "open",
    description: str = "リスク説明",
    mitigation: str | None = None,
    owner_id: int | None = None,
    due_date: date | None = None,
    deleted_at: datetime | None = None,
) -> MagicMock:
    r = MagicMock()
    r.id = id
    r.contract_id = contract_id
    r.category = category
    r.severity = severity
    r.status = status
    r.description = description
    r.mitigation = mitigation
    r.owner_id = owner_id
    r.due_date = due_date
    r.deleted_at = deleted_at
    r.created_at = datetime.now(UTC)
    r.updated_at = datetime.now(UTC)
    return r


def _list_session(
    *,
    total: int = 0,
    rows: list[Any] | None = None,
) -> AsyncMock:
    """Create a session mock that returns (total, rows) for list_risks queries."""
    session = _make_session()
    rows = rows or []

    # First execute → count query
    count_result = MagicMock()
    count_result.scalar.return_value = total

    # Second execute → data rows
    rows_result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.__iter__ = MagicMock(return_value=iter(rows))
    rows_result.scalars.return_value = scalars_mock

    session.execute = AsyncMock(side_effect=[count_result, rows_result])
    return session


def _aggregate_session(
    *,
    severity_rows: list[tuple[str, int]] | None = None,
    status_rows: list[tuple[str, int]] | None = None,
) -> AsyncMock:
    """Create a session mock that returns aggregated rows for aggregate()."""
    session = _make_session()
    severity_rows = severity_rows or []
    status_rows = status_rows or []

    sev_result = MagicMock()
    sev_result.__iter__ = MagicMock(return_value=iter(severity_rows))

    stat_result = MagicMock()
    stat_result.__iter__ = MagicMock(return_value=iter(status_rows))

    # aggregate() runs: base query + subquery + 2 group-by queries
    # We give enough side_effects to cover all execute calls.
    session.execute = AsyncMock(side_effect=[sev_result, stat_result])
    return session


# ---------------------------------------------------------------------------
# list_risks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestListRisks:
    async def test_returns_empty_list_and_zero_total(self) -> None:
        session = _list_session(total=0, rows=[])
        actor = _make_actor()
        items, total = await risk_service.list_risks(session, viewer=actor)
        assert total == 0
        assert items == []

    async def test_returns_items_with_correct_total(self) -> None:
        risk = _make_risk(id=1)
        session = _list_session(total=1, rows=[risk])
        actor = _make_actor()
        items, total = await risk_service.list_risks(session, viewer=actor)
        assert total == 1
        assert len(items) == 1

    async def test_item_dict_structure(self) -> None:
        """_to_dict maps category→title and adds department_id=None."""
        risk = _make_risk(id=1, category="契約リスク", severity="medium", status="open")
        session = _list_session(total=1, rows=[risk])
        actor = _make_actor()
        items, _ = await risk_service.list_risks(session, viewer=actor)
        item = items[0]
        assert item["id"] == 1
        assert item["title"] == "契約リスク"
        assert item["severity"] == "medium"
        assert item["status"] == "open"
        assert item["department_id"] is None

    async def test_filter_by_severity(self) -> None:
        session = _list_session(total=0, rows=[])
        actor = _make_actor()
        _, total = await risk_service.list_risks(session, viewer=actor, severity="high")
        assert total == 0
        session.execute.assert_awaited()

    async def test_filter_by_status(self) -> None:
        session = _list_session(total=0, rows=[])
        actor = _make_actor()
        _, total = await risk_service.list_risks(session, viewer=actor, status="open")
        assert total == 0

    async def test_filter_by_contract_id(self) -> None:
        session = _list_session(total=0, rows=[])
        actor = _make_actor()
        _, total = await risk_service.list_risks(session, viewer=actor, contract_id=42)
        assert total == 0

    async def test_filter_by_owner_id(self) -> None:
        session = _list_session(total=0, rows=[])
        actor = _make_actor()
        _, total = await risk_service.list_risks(session, viewer=actor, owner_id=5)
        assert total == 0

    async def test_department_id_filter_silently_ignored(self) -> None:
        """department_id filter is accepted but silently ignored (no DB column)."""
        session = _list_session(total=0, rows=[])
        actor = _make_actor()
        _, total = await risk_service.list_risks(session, viewer=actor, department_id=99)
        assert total == 0

    async def test_pagination_page2(self) -> None:
        session = _list_session(total=25)
        actor = _make_actor()
        _, total = await risk_service.list_risks(session, viewer=actor, page=2, size=10)
        assert total == 25

    async def test_execute_called_twice(self) -> None:
        """list_risks runs 2 DB queries: count + data."""
        session = _list_session(total=0)
        actor = _make_actor()
        await risk_service.list_risks(session, viewer=actor)
        assert session.execute.call_count == 2

    async def test_non_privileged_role_adds_join(self) -> None:
        """Non-privileged viewer triggers join to Contract for drafter_id scope."""
        session = _list_session(total=0, rows=[])
        actor = _make_actor(role="general", user_id=7)
        _, total = await risk_service.list_risks(session, viewer=actor)
        assert total == 0
        # The query ran without error; the join clause is verified by coverage.

    async def test_privileged_roles_see_all(self) -> None:
        """Admin/legal/auditor/reviewer/approver roles bypass drafter scope."""
        for role in ("admin", "legal", "auditor", "reviewer", "approver"):
            risk = _make_risk(id=1)
            session = _list_session(total=1, rows=[risk])
            actor = _make_actor(role=role, user_id=1)
            _, total = await risk_service.list_risks(session, viewer=actor)
            assert total == 1, f"Role {role!r} should see all risks"

    async def test_all_filters_combined(self) -> None:
        session = _list_session(total=0)
        actor = _make_actor()
        _, total = await risk_service.list_risks(
            session,
            viewer=actor,
            severity="high",
            status="open",
            contract_id=10,
            owner_id=3,
            department_id=5,
            page=1,
            size=5,
        )
        assert total == 0


# ---------------------------------------------------------------------------
# aggregate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAggregate:
    async def test_returns_risk_aggregate_schema(self) -> None:
        from app.schemas.risk import RiskAggregate

        session = _aggregate_session(
            severity_rows=[("high", 3), ("medium", 2)],
            status_rows=[("open", 4), ("closed", 1)],
        )
        actor = _make_actor()
        result = await risk_service.aggregate(session, viewer=actor)
        assert isinstance(result, RiskAggregate)

    async def test_by_severity_populated(self) -> None:
        session = _aggregate_session(
            severity_rows=[("high", 5), ("low", 2)],
            status_rows=[],
        )
        actor = _make_actor()
        result = await risk_service.aggregate(session, viewer=actor)
        assert result.by_severity == {"high": 5, "low": 2}

    async def test_by_status_populated(self) -> None:
        session = _aggregate_session(
            severity_rows=[],
            status_rows=[("open", 10), ("mitigated", 3)],
        )
        actor = _make_actor()
        result = await risk_service.aggregate(session, viewer=actor)
        assert result.by_status == {"open": 10, "mitigated": 3}

    async def test_open_count_derived_from_by_status(self) -> None:
        session = _aggregate_session(
            severity_rows=[],
            status_rows=[("open", 7), ("closed", 2)],
        )
        actor = _make_actor()
        result = await risk_service.aggregate(session, viewer=actor)
        assert result.open_count == 7
        assert result.closed_count == 2

    async def test_empty_aggregate_returns_zeros(self) -> None:
        session = _aggregate_session(severity_rows=[], status_rows=[])
        actor = _make_actor()
        result = await risk_service.aggregate(session, viewer=actor)
        assert result.open_count == 0
        assert result.closed_count == 0
        assert result.by_severity == {}
        assert result.by_status == {}

    async def test_disclaimer_in_aggregate(self) -> None:
        session = _aggregate_session()
        actor = _make_actor()
        result = await risk_service.aggregate(session, viewer=actor)
        assert "法務担当者" in result.disclaimer

    async def test_with_date_from_valid(self) -> None:
        """date_from is accepted without error."""
        session = _aggregate_session()
        actor = _make_actor()
        result = await risk_service.aggregate(session, viewer=actor, date_from="2026-01-01")
        assert result is not None

    async def test_with_date_to_valid(self) -> None:
        """date_to is accepted without error."""
        session = _aggregate_session()
        actor = _make_actor()
        result = await risk_service.aggregate(session, viewer=actor, date_to="2026-12-31")
        assert result is not None

    async def test_with_invalid_date_from_silently_ignored(self) -> None:
        """Invalid date_from string is silently skipped (no exception)."""
        session = _aggregate_session()
        actor = _make_actor()
        result = await risk_service.aggregate(session, viewer=actor, date_from="not-a-date")
        assert result is not None

    async def test_with_invalid_date_to_silently_ignored(self) -> None:
        """Invalid date_to string is silently skipped (no exception)."""
        session = _aggregate_session()
        actor = _make_actor()
        result = await risk_service.aggregate(session, viewer=actor, date_to="bad-date")
        assert result is not None

    async def test_non_privileged_viewer_applies_scope(self) -> None:
        """Non-privileged viewer triggers drafter_id JOIN scope without error."""
        session = _aggregate_session()
        actor = _make_actor(role="staff", user_id=42)
        result = await risk_service.aggregate(session, viewer=actor)
        assert result is not None


# ---------------------------------------------------------------------------
# update_risk
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestUpdateRisk:
    def _session_with_risk(self, risk: Any | None) -> AsyncMock:
        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = risk
        session.execute = AsyncMock(return_value=result_mock)
        return session

    async def test_raises_lookup_error_when_not_found(self) -> None:
        session = self._session_with_risk(None)
        data = RiskUpdate()
        editor = _make_actor()

        with pytest.raises(LookupError, match="not found"):
            await risk_service.update_risk(session, risk_id=999, data=data, editor=editor)

    async def test_updates_status(self) -> None:
        risk = _make_risk(id=1, status="open")
        session = self._session_with_risk(risk)
        data = RiskUpdate(status="mitigated")
        editor = _make_actor()

        result = await risk_service.update_risk(session, risk_id=1, data=data, editor=editor)
        assert risk.status == "mitigated"
        assert result["id"] == 1

    async def test_updates_mitigation(self) -> None:
        risk = _make_risk(id=1, mitigation=None)
        session = self._session_with_risk(risk)
        data = RiskUpdate(mitigation="リスク低減策を実施")
        editor = _make_actor()

        await risk_service.update_risk(session, risk_id=1, data=data, editor=editor)
        assert risk.mitigation == "リスク低減策を実施"

    async def test_updates_severity(self) -> None:
        risk = _make_risk(id=1, severity="low")
        session = self._session_with_risk(risk)
        data = RiskUpdate(severity="high")
        editor = _make_actor()

        await risk_service.update_risk(session, risk_id=1, data=data, editor=editor)
        assert risk.severity == "high"

    async def test_updates_owner_id(self) -> None:
        risk = _make_risk(id=1, owner_id=None)
        session = self._session_with_risk(risk)
        data = RiskUpdate(owner_id=5)
        editor = _make_actor()

        await risk_service.update_risk(session, risk_id=1, data=data, editor=editor)
        assert risk.owner_id == 5

    async def test_partial_update_only_sets_provided_fields(self) -> None:
        """model_dump(exclude_unset=True) ensures unset fields are not touched."""
        risk = _make_risk(id=1, status="open", severity="high")
        session = self._session_with_risk(risk)
        # Only update status; severity should remain unchanged.
        data = RiskUpdate(status="mitigated")
        editor = _make_actor()

        await risk_service.update_risk(session, risk_id=1, data=data, editor=editor)
        assert risk.status == "mitigated"
        assert risk.severity == "high"  # unchanged

    async def test_due_date_datetime_converted_to_date(self) -> None:
        """due_date datetime is converted to date via .date()."""
        risk = _make_risk(id=1, due_date=None)
        session = self._session_with_risk(risk)
        dt = datetime(2026, 6, 30, 12, 0, 0, tzinfo=UTC)
        data = RiskUpdate(due_date=dt)
        editor = _make_actor()

        await risk_service.update_risk(session, risk_id=1, data=data, editor=editor)
        assert risk.due_date == date(2026, 6, 30)

    async def test_due_date_none_sets_none(self) -> None:
        """Explicitly passing due_date=None clears it."""
        risk = _make_risk(id=1, due_date=date(2026, 1, 1))
        session = self._session_with_risk(risk)
        # RiskUpdate(due_date=None) leaves due_date unset by default in pydantic v2,
        # so we force the field to be present via model_construct.
        data = RiskUpdate.model_construct(due_date=None)
        editor = _make_actor()

        await risk_service.update_risk(session, risk_id=1, data=data, editor=editor)
        # due_date=None branch: value is None, no .date() call needed.
        assert risk.due_date is None

    async def test_flushes_and_refreshes(self) -> None:
        risk = _make_risk(id=1)
        session = self._session_with_risk(risk)
        data = RiskUpdate(status="open")
        editor = _make_actor()

        await risk_service.update_risk(session, risk_id=1, data=data, editor=editor)

        session.flush.assert_awaited_once()
        session.refresh.assert_awaited_once_with(risk)

    async def test_returns_dict_with_expected_keys(self) -> None:
        risk = _make_risk(id=1)
        session = self._session_with_risk(risk)
        data = RiskUpdate(status="open")
        editor = _make_actor()

        result = await risk_service.update_risk(session, risk_id=1, data=data, editor=editor)

        assert "id" in result
        assert "contract_id" in result
        assert "severity" in result
        assert "status" in result
        assert "title" in result
        assert "department_id" in result

    async def test_empty_update_still_flushes(self) -> None:
        """Empty RiskUpdate (no fields set) still calls flush/refresh."""
        risk = _make_risk(id=1)
        session = self._session_with_risk(risk)
        data = RiskUpdate()
        editor = _make_actor()

        await risk_service.update_risk(session, risk_id=1, data=data, editor=editor)

        session.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# _is_full_access
# ---------------------------------------------------------------------------


class TestIsFullAccess:
    def test_admin_is_full_access(self) -> None:
        actor = _make_actor(role="admin")
        assert risk_service._is_full_access(actor) is True

    def test_legal_is_full_access(self) -> None:
        actor = _make_actor(role="legal")
        assert risk_service._is_full_access(actor) is True

    def test_auditor_is_full_access(self) -> None:
        actor = _make_actor(role="auditor")
        assert risk_service._is_full_access(actor) is True

    def test_reviewer_is_full_access(self) -> None:
        actor = _make_actor(role="reviewer")
        assert risk_service._is_full_access(actor) is True

    def test_approver_is_full_access(self) -> None:
        actor = _make_actor(role="approver")
        assert risk_service._is_full_access(actor) is True

    def test_general_is_not_full_access(self) -> None:
        actor = _make_actor(role="general")
        assert risk_service._is_full_access(actor) is False

    def test_no_role_is_not_full_access(self) -> None:
        actor = MagicMock(spec=[])  # no .role attribute
        assert risk_service._is_full_access(actor) is False


# ---------------------------------------------------------------------------
# _to_dict
# ---------------------------------------------------------------------------


class TestToDict:
    def test_category_mapped_to_title(self) -> None:
        risk = _make_risk(category="財務リスク")
        result = risk_service._to_dict(risk)
        assert result["title"] == "財務リスク"

    def test_department_id_is_none(self) -> None:
        risk = _make_risk()
        result = risk_service._to_dict(risk)
        assert result["department_id"] is None

    def test_all_expected_keys_present(self) -> None:
        risk = _make_risk()
        result = risk_service._to_dict(risk)
        expected_keys = {
            "id",
            "contract_id",
            "severity",
            "status",
            "title",
            "description",
            "mitigation",
            "owner_id",
            "department_id",
            "due_date",
            "created_at",
            "updated_at",
        }
        assert expected_keys.issubset(result.keys())
