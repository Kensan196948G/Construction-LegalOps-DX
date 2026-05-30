"""Unit tests for app.services.review_service.

Covers list_reviews / get_review / update_review / accept / reject
using AsyncMock to avoid a real database.

Target: review_service.py coverage >= 60 %.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import guard – skip whole module gracefully if service not yet present
# ---------------------------------------------------------------------------
review_service = pytest.importorskip(
    "app.services.review_service",
    reason="review_service implemented in Loop 3+",
)

from app.models.enums import ReviewStatus  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_review(
    *,
    id: int = 1,
    contract_id: int = 10,
    status: str = ReviewStatus.PENDING,
    reviewer_id: int | None = None,
    result: dict[str, Any] | None = None,
    deleted_at: object = None,
) -> MagicMock:
    """Create a mock LegalReview ORM object with the minimum required attributes."""
    r = MagicMock()
    r.id = id
    r.contract_id = contract_id
    r.review_type = "ai"
    r.status = status
    r.ai_model = "claude-3-5-sonnet"
    r.overall_risk = "medium"
    r.risk_score = 55
    r.summary = "Test summary"
    r.started_at = None
    r.finished_at = None
    r.reviewer_id = reviewer_id
    r.ai_input_tokens = 100
    r.ai_output_tokens = 200
    r.result = result or {}
    r.created_at = None
    r.updated_at = None
    r.deleted_at = deleted_at
    return r


def _make_viewer(role: str = "admin", user_id: int = 1) -> MagicMock:
    v = MagicMock()
    v.role = role
    v.id = user_id
    return v


def _make_session() -> AsyncMock:
    """Return an AsyncMock that mimics AsyncSession enough for the service."""
    session = AsyncMock()
    session.flush = AsyncMock(return_value=None)
    return session


def _stub_execute(session: AsyncMock, *, scalar_value: int = 0, rows: list[Any]) -> None:
    """Wire session.execute side_effect for (count_q, data_q) call pair."""

    def _make_scalar_result(val: int) -> MagicMock:
        res = MagicMock()
        res.scalar.return_value = val
        return res

    def _make_rows_result(items: list[Any]) -> MagicMock:
        res = MagicMock()
        scalars_ret = MagicMock()
        # scalars() returns an object; iterating it yields the items.
        scalars_ret.__iter__ = MagicMock(return_value=iter(items))
        # Support both .all() and direct iteration patterns in service code.
        scalars_ret.all.return_value = items
        res.scalars.return_value = scalars_ret
        return res

    session.execute.side_effect = [
        _make_scalar_result(scalar_value),
        _make_rows_result(rows),
    ]


# ===========================================================================
# _is_full_access (private helper)
# ===========================================================================


class TestIsFullAccess:
    def test_admin_is_full_access(self) -> None:
        assert review_service._is_full_access(_make_viewer("admin")) is True

    def test_legal_is_full_access(self) -> None:
        assert review_service._is_full_access(_make_viewer("legal")) is True

    def test_auditor_is_full_access(self) -> None:
        assert review_service._is_full_access(_make_viewer("auditor")) is True

    def test_reviewer_is_full_access(self) -> None:
        assert review_service._is_full_access(_make_viewer("reviewer")) is True

    def test_approver_is_full_access(self) -> None:
        assert review_service._is_full_access(_make_viewer("approver")) is True

    def test_drafter_is_not_full_access(self) -> None:
        assert review_service._is_full_access(_make_viewer("drafter")) is False

    def test_viewer_is_not_full_access(self) -> None:
        assert review_service._is_full_access(_make_viewer("viewer")) is False

    def test_missing_role_attr_is_not_full_access(self) -> None:
        obj = MagicMock(spec=[])  # no attributes
        assert review_service._is_full_access(obj) is False


# ===========================================================================
# _to_dict (private helper)
# ===========================================================================


class TestToDict:
    def test_to_dict_returns_required_keys(self) -> None:
        r = _make_review(result={"issues": ["x"], "suggested_actions": ["y"]})
        d = review_service._to_dict(r)
        required = {
            "id",
            "contract_id",
            "review_type",
            "status",
            "summary",
            "findings",
            "suggested_actions",
            "disclaimer",
        }
        assert required.issubset(d.keys())

    def test_to_dict_extracts_findings_and_actions(self) -> None:
        r = _make_review(result={"issues": ["a", "b"], "suggested_actions": ["s1"]})
        d = review_service._to_dict(r)
        assert d["findings"] == ["a", "b"]
        assert d["suggested_actions"] == ["s1"]

    def test_to_dict_empty_result_gives_empty_lists(self) -> None:
        r = _make_review(result={})
        d = review_service._to_dict(r)
        assert d["findings"] == []
        assert d["suggested_actions"] == []

    def test_to_dict_reviewer_id_int_preserved(self) -> None:
        r = _make_review(reviewer_id=42)
        d = review_service._to_dict(r)
        assert d["reviewer_id"] == 42

    def test_to_dict_reviewer_id_none_preserved(self) -> None:
        r = _make_review(reviewer_id=None)
        d = review_service._to_dict(r)
        assert d["reviewer_id"] is None

    def test_to_dict_non_int_reviewer_id_returns_none(self) -> None:
        r = _make_review()
        r.reviewer_id = "not-an-int"
        d = review_service._to_dict(r)
        assert d["reviewer_id"] is None

    def test_to_dict_disclaimer_present(self) -> None:
        r = _make_review()
        d = review_service._to_dict(r)
        assert "AI レビュー" in d["disclaimer"] or "法務担当者" in d["disclaimer"]


# ===========================================================================
# list_reviews
# ===========================================================================


@pytest.mark.asyncio
class TestListReviews:
    async def test_full_access_returns_all_reviews(self) -> None:
        """Admin viewer: list_reviews returns count from scalar and items."""
        session = _make_session()
        review1 = _make_review(id=1)
        review2 = _make_review(id=2)
        _stub_execute(session, scalar_value=2, rows=[review1, review2])

        viewer = _make_viewer("admin")
        items, total = await review_service.list_reviews(session, viewer=viewer)

        assert total == 2
        assert len(items) == 2

    async def test_full_access_zero_results(self) -> None:
        """Admin viewer, empty table: returns empty list and total=0."""
        session = _make_session()
        _stub_execute(session, scalar_value=0, rows=[])

        viewer = _make_viewer("admin")
        items, total = await review_service.list_reviews(session, viewer=viewer)

        assert total == 0
        assert items == []

    async def test_non_full_access_joins_contract(self) -> None:
        """Drafter viewer: query is constructed without error (no full access)."""
        session = _make_session()
        r = _make_review(id=5, contract_id=99)

        # Re-stub after the with block (which doesn't change session state).
        with patch("app.services.review_service.LegalReview"):
            pass

        _stub_execute(session, scalar_value=1, rows=[r])
        items, total = await review_service.list_reviews(
            session, viewer=_make_viewer("drafter", user_id=7)
        )
        assert total == 1
        assert items[0]["id"] == 5

    async def test_pagination_offset_applied(self) -> None:
        """page=2, size=5: execute called, result is passed through."""
        session = _make_session()
        r = _make_review(id=10)
        _stub_execute(session, scalar_value=10, rows=[r])

        viewer = _make_viewer("admin")
        items, total = await review_service.list_reviews(session, viewer=viewer, page=2, size=5)
        assert total == 10
        assert len(items) == 1

    async def test_filters_forwarded_no_exception(self) -> None:
        """Passing contract_id / status / ai_model filters builds query without error."""
        session = _make_session()
        _stub_execute(session, scalar_value=0, rows=[])

        viewer = _make_viewer("admin")
        items, total = await review_service.list_reviews(
            session,
            viewer=viewer,
            contract_id=3,
            status="completed",
            ai_model="claude-3-5-sonnet",
        )
        assert total == 0
        assert items == []


# ===========================================================================
# get_review
# ===========================================================================


@pytest.mark.asyncio
class TestGetReview:
    async def test_full_access_returns_dict_when_found(self) -> None:
        """Admin viewer: review found → dict returned."""
        session = _make_session()
        r = _make_review(id=1)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = r
        session.execute.return_value = mock_result

        viewer = _make_viewer("admin")
        result = await review_service.get_review(session, review_id=1, viewer=viewer)

        assert result is not None
        assert result["id"] == 1

    async def test_returns_none_when_review_not_found(self) -> None:
        """No row in DB: get_review returns None."""
        session = _make_session()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        viewer = _make_viewer("admin")
        result = await review_service.get_review(session, review_id=999, viewer=viewer)

        assert result is None

    async def test_non_full_access_returns_none_when_not_own_contract(self) -> None:
        """Drafter viewer cannot see another user's contract review."""
        session = _make_session()
        r = _make_review(id=2, contract_id=55)
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = r
        session.execute.return_value = exec_result

        # session.get returns a Contract whose drafter_id != viewer.id
        mock_contract = MagicMock()
        mock_contract.drafter_id = 999  # different from viewer.id=7
        session.get.return_value = mock_contract

        viewer = _make_viewer("drafter", user_id=7)
        result = await review_service.get_review(session, review_id=2, viewer=viewer)

        assert result is None

    async def test_non_full_access_returns_none_when_contract_missing(self) -> None:
        """Drafter viewer: contract row is missing → returns None."""
        session = _make_session()
        r = _make_review(id=3, contract_id=60)
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = r
        session.execute.return_value = exec_result

        session.get.return_value = None  # contract not found

        viewer = _make_viewer("drafter", user_id=7)
        result = await review_service.get_review(session, review_id=3, viewer=viewer)

        assert result is None

    async def test_non_full_access_returns_dict_when_own_contract(self) -> None:
        """Drafter viewer: review belongs to their contract → dict returned."""
        session = _make_session()
        r = _make_review(id=4, contract_id=70)
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = r
        session.execute.return_value = exec_result

        mock_contract = MagicMock()
        mock_contract.drafter_id = 7  # matches viewer.id
        session.get.return_value = mock_contract

        viewer = _make_viewer("drafter", user_id=7)
        result = await review_service.get_review(session, review_id=4, viewer=viewer)

        assert result is not None
        assert result["id"] == 4


# ===========================================================================
# update_review
# ===========================================================================


@pytest.mark.asyncio
class TestUpdateReview:
    async def test_raises_lookup_error_when_not_found(self) -> None:
        """update_review raises LookupError for missing review."""
        session = _make_session()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None
        session.execute.return_value = exec_result

        data = MagicMock()
        data.model_dump.return_value = {}

        with pytest.raises(LookupError, match="not found"):
            await review_service.update_review(
                session, review_id=999, data=data, editor=MagicMock()
            )

    async def test_partial_update_sets_field(self) -> None:
        """update_review applies provided field values to the ORM object."""
        session = _make_session()
        r = _make_review(id=1)
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = r
        session.execute.return_value = exec_result

        data = MagicMock()
        data.model_dump.return_value = {"summary": "updated summary"}

        result = await review_service.update_review(
            session, review_id=1, data=data, editor=_make_viewer()
        )

        # The service calls setattr(review, "summary", "updated summary")
        assert r.summary == "updated summary"
        assert result["id"] == 1

    async def test_update_review_flushes_session(self) -> None:
        """update_review must call session.flush()."""
        session = _make_session()
        r = _make_review(id=1)
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = r
        session.execute.return_value = exec_result

        data = MagicMock()
        data.model_dump.return_value = {}

        await review_service.update_review(session, review_id=1, data=data, editor=_make_viewer())

        session.flush.assert_awaited_once()

    async def test_update_review_ignores_unknown_fields(self) -> None:
        """Fields not present on the ORM model are silently skipped."""
        session = _make_session()
        r = _make_review(id=1)
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = r
        session.execute.return_value = exec_result

        data = MagicMock()
        data.model_dump.return_value = {"nonexistent_field": "value"}

        # Should not raise
        result = await review_service.update_review(
            session, review_id=1, data=data, editor=_make_viewer()
        )
        assert result["id"] == 1


# ===========================================================================
# accept
# ===========================================================================


@pytest.mark.asyncio
class TestAccept:
    async def test_accept_raises_lookup_error_when_not_found(self) -> None:
        session = _make_session()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None
        session.execute.return_value = exec_result

        with pytest.raises(LookupError, match="not found"):
            await review_service.accept(session, review_id=999, actor=_make_viewer())

    async def test_accept_raises_value_error_for_invalid_status(self) -> None:
        """accept raises ValueError if review is in PENDING status."""
        session = _make_session()
        r = _make_review(id=1, status=ReviewStatus.PENDING)
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = r
        session.execute.return_value = exec_result

        with pytest.raises(ValueError, match="cannot accept"):
            await review_service.accept(session, review_id=1, actor=_make_viewer())

    async def test_accept_completed_review_sets_status(self) -> None:
        """accept on COMPLETED review sets status to COMPLETED and reviewer_id."""
        session = _make_session()
        r = _make_review(id=1, status=ReviewStatus.COMPLETED)
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = r
        session.execute.return_value = exec_result

        actor = _make_viewer("legal", user_id=42)
        result = await review_service.accept(session, review_id=1, actor=actor)

        assert r.status == ReviewStatus.COMPLETED.value
        assert r.reviewer_id == 42
        assert result["id"] == 1

    async def test_accept_running_review_allowed(self) -> None:
        """accept on RUNNING review should succeed (service allows it)."""
        session = _make_session()
        r = _make_review(id=2, status=ReviewStatus.RUNNING)
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = r
        session.execute.return_value = exec_result

        actor = _make_viewer("reviewer", user_id=5)
        result = await review_service.accept(session, review_id=2, actor=actor)

        assert r.reviewer_id == 5
        assert result["id"] == 2

    async def test_accept_with_comment_stores_in_result(self) -> None:
        """accept with a legal_comment stores it in review.result."""
        session = _make_session()
        r = _make_review(id=3, status=ReviewStatus.COMPLETED, result={})
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = r
        session.execute.return_value = exec_result

        await review_service.accept(session, review_id=3, actor=_make_viewer(), comment="LGTM")

        assert r.result.get("legal_comment") == "LGTM"

    async def test_accept_without_comment_does_not_set_key(self) -> None:
        """accept with no comment leaves result dict unchanged."""
        session = _make_session()
        r = _make_review(id=4, status=ReviewStatus.COMPLETED, result={})
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = r
        session.execute.return_value = exec_result

        await review_service.accept(session, review_id=4, actor=_make_viewer())

        assert "legal_comment" not in r.result

    async def test_accept_flushes_session(self) -> None:
        session = _make_session()
        r = _make_review(id=5, status=ReviewStatus.COMPLETED)
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = r
        session.execute.return_value = exec_result

        await review_service.accept(session, review_id=5, actor=_make_viewer())

        session.flush.assert_awaited_once()


# ===========================================================================
# reject
# ===========================================================================


@pytest.mark.asyncio
class TestReject:
    async def test_reject_raises_lookup_error_when_not_found(self) -> None:
        session = _make_session()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None
        session.execute.return_value = exec_result

        with pytest.raises(LookupError, match="not found"):
            await review_service.reject(session, review_id=999, actor=_make_viewer())

    async def test_reject_sets_status_to_rejected(self) -> None:
        """reject sets review.status to REJECTED and assigns reviewer_id."""
        session = _make_session()
        r = _make_review(id=1, status=ReviewStatus.COMPLETED)
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = r
        session.execute.return_value = exec_result

        actor = _make_viewer("legal", user_id=99)
        result = await review_service.reject(session, review_id=1, actor=actor)

        assert r.status == ReviewStatus.REJECTED.value
        assert r.reviewer_id == 99
        assert result["id"] == 1

    async def test_reject_with_reason_stores_in_result(self) -> None:
        """reject with reason stores rejection_reason in review.result."""
        session = _make_session()
        r = _make_review(id=2, status=ReviewStatus.COMPLETED, result={})
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = r
        session.execute.return_value = exec_result

        await review_service.reject(
            session, review_id=2, actor=_make_viewer(), reason="Clause 5 unacceptable"
        )

        assert r.result.get("rejection_reason") == "Clause 5 unacceptable"

    async def test_reject_without_reason_does_not_set_key(self) -> None:
        """reject with no reason leaves result dict unchanged."""
        session = _make_session()
        r = _make_review(id=3, status=ReviewStatus.RUNNING, result={})
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = r
        session.execute.return_value = exec_result

        await review_service.reject(session, review_id=3, actor=_make_viewer())

        assert "rejection_reason" not in r.result

    async def test_reject_sets_finished_at(self) -> None:
        """reject sets finished_at to current UTC time."""
        session = _make_session()
        r = _make_review(id=4, status=ReviewStatus.PENDING)
        r.finished_at = None
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = r
        session.execute.return_value = exec_result

        await review_service.reject(session, review_id=4, actor=_make_viewer())

        assert r.finished_at is not None

    async def test_reject_flushes_session(self) -> None:
        session = _make_session()
        r = _make_review(id=5, status=ReviewStatus.COMPLETED)
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = r
        session.execute.return_value = exec_result

        await review_service.reject(session, review_id=5, actor=_make_viewer())

        session.flush.assert_awaited_once()

    async def test_reject_any_status_does_not_raise(self) -> None:
        """Unlike accept, reject has no status guard — any status is allowed."""
        session = _make_session()
        for status in [ReviewStatus.PENDING, ReviewStatus.FAILED, ReviewStatus.ACCEPTED]:
            r = _make_review(id=6, status=status)
            exec_result = MagicMock()
            exec_result.scalar_one_or_none.return_value = r
            session.execute.return_value = exec_result
            # Should not raise
            await review_service.reject(session, review_id=6, actor=_make_viewer())
