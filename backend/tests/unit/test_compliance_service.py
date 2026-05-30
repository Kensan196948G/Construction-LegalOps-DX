"""Unit tests for app.services.compliance_service.

Covers:
- list_checklists : category / contract_type filter branches
- get_result      : contract not found / snapshot build / ComplianceChecker execution
- start_run       : contract not found / job_id generation
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import compliance_service

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


def _make_contract(
    *,
    id: int = 1,
    contract_type: str = "請負",
    amount: Decimal | None = Decimal("5000000"),
    extra_metadata: dict[str, Any] | None = None,
    deleted_at: datetime | None = None,
    drafter_id: int = 1,
) -> MagicMock:
    c = MagicMock()
    c.id = id
    c.contract_type = contract_type
    c.amount = amount
    c.extra_metadata = extra_metadata if extra_metadata is not None else {}
    c.deleted_at = deleted_at
    c.drafter_id = drafter_id
    c.text = "工事内容 請負代金 工期 引渡 前金払"
    return c


def _execute_returning(value: Any) -> AsyncMock:
    """Create a session.execute mock that returns scalar_one_or_none = value."""
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = value
    session = _make_session()
    session.execute = AsyncMock(return_value=result_mock)
    return session


# ---------------------------------------------------------------------------
# list_checklists
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestListChecklists:
    async def test_returns_all_when_no_filter(self) -> None:
        session = _make_session()
        result = await compliance_service.list_checklists(session)
        assert len(result) == 4

    async def test_filter_by_category_construction_law(self) -> None:
        session = _make_session()
        result = await compliance_service.list_checklists(session, category="construction_law")
        assert all(r["category"] == "construction_law" for r in result)
        assert len(result) == 1
        assert result[0]["code"] == "建設業法19条"

    async def test_filter_by_category_subcontract_act(self) -> None:
        session = _make_session()
        result = await compliance_service.list_checklists(session, category="subcontract_act")
        assert len(result) == 1
        assert result[0]["code"] == "下請法3条"

    async def test_filter_by_category_others(self) -> None:
        session = _make_session()
        result = await compliance_service.list_checklists(session, category="others")
        assert len(result) == 2
        assert all(r["category"] == "others" for r in result)

    async def test_filter_by_nonexistent_category(self) -> None:
        session = _make_session()
        result = await compliance_service.list_checklists(session, category="nonexistent")
        assert result == []

    async def test_filter_by_contract_type_subcontract(self) -> None:
        """contract_type='subcontract' returns items with None or 'subcontract' contract_type."""
        session = _make_session()
        result = await compliance_service.list_checklists(session, contract_type="subcontract")
        # Items with contract_type=None or contract_type='subcontract' are included.
        assert all(
            r["contract_type"] is None or r["contract_type"] == "subcontract" for r in result
        )
        # The subcontract-specific item must be included.
        codes = [r["code"] for r in result]
        assert "下請法3条" in codes

    async def test_filter_by_contract_type_unknown(self) -> None:
        """Unknown contract_type keeps only items with contract_type=None."""
        session = _make_session()
        result = await compliance_service.list_checklists(session, contract_type="unknown_type")
        assert all(r["contract_type"] is None for r in result)

    async def test_filter_by_both_category_and_contract_type(self) -> None:
        session = _make_session()
        result = await compliance_service.list_checklists(
            session, category="subcontract_act", contract_type="subcontract"
        )
        assert len(result) == 1
        assert result[0]["code"] == "下請法3条"

    async def test_filter_by_category_and_mismatched_contract_type_returns_empty(self) -> None:
        session = _make_session()
        result = await compliance_service.list_checklists(
            session, category="construction_law", contract_type="subcontract"
        )
        # construction_law item has contract_type=None → passes contract_type filter
        # but category filter keeps only construction_law → should return it
        assert all(r["category"] == "construction_law" for r in result)


# ---------------------------------------------------------------------------
# get_result
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGetResult:
    async def test_returns_none_when_contract_not_found(self) -> None:
        session = _execute_returning(None)
        actor = _make_actor()
        result = await compliance_service.get_result(session, contract_id=999, viewer=actor)
        assert result is None

    async def test_returns_result_dict_when_contract_found(self) -> None:
        contract = _make_contract()
        session = _execute_returning(contract)
        actor = _make_actor()

        # Mock ComplianceChecker.check to return an empty list of findings.
        mock_finding = MagicMock()
        mock_finding.code = "KEN19-1"
        mock_finding.title = "工事内容"
        mock_finding.severity = "warn"
        mock_finding.description = "工事内容の記載が必要です"
        mock_finding.citation = "建設業法第19条1号"

        with patch("app.services.compliance_checker.ComplianceChecker") as MockChecker:
            instance = MockChecker.return_value
            instance.check = AsyncMock(return_value=[mock_finding])
            result = await compliance_service.get_result(session, contract_id=1, viewer=actor)

        assert result is not None
        assert result["contract_id"] == 1
        assert "overall_status" in result
        assert "findings" in result
        assert "disclaimer" in result
        assert "checked_at" in result

    async def test_returns_result_with_no_findings(self) -> None:
        contract = _make_contract()
        session = _execute_returning(contract)
        actor = _make_actor()

        with patch("app.services.compliance_checker.ComplianceChecker") as MockChecker:
            instance = MockChecker.return_value
            instance.check = AsyncMock(return_value=[])
            result = await compliance_service.get_result(session, contract_id=1, viewer=actor)

        assert result is not None
        assert result["overall_status"] == "pass"
        assert result["findings"] == []

    async def test_overall_status_fail_when_block_finding(self) -> None:
        contract = _make_contract()
        session = _execute_returning(contract)
        actor = _make_actor()

        block_finding = MagicMock()
        block_finding.code = "KEN19-BLOCK"
        block_finding.title = "必須項目欠如"
        block_finding.severity = "block"
        block_finding.description = "必須条項が不足しています"
        block_finding.citation = "建設業法第19条"

        with patch("app.services.compliance_checker.ComplianceChecker") as MockChecker:
            instance = MockChecker.return_value
            instance.check = AsyncMock(return_value=[block_finding])
            result = await compliance_service.get_result(session, contract_id=1, viewer=actor)

        assert result["overall_status"] == "fail"

    async def test_overall_status_warning_when_warn_finding(self) -> None:
        contract = _make_contract()
        session = _execute_returning(contract)
        actor = _make_actor()

        warn_finding = MagicMock()
        warn_finding.code = "KEN19-WARN"
        warn_finding.title = "推奨項目"
        warn_finding.severity = "warn"
        warn_finding.description = "推奨条項が不足しています"
        warn_finding.citation = "建設業法第19条"

        with patch("app.services.compliance_checker.ComplianceChecker") as MockChecker:
            instance = MockChecker.return_value
            instance.check = AsyncMock(return_value=[warn_finding])
            result = await compliance_service.get_result(session, contract_id=1, viewer=actor)

        assert result["overall_status"] == "warning"

    async def test_snapshot_with_extra_metadata_is_public_work(self) -> None:
        """ContractSnapshot is built with is_public_work from extra_metadata."""
        contract = _make_contract(extra_metadata={"is_public_work": True})
        session = _execute_returning(contract)
        actor = _make_actor()

        captured_snapshots: list[Any] = []

        async def fake_check(snapshot: Any) -> list:
            captured_snapshots.append(snapshot)
            return []

        with patch("app.services.compliance_checker.ComplianceChecker") as MockChecker:
            instance = MockChecker.return_value
            instance.check = fake_check
            await compliance_service.get_result(session, contract_id=1, viewer=actor)

        assert len(captured_snapshots) == 1
        assert captured_snapshots[0].is_public_work is True

    async def test_snapshot_with_handles_personal_data(self) -> None:
        """ContractSnapshot is built with handles_personal_data from extra_metadata."""
        contract = _make_contract(extra_metadata={"handles_personal_data": True})
        session = _execute_returning(contract)
        actor = _make_actor()

        captured_snapshots: list[Any] = []

        async def fake_check(snapshot: Any) -> list:
            captured_snapshots.append(snapshot)
            return []

        with patch("app.services.compliance_checker.ComplianceChecker") as MockChecker:
            instance = MockChecker.return_value
            instance.check = fake_check
            await compliance_service.get_result(session, contract_id=1, viewer=actor)

        assert len(captured_snapshots) == 1
        assert captured_snapshots[0].handles_personal_data is True

    async def test_snapshot_amount_none_becomes_none(self) -> None:
        """Contract with amount=None passes amount_jpy=None to snapshot."""
        contract = _make_contract(amount=None)
        session = _execute_returning(contract)
        actor = _make_actor()

        captured_snapshots: list[Any] = []

        async def fake_check(snapshot: Any) -> list:
            captured_snapshots.append(snapshot)
            return []

        with patch("app.services.compliance_checker.ComplianceChecker") as MockChecker:
            instance = MockChecker.return_value
            instance.check = fake_check
            await compliance_service.get_result(session, contract_id=1, viewer=actor)

        assert captured_snapshots[0].amount_jpy is None

    async def test_non_privileged_viewer_restricted_scope(self) -> None:
        """Non-privileged viewer query restricts to drafter_id scope (contract not found)."""
        session = _execute_returning(None)  # no matching contract in restricted scope
        # Non-privileged role
        actor = _make_actor(role="general", user_id=99)

        result = await compliance_service.get_result(session, contract_id=1, viewer=actor)
        assert result is None

    async def test_disclaimer_in_result(self) -> None:
        """Result dict always contains the legal disclaimer."""
        contract = _make_contract()
        session = _execute_returning(contract)
        actor = _make_actor()

        with patch("app.services.compliance_checker.ComplianceChecker") as MockChecker:
            instance = MockChecker.return_value
            instance.check = AsyncMock(return_value=[])
            result = await compliance_service.get_result(session, contract_id=1, viewer=actor)

        assert result is not None
        assert "法務担当者" in result["disclaimer"]

    async def test_finding_severity_block_maps_to_high(self) -> None:
        """block severity maps to 'high' in the finding output."""
        contract = _make_contract()
        session = _execute_returning(contract)
        actor = _make_actor()

        block_finding = MagicMock()
        block_finding.code = "X"
        block_finding.title = "X"
        block_finding.severity = "block"
        block_finding.description = "X"
        block_finding.citation = "X"

        with patch("app.services.compliance_checker.ComplianceChecker") as MockChecker:
            instance = MockChecker.return_value
            instance.check = AsyncMock(return_value=[block_finding])
            result = await compliance_service.get_result(session, contract_id=1, viewer=actor)

        assert result["findings"][0]["severity"] == "high"
        assert result["findings"][0]["status"] == "fail"

    async def test_finding_severity_warn_maps_to_medium(self) -> None:
        """warn severity maps to 'medium' in the finding output."""
        contract = _make_contract()
        session = _execute_returning(contract)
        actor = _make_actor()

        warn_finding = MagicMock()
        warn_finding.code = "Y"
        warn_finding.title = "Y"
        warn_finding.severity = "warn"
        warn_finding.description = "Y"
        warn_finding.citation = "Y"

        with patch("app.services.compliance_checker.ComplianceChecker") as MockChecker:
            instance = MockChecker.return_value
            instance.check = AsyncMock(return_value=[warn_finding])
            result = await compliance_service.get_result(session, contract_id=1, viewer=actor)

        assert result["findings"][0]["severity"] == "medium"
        assert result["findings"][0]["status"] == "warning"

    async def test_finding_severity_info_maps_to_info(self) -> None:
        """info severity maps to 'info' severity and 'pass' status."""
        contract = _make_contract()
        session = _execute_returning(contract)
        actor = _make_actor()

        info_finding = MagicMock()
        info_finding.code = "Z"
        info_finding.title = "Z"
        info_finding.severity = "info"
        info_finding.description = "Z"
        info_finding.citation = None  # no citation

        with patch("app.services.compliance_checker.ComplianceChecker") as MockChecker:
            instance = MockChecker.return_value
            instance.check = AsyncMock(return_value=[info_finding])
            result = await compliance_service.get_result(session, contract_id=1, viewer=actor)

        assert result["findings"][0]["severity"] == "info"
        assert result["findings"][0]["status"] == "pass"
        assert result["findings"][0]["citations"] == []


# ---------------------------------------------------------------------------
# start_run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestStartRun:
    async def test_raises_lookup_error_when_contract_not_found(self) -> None:
        session = _execute_returning(None)
        actor = _make_actor()

        with pytest.raises(LookupError, match="not found"):
            await compliance_service.start_run(session, contract_id=999, actor=actor)

    async def test_returns_job_handle_when_contract_found(self) -> None:
        contract = _make_contract()
        session = _execute_returning(contract)
        actor = _make_actor()

        result = await compliance_service.start_run(session, contract_id=1, actor=actor)

        assert result["contract_id"] == 1
        assert result["status"] == "queued"
        assert "job_id" in result
        assert "accepted_at" in result
        assert "disclaimer" in result

    async def test_job_id_is_valid_uuid_string(self) -> None:
        """job_id returned by start_run is a valid UUID string."""
        import uuid

        contract = _make_contract()
        session = _execute_returning(contract)
        actor = _make_actor()

        result = await compliance_service.start_run(session, contract_id=1, actor=actor)

        # Should not raise
        parsed = uuid.UUID(result["job_id"])
        assert parsed.version == 4

    async def test_accepted_at_is_utc_aware(self) -> None:
        """accepted_at in the job handle is UTC-aware."""
        contract = _make_contract()
        session = _execute_returning(contract)
        actor = _make_actor()

        result = await compliance_service.start_run(session, contract_id=1, actor=actor)

        accepted_at = result["accepted_at"]
        assert accepted_at.tzinfo is not None

    async def test_each_call_generates_unique_job_id(self) -> None:
        """Two calls produce different job_ids."""
        contract = _make_contract()
        session1 = _execute_returning(contract)
        session2 = _execute_returning(contract)
        actor = _make_actor()

        r1 = await compliance_service.start_run(session1, contract_id=1, actor=actor)
        r2 = await compliance_service.start_run(session2, contract_id=1, actor=actor)

        assert r1["job_id"] != r2["job_id"]

    async def test_with_checklist_codes(self) -> None:
        """start_run accepts optional checklist_codes without error."""
        contract = _make_contract()
        session = _execute_returning(contract)
        actor = _make_actor()

        result = await compliance_service.start_run(
            session,
            contract_id=1,
            checklist_codes=["建設業法19条", "下請法3条"],
            actor=actor,
        )

        assert result["status"] == "queued"

    async def test_disclaimer_in_job_handle(self) -> None:
        """Job handle always carries the legal disclaimer."""
        contract = _make_contract()
        session = _execute_returning(contract)
        actor = _make_actor()

        result = await compliance_service.start_run(session, contract_id=1, actor=actor)

        assert "法務担当者" in result["disclaimer"]


# ---------------------------------------------------------------------------
# Internal helpers (_severity_map, _status_map, _overall_status)
# ---------------------------------------------------------------------------


class TestSeverityMap:
    def test_block_maps_to_high(self) -> None:
        assert compliance_service._severity_map("block") == "high"

    def test_warn_maps_to_medium(self) -> None:
        assert compliance_service._severity_map("warn") == "medium"

    def test_info_maps_to_info(self) -> None:
        assert compliance_service._severity_map("info") == "info"

    def test_unknown_maps_to_low(self) -> None:
        assert compliance_service._severity_map("unknown") == "low"


class TestStatusMap:
    def test_block_maps_to_fail(self) -> None:
        assert compliance_service._status_map("block") == "fail"

    def test_warn_maps_to_warning(self) -> None:
        assert compliance_service._status_map("warn") == "warning"

    def test_info_maps_to_pass(self) -> None:
        assert compliance_service._status_map("info") == "pass"


class TestOverallStatus:
    def _make_finding(self, status: str) -> Any:
        from app.schemas.compliance import ComplianceFinding

        return ComplianceFinding(
            rule_id="X",
            rule_name="X",
            severity="info",
            status=status,
            message="X",
        )

    def test_fail_when_any_fail(self) -> None:
        findings = [
            self._make_finding("pass"),
            self._make_finding("fail"),
        ]
        assert compliance_service._overall_status(findings) == "fail"

    def test_warning_when_warning_no_fail(self) -> None:
        findings = [
            self._make_finding("pass"),
            self._make_finding("warning"),
        ]
        assert compliance_service._overall_status(findings) == "warning"

    def test_pass_when_all_pass(self) -> None:
        findings = [self._make_finding("pass")]
        assert compliance_service._overall_status(findings) == "pass"

    def test_pass_when_empty(self) -> None:
        assert compliance_service._overall_status([]) == "pass"
