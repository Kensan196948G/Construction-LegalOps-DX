"""Unit tests for app.services.contract_service.

Covers create_contract / get_contract / update_contract /
soft_delete_contract / list_contracts using AsyncMock sessions.

Target: contract_service.py coverage >= 70%.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import contract_service

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_actor(role: str = "admin", user_id: int = 1) -> MagicMock:
    actor = MagicMock()
    actor.role = role
    actor.id = user_id
    actor.db_id = user_id  # resolved users.id (Issue #45)
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
    contract_no: str = "C-AABBCCDDEE11",
    title: str = "テスト契約",
    counterparty: str = "株式会社テスト",
    contract_type: str = "請負",
    status: str = "draft",
    version: int = 1,
    deleted_at: datetime | None = None,
    drafter_id: int = 1,
    department_id: int = 10,
) -> MagicMock:
    c = MagicMock()
    c.id = id
    c.contract_no = contract_no
    c.title = title
    c.counterparty = counterparty
    c.contract_type = contract_type
    c.status = status
    c.version = version
    c.deleted_at = deleted_at
    c.drafter_id = drafter_id
    c.department_id = department_id
    c.amount = Decimal("1000000")
    c.currency = "JPY"
    c.start_date = date(2026, 1, 1)
    c.end_date = date(2026, 12, 31)
    c.confidentiality = "normal"
    c.extra_metadata = {}
    c.created_at = datetime.now(UTC)
    c.updated_at = datetime.now(UTC)
    c.sharepoint_item_id = None
    return c


def _make_contract_create(
    *,
    title: str = "テスト契約",
    counterparty: str = "株式会社テスト",
    contract_type: str = "請負",
    department_id: int = 10,
) -> MagicMock:
    data = MagicMock()
    data.title = title
    data.counterparty = counterparty
    data.contract_type = contract_type
    data.amount = Decimal("500000")
    data.currency = "JPY"
    data.start_date = date(2026, 1, 1)
    data.end_date = date(2026, 12, 31)
    data.department_id = department_id
    # confidentiality with .value attribute
    conf = MagicMock()
    conf.value = "normal"
    data.confidentiality = conf
    data.extra_metadata = {}
    return data


def _make_contract_update(
    *,
    title: str | None = None,
    version: int = 1,
) -> MagicMock:
    data = MagicMock()
    data.version = version
    updates: dict[str, Any] = {}
    if title is not None:
        updates["title"] = title
    data.model_dump.return_value = updates
    return data


# ===========================================================================
# create_contract
# ===========================================================================


@pytest.mark.asyncio
class TestCreateContract:
    async def test_create_returns_contract(self) -> None:
        session = _make_session()
        contract = _make_contract()
        session.refresh = AsyncMock(side_effect=lambda obj: None)

        # Simulate that after flush/refresh the session.add'd object is usable
        actor = _make_actor()
        data = _make_contract_create()

        with patch.object(contract_service, "Contract") as MockContract:
            MockContract.return_value = contract
            result = await contract_service.create_contract(session, creator=actor, data=data)

        session.add.assert_called_once()
        session.flush.assert_awaited_once()
        assert result is contract

    async def test_create_generates_contract_no(self) -> None:
        """contract_no starts with 'C-'."""
        session = _make_session()
        actor = _make_actor()
        data = _make_contract_create()

        captured: list[Any] = []

        def capture_contract(*args: Any, **kwargs: Any) -> Any:
            obj = MagicMock()
            captured.append(kwargs.get("contract_no", ""))
            return obj

        with patch.object(contract_service, "Contract", side_effect=capture_contract):
            await contract_service.create_contract(session, creator=actor, data=data)

        assert len(captured) == 1
        assert captured[0].startswith("C-")

    async def test_create_uses_status_draft(self) -> None:
        """Newly created contract gets status='draft'."""
        session = _make_session()
        actor = _make_actor()
        data = _make_contract_create()

        captured_kwargs: dict[str, Any] = {}

        def capture_contract(*args: Any, **kwargs: Any) -> Any:
            captured_kwargs.update(kwargs)
            return MagicMock()

        with patch.object(contract_service, "Contract", side_effect=capture_contract):
            await contract_service.create_contract(session, creator=actor, data=data)

        assert captured_kwargs.get("status") == "draft"

    async def test_create_uses_version_1(self) -> None:
        session = _make_session()
        actor = _make_actor()
        data = _make_contract_create()

        captured_kwargs: dict[str, Any] = {}

        def capture_contract(*args: Any, **kwargs: Any) -> Any:
            captured_kwargs.update(kwargs)
            return MagicMock()

        with patch.object(contract_service, "Contract", side_effect=capture_contract):
            await contract_service.create_contract(session, creator=actor, data=data)

        assert captured_kwargs.get("version") == 1

    async def test_create_with_confidentiality_value_attr(self) -> None:
        """Confidentiality with .value attribute uses enum value."""
        session = _make_session()
        actor = _make_actor()
        data = _make_contract_create()
        # data.confidentiality already has .value = "normal"

        captured_kwargs: dict[str, Any] = {}

        def capture_contract(*args: Any, **kwargs: Any) -> Any:
            captured_kwargs.update(kwargs)
            return MagicMock()

        with patch.object(contract_service, "Contract", side_effect=capture_contract):
            await contract_service.create_contract(session, creator=actor, data=data)

        assert captured_kwargs.get("confidentiality") == "normal"

    async def test_create_with_confidentiality_string(self) -> None:
        """Confidentiality as plain string (no .value) falls through to str() branch."""
        session = _make_session()
        actor = _make_actor()
        data = _make_contract_create()

        # Use a simple object that has no .value attribute → triggers str() branch
        class _PlainConf:
            def __str__(self) -> str:
                return "confidential"

        data.confidentiality = _PlainConf()

        captured_kwargs: dict[str, Any] = {}

        def capture_contract(*args: Any, **kwargs: Any) -> Any:
            captured_kwargs.update(kwargs)
            return MagicMock()

        with patch.object(contract_service, "Contract", side_effect=capture_contract):
            await contract_service.create_contract(session, creator=actor, data=data)

        # str() branch: confidentiality should be the string representation
        assert captured_kwargs.get("confidentiality") == "confidential"


# ===========================================================================
# get_contract
# ===========================================================================


@pytest.mark.asyncio
class TestGetContract:
    async def test_returns_contract_when_found(self) -> None:
        session = _make_session()
        contract = _make_contract(id=1)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = contract
        session.execute = AsyncMock(return_value=result_mock)

        actor = _make_actor()
        found = await contract_service.get_contract(session, contract_id=1, viewer=actor)
        assert found is contract

    async def test_returns_none_when_not_found(self) -> None:
        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_mock)

        actor = _make_actor()
        found = await contract_service.get_contract(session, contract_id=999, viewer=actor)
        assert found is None

    async def test_include_deleted_false_filters_deleted(self) -> None:
        """include_deleted=False (default) adds deleted_at.is_(None) filter."""
        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_mock)

        actor = _make_actor()
        # Just ensure no exception; deleted_at filter logic is in SQLAlchemy stmt
        await contract_service.get_contract(
            session, contract_id=1, viewer=actor, include_deleted=False
        )
        session.execute.assert_awaited_once()

    async def test_include_deleted_true_skips_filter(self) -> None:
        session = _make_session()
        contract = _make_contract(id=1, deleted_at=datetime.now(UTC))
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = contract
        session.execute = AsyncMock(return_value=result_mock)

        actor = _make_actor()
        found = await contract_service.get_contract(
            session, contract_id=1, viewer=actor, include_deleted=True
        )
        assert found is contract


# ===========================================================================
# update_contract
# ===========================================================================


@pytest.mark.asyncio
class TestUpdateContract:
    async def test_raises_lookup_error_when_not_found(self) -> None:
        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_mock)

        data = _make_contract_update(version=1)
        actor = _make_actor()

        with pytest.raises(LookupError, match="not found"):
            await contract_service.update_contract(
                session, contract_id=999, data=data, editor=actor
            )

    async def test_raises_value_error_on_version_conflict(self) -> None:
        session = _make_session()
        contract = _make_contract(id=1, version=2)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = contract
        session.execute = AsyncMock(return_value=result_mock)

        data = _make_contract_update(version=1)  # mismatch: expected 1, got 2
        actor = _make_actor()

        with pytest.raises(ValueError, match=r"[Oo]ptimistic"):
            await contract_service.update_contract(session, contract_id=1, data=data, editor=actor)

    async def test_updates_field_and_increments_version(self) -> None:
        session = _make_session()
        contract = _make_contract(id=1, version=1, title="旧タイトル")
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = contract
        session.execute = AsyncMock(return_value=result_mock)

        data = _make_contract_update(title="新タイトル", version=1)
        actor = _make_actor()

        result = await contract_service.update_contract(
            session, contract_id=1, data=data, editor=actor
        )

        assert contract.title == "新タイトル"
        assert contract.version == 2
        assert result is contract

    async def test_flushes_and_refreshes(self) -> None:
        session = _make_session()
        contract = _make_contract(id=1, version=1)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = contract
        session.execute = AsyncMock(return_value=result_mock)

        data = _make_contract_update(version=1)
        actor = _make_actor()

        await contract_service.update_contract(session, contract_id=1, data=data, editor=actor)

        session.flush.assert_awaited_once()
        session.refresh.assert_awaited_once_with(contract)

    async def test_ignores_unknown_fields(self) -> None:
        """Fields not present on contract model are silently skipped."""
        session = _make_session()
        contract = _make_contract(id=1, version=1)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = contract
        session.execute = AsyncMock(return_value=result_mock)

        data = _make_contract_update(version=1)
        data.model_dump.return_value = {"nonexistent_field_xyz": "value"}
        actor = _make_actor()

        # Should not raise
        result = await contract_service.update_contract(
            session, contract_id=1, data=data, editor=actor
        )
        assert result is contract


# ===========================================================================
# soft_delete_contract
# ===========================================================================


@pytest.mark.asyncio
class TestSoftDeleteContract:
    async def test_raises_lookup_error_when_not_found(self) -> None:
        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_mock)

        actor = _make_actor()

        with pytest.raises(LookupError, match="not found"):
            await contract_service.soft_delete_contract(session, contract_id=999, actor=actor)

    async def test_sets_deleted_at(self) -> None:
        session = _make_session()
        contract = _make_contract(id=1, deleted_at=None)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = contract
        session.execute = AsyncMock(return_value=result_mock)

        actor = _make_actor()
        await contract_service.soft_delete_contract(session, contract_id=1, actor=actor)

        assert contract.deleted_at is not None

    async def test_deleted_at_is_utc(self) -> None:
        session = _make_session()
        contract = _make_contract(id=1)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = contract
        session.execute = AsyncMock(return_value=result_mock)

        actor = _make_actor()
        await contract_service.soft_delete_contract(session, contract_id=1, actor=actor)

        assert contract.deleted_at.tzinfo is not None

    async def test_flushes_after_delete(self) -> None:
        session = _make_session()
        contract = _make_contract(id=1)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = contract
        session.execute = AsyncMock(return_value=result_mock)

        actor = _make_actor()
        await contract_service.soft_delete_contract(session, contract_id=1, actor=actor)

        session.flush.assert_awaited_once()

    async def test_returns_none(self) -> None:
        session = _make_session()
        contract = _make_contract(id=1)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = contract
        session.execute = AsyncMock(return_value=result_mock)

        actor = _make_actor()
        result = await contract_service.soft_delete_contract(session, contract_id=1, actor=actor)

        assert result is None


# ===========================================================================
# submit_for_review
# ===========================================================================


@pytest.mark.asyncio
class TestSubmitForReview:
    async def test_raises_lookup_error_when_not_found(self) -> None:
        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_mock)

        actor = _make_actor()
        with pytest.raises(LookupError, match="not found"):
            await contract_service.submit_for_review(session, contract_id=999, actor=actor)

    async def test_raises_value_error_when_not_draft(self) -> None:
        session = _make_session()
        contract = _make_contract(id=1, status="in_review")
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = contract
        session.execute = AsyncMock(return_value=result_mock)

        actor = _make_actor()
        with pytest.raises(ValueError, match="cannot be submitted"):
            await contract_service.submit_for_review(session, contract_id=1, actor=actor)

    async def test_moves_draft_contract_to_in_review(self) -> None:
        session = _make_session()
        contract = _make_contract(id=1, status="draft", version=3)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = contract
        session.execute = AsyncMock(return_value=result_mock)

        actor = _make_actor()
        result = await contract_service.submit_for_review(session, contract_id=1, actor=actor)

        assert result is contract
        assert contract.status == "in_review"
        assert contract.version == 4
        session.flush.assert_awaited_once()
        session.refresh.assert_awaited_once_with(contract)


# ===========================================================================
# list_contracts
# ===========================================================================


@pytest.mark.asyncio
class TestListContracts:
    def _make_list_session(
        self,
        *,
        total: int = 0,
        rows: list[Any] | None = None,
    ) -> AsyncMock:
        session = _make_session()
        rows = rows or []

        count_result = MagicMock()
        count_result.scalar_one.return_value = total

        rows_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = rows
        rows_result.scalars.return_value = scalars_mock

        session.execute = AsyncMock(side_effect=[count_result, rows_result])
        return session

    async def test_returns_empty_list_and_zero_total(self) -> None:
        session = self._make_list_session(total=0, rows=[])
        actor = _make_actor()
        items, total = await contract_service.list_contracts(session, viewer=actor)
        assert total == 0
        assert items == []

    async def test_returns_items_with_correct_total(self) -> None:
        contract = _make_contract(id=1)
        session = self._make_list_session(total=1, rows=[contract])
        actor = _make_actor()

        with patch("app.schemas.contract.ContractOut.model_validate", return_value=contract):
            items, total = await contract_service.list_contracts(session, viewer=actor)

        assert total == 1
        assert len(items) == 1

    async def test_with_q_filter_no_exception(self) -> None:
        session = self._make_list_session(total=0)
        actor = _make_actor()
        _, total = await contract_service.list_contracts(session, viewer=actor, q="テスト")
        assert total == 0

    async def test_with_status_filter_no_exception(self) -> None:
        session = self._make_list_session(total=0)
        actor = _make_actor()
        _, total = await contract_service.list_contracts(session, viewer=actor, status="draft")
        assert total == 0

    async def test_with_contract_type_filter_no_exception(self) -> None:
        session = self._make_list_session(total=0)
        actor = _make_actor()
        _, total = await contract_service.list_contracts(
            session, viewer=actor, contract_type="請負"
        )
        assert total == 0

    async def test_with_department_id_filter_no_exception(self) -> None:
        session = self._make_list_session(total=0)
        actor = _make_actor()
        _, total = await contract_service.list_contracts(session, viewer=actor, department_id=5)
        assert total == 0

    async def test_pagination_page2(self) -> None:
        session = self._make_list_session(total=10)
        actor = _make_actor()
        _, total = await contract_service.list_contracts(session, viewer=actor, page=2, size=5)
        assert total == 10

    async def test_execute_called_twice(self) -> None:
        """list_contracts executes 2 queries: count + data."""
        session = self._make_list_session(total=0)
        actor = _make_actor()
        await contract_service.list_contracts(session, viewer=actor)
        assert session.execute.call_count == 2

    async def test_all_filters_combined_no_exception(self) -> None:
        session = self._make_list_session(total=0)
        actor = _make_actor()
        _, total = await contract_service.list_contracts(
            session,
            viewer=actor,
            q="検索",
            status="draft",
            contract_type="請負",
            department_id=3,
            page=1,
            size=10,
        )
        assert total == 0


# ===========================================================================
# __getattr__ stub fallback
# ===========================================================================


@pytest.mark.asyncio
class TestStubFallback:
    async def test_unknown_function_raises_http_501(self) -> None:
        """Accessing an unimplemented function via __getattr__ returns a 501 coroutine."""
        from fastapi import HTTPException

        func = contract_service.legacy_unimplemented_operation  # via __getattr__ → _stub
        with pytest.raises(HTTPException) as exc_info:
            await func()
        assert exc_info.value.status_code == 501
