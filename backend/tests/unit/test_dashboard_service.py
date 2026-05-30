"""Unit tests for app.services.dashboard_service.

Covers get_summary() and get_trends() using AsyncMock to avoid a real database.
Also covers _is_full_access() and _apply_scope() private helpers.

Target: dashboard_service.py coverage >= 60%.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import dashboard_service
from app.services.dashboard_service import (
    _apply_scope,
    _is_full_access,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_viewer(role: str = "admin", user_id: int = 1) -> MagicMock:
    v = MagicMock()
    v.role = role
    v.id = user_id
    return v


def _make_session() -> AsyncMock:
    """Return an AsyncMock that mimics AsyncSession with scalar results."""
    session = AsyncMock()
    session.flush = AsyncMock(return_value=None)
    return session


def _make_scalar_result(value: Any) -> MagicMock:
    res = MagicMock()
    res.scalar.return_value = value
    return res


def _make_scalars_result(value: Any) -> MagicMock:
    """Scalar result (single value)."""
    res = MagicMock()
    res.scalar.return_value = value
    # Support scalar() access
    res.scalar_one_or_none.return_value = value
    return res


def _make_all_zeros_summary_session() -> AsyncMock:
    """Wire a session that returns zeros/empty for all 9 queries in get_summary()."""
    session = _make_session()

    def _make_rows_result(rows: list[Any]) -> MagicMock:
        res = MagicMock()
        res.__iter__ = MagicMock(return_value=iter(rows))
        return res

    # Query order in get_summary:
    # 1. status_q          -> rows (iterable with .status/.cnt)
    # 2. wf_q              -> scalar()
    # 3. overdue_q         -> scalar()
    # 4. hr_q              -> scalar()
    # 5. rc_q              -> scalar()
    # 6. mt_q              -> scalar()
    # 7. avg_q             -> scalar()
    # 8. pr_q              -> scalar()
    session.execute.side_effect = [
        _make_rows_result([]),  # 1. contracts_by_status
        _make_scalars_result(0),  # 2. pending_approval (wf_q)
        _make_scalars_result(0),  # 3. overdue
        _make_scalars_result(0),  # 4. high_risk
        _make_scalars_result(0),  # 5. recent_completed
        _make_scalars_result(0),  # 6. my_tasks
        _make_scalars_result(None),  # 7. avg_risk_score (None → 0.0)
        _make_scalars_result(0),  # 8. pending_reviews
    ]
    return session


# ===========================================================================
# _is_full_access
# ===========================================================================


class TestIsFullAccess:
    def test_admin_is_full_access(self) -> None:
        assert _is_full_access(_make_viewer("admin")) is True

    def test_legal_is_full_access(self) -> None:
        assert _is_full_access(_make_viewer("legal")) is True

    def test_auditor_is_full_access(self) -> None:
        assert _is_full_access(_make_viewer("auditor")) is True

    def test_reviewer_is_full_access(self) -> None:
        assert _is_full_access(_make_viewer("reviewer")) is True

    def test_approver_is_full_access(self) -> None:
        assert _is_full_access(_make_viewer("approver")) is True

    def test_drafter_is_not_full_access(self) -> None:
        assert _is_full_access(_make_viewer("drafter")) is False

    def test_viewer_role_is_not_full_access(self) -> None:
        assert _is_full_access(_make_viewer("viewer")) is False

    def test_no_role_attr_is_not_full_access(self) -> None:
        obj = MagicMock(spec=[])  # no attributes
        assert _is_full_access(obj) is False

    def test_none_role_is_not_full_access(self) -> None:
        v = MagicMock()
        v.role = None
        assert _is_full_access(v) is False


# ===========================================================================
# _apply_scope
# ===========================================================================


class TestApplyScope:
    def test_full_access_role_does_not_add_where(self) -> None:
        """Admin viewer: stmt is returned unchanged (no drafter_id filter)."""
        stmt = MagicMock()
        viewer = _make_viewer("admin")
        result = _apply_scope(stmt, viewer)
        # Should not call .where() for full-access roles
        stmt.where.assert_not_called()
        assert result is stmt

    def test_limited_role_adds_drafter_filter(self) -> None:
        """Drafter viewer: stmt.where() is called to scope by drafter_id."""
        stmt = MagicMock()
        filtered_stmt = MagicMock()
        stmt.where.return_value = filtered_stmt

        viewer = _make_viewer("drafter", user_id=42)
        result = _apply_scope(stmt, viewer)

        stmt.where.assert_called_once()
        assert result is filtered_stmt

    def test_legal_role_does_not_filter(self) -> None:
        stmt = MagicMock()
        viewer = _make_viewer("legal")
        result = _apply_scope(stmt, viewer)
        stmt.where.assert_not_called()
        assert result is stmt


# ===========================================================================
# get_summary — all zeros / None
# ===========================================================================


@pytest.mark.asyncio
class TestGetSummaryZeros:
    async def test_returns_dashboard_summary_type(self) -> None:
        from app.schemas.dashboard import DashboardSummary

        session = _make_all_zeros_summary_session()
        viewer = _make_viewer("admin")
        result = await dashboard_service.get_summary(session, viewer=viewer)
        assert isinstance(result, DashboardSummary)

    async def test_all_counts_zero_when_db_empty(self) -> None:
        session = _make_all_zeros_summary_session()
        viewer = _make_viewer("admin")
        result = await dashboard_service.get_summary(session, viewer=viewer)

        assert result.pending_review == 0
        assert result.pending_approval == 0
        assert result.overdue == 0
        assert result.high_risk == 0
        assert result.recent_completed == 0
        assert result.my_tasks == 0
        assert result.pending_reviews == 0

    async def test_avg_risk_score_zero_when_none(self) -> None:
        """avg_q returning None is converted to 0.0."""
        session = _make_all_zeros_summary_session()
        viewer = _make_viewer("admin")
        result = await dashboard_service.get_summary(session, viewer=viewer)
        assert result.avg_risk_score == 0.0

    async def test_generated_at_is_set(self) -> None:
        session = _make_all_zeros_summary_session()
        viewer = _make_viewer("admin")
        result = await dashboard_service.get_summary(session, viewer=viewer)
        assert result.generated_at is not None

    async def test_contracts_by_status_empty_dict(self) -> None:
        session = _make_all_zeros_summary_session()
        viewer = _make_viewer("admin")
        result = await dashboard_service.get_summary(session, viewer=viewer)
        assert result.contracts_by_status == {}

    async def test_execute_called_eight_times(self) -> None:
        """get_summary executes 8 DB queries."""
        session = _make_all_zeros_summary_session()
        viewer = _make_viewer("admin")
        await dashboard_service.get_summary(session, viewer=viewer)
        assert session.execute.call_count == 8


# ===========================================================================
# get_summary — with data
# ===========================================================================


@pytest.mark.asyncio
class TestGetSummaryWithData:
    def _make_status_row(self, status: str, cnt: int) -> MagicMock:
        row = MagicMock()
        row.status = status
        row.cnt = cnt
        return row

    def _make_data_session(
        self,
        *,
        status_rows: list[Any] | None = None,
        wf_pending: int = 0,
        overdue: int = 0,
        high_risk: int = 0,
        recent_completed: int = 0,
        my_tasks: int = 0,
        avg_score: float | None = None,
        pending_reviews: int = 0,
    ) -> AsyncMock:
        session = _make_session()

        def _rows_result(rows: list[Any]) -> MagicMock:
            res = MagicMock()
            res.__iter__ = MagicMock(return_value=iter(rows))
            return res

        session.execute.side_effect = [
            _rows_result(status_rows or []),
            _make_scalars_result(wf_pending),
            _make_scalars_result(overdue),
            _make_scalars_result(high_risk),
            _make_scalars_result(recent_completed),
            _make_scalars_result(my_tasks),
            _make_scalars_result(avg_score),
            _make_scalars_result(pending_reviews),
        ]
        return session

    async def test_pending_review_from_in_review_status(self) -> None:
        """contracts_by_status['in_review'] populates pending_review."""
        row = self._make_status_row("in_review", 5)
        session = self._make_data_session(status_rows=[row])
        viewer = _make_viewer("admin")
        result = await dashboard_service.get_summary(session, viewer=viewer)
        assert result.pending_review == 5

    async def test_pending_approval_from_wf_query(self) -> None:
        session = self._make_data_session(wf_pending=3)
        viewer = _make_viewer("admin")
        result = await dashboard_service.get_summary(session, viewer=viewer)
        assert result.pending_approval == 3

    async def test_overdue_count(self) -> None:
        session = self._make_data_session(overdue=7)
        viewer = _make_viewer("admin")
        result = await dashboard_service.get_summary(session, viewer=viewer)
        assert result.overdue == 7

    async def test_high_risk_count(self) -> None:
        session = self._make_data_session(high_risk=2)
        viewer = _make_viewer("admin")
        result = await dashboard_service.get_summary(session, viewer=viewer)
        assert result.high_risk == 2

    async def test_recent_completed_count(self) -> None:
        session = self._make_data_session(recent_completed=10)
        viewer = _make_viewer("admin")
        result = await dashboard_service.get_summary(session, viewer=viewer)
        assert result.recent_completed == 10

    async def test_my_tasks_count(self) -> None:
        session = self._make_data_session(my_tasks=4)
        viewer = _make_viewer("admin")
        result = await dashboard_service.get_summary(session, viewer=viewer)
        assert result.my_tasks == 4

    async def test_avg_risk_score_rounded(self) -> None:
        session = self._make_data_session(avg_score=72.567)
        viewer = _make_viewer("admin")
        result = await dashboard_service.get_summary(session, viewer=viewer)
        assert result.avg_risk_score == 72.6

    async def test_pending_reviews_count(self) -> None:
        session = self._make_data_session(pending_reviews=6)
        viewer = _make_viewer("admin")
        result = await dashboard_service.get_summary(session, viewer=viewer)
        assert result.pending_reviews == 6

    async def test_contracts_by_status_populated(self) -> None:
        rows = [
            self._make_status_row("draft", 3),
            self._make_status_row("approved", 2),
        ]
        session = self._make_data_session(status_rows=rows)
        viewer = _make_viewer("admin")
        result = await dashboard_service.get_summary(session, viewer=viewer)
        assert result.contracts_by_status["draft"] == 3
        assert result.contracts_by_status["approved"] == 2

    async def test_department_filter_accepted(self) -> None:
        """department_id parameter is forwarded without error."""
        session = self._make_data_session()
        viewer = _make_viewer("admin")
        result = await dashboard_service.get_summary(session, viewer=viewer, department_id=10)
        assert result is not None

    async def test_drafter_viewer_scoped_query(self) -> None:
        """Drafter viewer triggers scope filtering (no exception expected)."""
        session = self._make_data_session()
        viewer = _make_viewer("drafter", user_id=99)
        result = await dashboard_service.get_summary(session, viewer=viewer)
        assert result is not None


# ===========================================================================
# get_trends
# ===========================================================================


@pytest.mark.asyncio
class TestGetTrends:
    def _make_trends_session(self, windows: int = 4, value: int = 0) -> AsyncMock:
        """Wire session for get_trends: 3 queries per bucket (created/completed/reviews)."""
        session = _make_session()
        side = []
        for _ in range(windows):
            side.append(_make_scalars_result(value))  # created_series
            side.append(_make_scalars_result(value))  # completed_series
            side.append(_make_scalars_result(value))  # review_series
        session.execute.side_effect = side
        return session

    async def test_returns_dashboard_trends_type(self) -> None:
        from app.schemas.dashboard import DashboardTrends

        session = self._make_trends_session()
        viewer = _make_viewer("admin")
        result = await dashboard_service.get_trends(
            session, viewer=viewer, interval="week", windows=4
        )
        assert isinstance(result, DashboardTrends)

    async def test_week_interval_granularity(self) -> None:
        session = self._make_trends_session(windows=4)
        viewer = _make_viewer("admin")
        result = await dashboard_service.get_trends(
            session, viewer=viewer, interval="week", windows=4
        )
        assert result.granularity == "week"

    async def test_month_interval_granularity(self) -> None:
        session = self._make_trends_session(windows=3)
        viewer = _make_viewer("admin")
        result = await dashboard_service.get_trends(
            session, viewer=viewer, interval="month", windows=3
        )
        assert result.granularity == "month"

    async def test_series_keys_present(self) -> None:
        session = self._make_trends_session(windows=4)
        viewer = _make_viewer("admin")
        result = await dashboard_service.get_trends(
            session, viewer=viewer, interval="week", windows=4
        )
        assert "created" in result.series
        assert "completed" in result.series
        assert "reviews" in result.series

    async def test_series_length_matches_windows(self) -> None:
        windows = 6
        session = self._make_trends_session(windows=windows)
        viewer = _make_viewer("admin")
        result = await dashboard_service.get_trends(
            session, viewer=viewer, interval="week", windows=windows
        )
        assert len(result.series["created"]) == windows
        assert len(result.series["completed"]) == windows
        assert len(result.series["reviews"]) == windows

    async def test_trend_points_have_bucket_dates(self) -> None:
        windows = 3
        session = self._make_trends_session(windows=windows)
        viewer = _make_viewer("admin")
        result = await dashboard_service.get_trends(
            session, viewer=viewer, interval="week", windows=windows
        )
        for point in result.series["created"]:
            assert isinstance(point.bucket, date)

    async def test_trend_points_value_zero(self) -> None:
        session = self._make_trends_session(windows=2, value=0)
        viewer = _make_viewer("admin")
        result = await dashboard_service.get_trends(
            session, viewer=viewer, interval="week", windows=2
        )
        assert all(p.value == 0 for p in result.series["created"])

    async def test_trend_points_with_nonzero_value(self) -> None:
        session = self._make_trends_session(windows=2, value=5)
        viewer = _make_viewer("admin")
        result = await dashboard_service.get_trends(
            session, viewer=viewer, interval="week", windows=2
        )
        assert all(p.value == 5 for p in result.series["created"])

    async def test_drafter_viewer_no_exception(self) -> None:
        session = self._make_trends_session(windows=3)
        viewer = _make_viewer("drafter", user_id=7)
        result = await dashboard_service.get_trends(
            session, viewer=viewer, interval="week", windows=3
        )
        assert result is not None

    async def test_execute_called_three_times_per_window(self) -> None:
        """3 queries per bucket: created / completed / reviews."""
        windows = 4
        session = self._make_trends_session(windows=windows)
        viewer = _make_viewer("admin")
        await dashboard_service.get_trends(session, viewer=viewer, interval="week", windows=windows)
        assert session.execute.call_count == windows * 3

    async def test_department_filter_no_exception(self) -> None:
        session = self._make_trends_session(windows=2)
        viewer = _make_viewer("admin")
        result = await dashboard_service.get_trends(
            session, viewer=viewer, interval="week", windows=2, department_id=5
        )
        assert result is not None

    async def test_buckets_are_ascending(self) -> None:
        """Trend points should be ordered oldest-first (ascending date)."""
        windows = 4
        session = self._make_trends_session(windows=windows)
        viewer = _make_viewer("admin")
        result = await dashboard_service.get_trends(
            session, viewer=viewer, interval="week", windows=windows
        )
        buckets = [p.bucket for p in result.series["created"]]
        assert buckets == sorted(buckets)
