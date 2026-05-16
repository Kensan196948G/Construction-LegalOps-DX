"""Dashboard / KPI Pydantic schemas.

Mirrors ``docs/api_design.md`` section 11. The aggregations are
role-scoped at the service layer (site → own cases, manager → reports,
legal/admin → all rows).
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class DashboardSummary(BaseModel):
    """KPI snapshot returned by ``GET /dashboard/summary``."""

    pending_review: int = Field(default=0, ge=0, description="未レビュー件数")
    pending_approval: int = Field(default=0, ge=0, description="承認待ち件数")
    overdue: int = Field(default=0, ge=0, description="期限切れ件数")
    high_risk: int = Field(default=0, ge=0, description="高リスク件数")
    recent_completed: int = Field(default=0, ge=0, description="直近完了件数")
    my_tasks: int = Field(default=0, ge=0, description="自分宛タスク件数")
    avg_risk_score: float = Field(default=0.0, ge=0.0, le=100.0)
    contracts_by_status: dict[str, int] = Field(default_factory=dict)
    pending_reviews: int = Field(default=0, ge=0)
    generated_at: datetime | None = None


class DashboardTrendPoint(BaseModel):
    """One bucket inside :class:`DashboardTrends`."""

    bucket: date
    value: int = Field(default=0, ge=0)


class DashboardTrends(BaseModel):
    """Response of ``GET /dashboard/trends``."""

    granularity: str = Field(default="month", pattern="^(week|month)$")
    series: dict[str, list[DashboardTrendPoint]] = Field(default_factory=dict)


__all__ = ["DashboardSummary", "DashboardTrendPoint", "DashboardTrends"]
