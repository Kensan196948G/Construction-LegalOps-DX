"""Dashboard aggregation service.

Computes KPI snapshots and trend series from Contract / LegalReview /
WorkflowStep tables.  All queries are role-scoped:
  - viewer.role in (admin, legal, auditor) → all rows
  - otherwise → rows where drafter_id == viewer.db_id
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract
from app.models.enums import ContractStatus, WorkflowStepStatus
from app.models.legal_review import LegalReview
from app.models.workflow import WorkflowStep
from app.schemas.dashboard import DashboardSummary, DashboardTrendPoint, DashboardTrends

_FULL_ACCESS_ROLES = {"admin", "legal", "auditor", "reviewer", "approver"}
_TERMINAL_STATUSES = {ContractStatus.ARCHIVED, ContractStatus.REJECTED}
_COMPLETED_STATUS = ContractStatus.APPROVED


def _is_full_access(viewer: Any) -> bool:
    role = getattr(viewer, "role", None)
    return role in _FULL_ACCESS_ROLES


def _apply_scope(stmt: Any, viewer: Any) -> Any:
    """Restrict a Contract-scoped statement to the viewer's accessible rows."""
    if not _is_full_access(viewer):
        stmt = stmt.where(Contract.drafter_id == viewer.db_id)
    return stmt


async def get_summary(
    session: AsyncSession,
    viewer: Any,
    department_id: int | None = None,
) -> DashboardSummary:
    today = date.today()
    recent_days = 30

    # Base contract filter
    def _base(stmt: Any) -> Any:
        stmt = _apply_scope(stmt, viewer)
        if department_id is not None:
            stmt = stmt.where(Contract.department_id == department_id)
        return stmt

    # 1. contracts_by_status
    status_q = await session.execute(
        _base(
            select(Contract.status, func.count(Contract.id).label("cnt"))
            .where(Contract.deleted_at.is_(None))
            .group_by(Contract.status)
        )
    )
    contracts_by_status: dict[str, int] = {row.status: row.cnt for row in status_q}

    # 2. pending_review: contracts in 'in_review' state
    pending_review = contracts_by_status.get(ContractStatus.IN_REVIEW, 0)

    # 3. pending_approval: workflow steps pending/in_progress
    wf_q = await session.execute(
        select(func.count(WorkflowStep.id))
        .join(Contract, Contract.id == WorkflowStep.contract_id)
        .where(
            WorkflowStep.status.in_(
                [
                    WorkflowStepStatus.PENDING,
                    WorkflowStepStatus.IN_PROGRESS,
                ]
            ),
            WorkflowStep.deleted_at.is_(None),
            Contract.deleted_at.is_(None),
            *([Contract.department_id == department_id] if department_id else []),
            *([Contract.drafter_id == viewer.db_id] if not _is_full_access(viewer) else []),
        )
    )
    pending_approval = wf_q.scalar() or 0

    # 4. overdue: end_date < today and not in terminal/completed status
    overdue_q = await session.execute(
        _base(
            select(func.count(Contract.id)).where(
                Contract.end_date < today,
                Contract.status.not_in([s.value for s in _TERMINAL_STATUSES]),
                Contract.status != ContractStatus.APPROVED,
                Contract.deleted_at.is_(None),
            )
        )
    )
    overdue = overdue_q.scalar() or 0

    # 5. high_risk: legal reviews with risk_score >= 70
    hr_q = await session.execute(
        select(func.count(LegalReview.id))
        .join(Contract, Contract.id == LegalReview.contract_id)
        .where(
            LegalReview.risk_score >= 70,
            LegalReview.deleted_at.is_(None),
            Contract.deleted_at.is_(None),
            *([Contract.department_id == department_id] if department_id else []),
            *([Contract.drafter_id == viewer.db_id] if not _is_full_access(viewer) else []),
        )
    )
    high_risk = hr_q.scalar() or 0

    # 6. recent_completed: approved in last 30 days
    cutoff = datetime.now(UTC).date() - timedelta(days=recent_days)
    rc_q = await session.execute(
        _base(
            select(func.count(Contract.id)).where(
                Contract.status == ContractStatus.APPROVED,
                Contract.updated_at >= cutoff,
                Contract.deleted_at.is_(None),
            )
        )
    )
    recent_completed = rc_q.scalar() or 0

    # 7. my_tasks: workflow steps assigned to viewer
    mt_q = await session.execute(
        select(func.count(WorkflowStep.id)).where(
            WorkflowStep.assignee_id == getattr(viewer, "id", None),
            WorkflowStep.status.in_(
                [
                    WorkflowStepStatus.PENDING,
                    WorkflowStepStatus.IN_PROGRESS,
                ]
            ),
            WorkflowStep.deleted_at.is_(None),
        )
    )
    my_tasks = mt_q.scalar() or 0

    # 8. avg_risk_score
    avg_q = await session.execute(
        select(func.avg(LegalReview.risk_score))
        .join(Contract, Contract.id == LegalReview.contract_id)
        .where(
            LegalReview.risk_score.is_not(None),
            LegalReview.deleted_at.is_(None),
            Contract.deleted_at.is_(None),
            *([Contract.department_id == department_id] if department_id else []),
            *([Contract.drafter_id == viewer.db_id] if not _is_full_access(viewer) else []),
        )
    )
    raw_avg = avg_q.scalar()
    avg_risk_score = float(raw_avg) if raw_avg is not None else 0.0

    # 9. pending_reviews: legal reviews with status 'pending'
    pr_q = await session.execute(
        select(func.count(LegalReview.id))
        .join(Contract, Contract.id == LegalReview.contract_id)
        .where(
            LegalReview.status == "pending",
            LegalReview.deleted_at.is_(None),
            Contract.deleted_at.is_(None),
            *([Contract.department_id == department_id] if department_id else []),
            *([Contract.drafter_id == viewer.db_id] if not _is_full_access(viewer) else []),
        )
    )
    pending_reviews = pr_q.scalar() or 0

    return DashboardSummary(
        pending_review=pending_review,
        pending_approval=pending_approval,
        overdue=overdue,
        high_risk=high_risk,
        recent_completed=recent_completed,
        my_tasks=my_tasks,
        avg_risk_score=round(avg_risk_score, 1),
        contracts_by_status=contracts_by_status,
        pending_reviews=pending_reviews,
        generated_at=datetime.now(UTC),
    )


async def get_trends(
    session: AsyncSession,
    viewer: Any,
    interval: str = "week",
    windows: int = 12,
    department_id: int | None = None,
) -> DashboardTrends:
    today = date.today()
    delta = timedelta(weeks=1) if interval == "week" else timedelta(days=30)

    buckets = [today - delta * i for i in range(windows - 1, -1, -1)]

    created_series: list[DashboardTrendPoint] = []
    completed_series: list[DashboardTrendPoint] = []
    review_series: list[DashboardTrendPoint] = []

    for bucket in buckets:
        bucket_end = bucket + delta

        # contracts created in bucket
        def _scope_contract(stmt: Any) -> Any:
            stmt = stmt.where(Contract.deleted_at.is_(None))
            if department_id is not None:
                stmt = stmt.where(Contract.department_id == department_id)
            if not _is_full_access(viewer):
                stmt = stmt.where(Contract.drafter_id == viewer.db_id)
            return stmt

        cr_q = await session.execute(
            _scope_contract(
                select(func.count(Contract.id)).where(
                    Contract.created_at >= bucket,
                    Contract.created_at < bucket_end,
                )
            )
        )
        created_series.append(DashboardTrendPoint(bucket=bucket, value=cr_q.scalar() or 0))

        # contracts completed (approved) in bucket
        co_q = await session.execute(
            _scope_contract(
                select(func.count(Contract.id)).where(
                    Contract.status == ContractStatus.APPROVED,
                    Contract.updated_at >= bucket,
                    Contract.updated_at < bucket_end,
                )
            )
        )
        completed_series.append(DashboardTrendPoint(bucket=bucket, value=co_q.scalar() or 0))

        # reviews created in bucket
        rv_q = await session.execute(
            select(func.count(LegalReview.id))
            .join(Contract, Contract.id == LegalReview.contract_id)
            .where(
                LegalReview.created_at >= bucket,
                LegalReview.created_at < bucket_end,
                LegalReview.deleted_at.is_(None),
                Contract.deleted_at.is_(None),
                *([Contract.department_id == department_id] if department_id else []),
                *([Contract.drafter_id == viewer.db_id] if not _is_full_access(viewer) else []),
            )
        )
        review_series.append(DashboardTrendPoint(bucket=bucket, value=rv_q.scalar() or 0))

    return DashboardTrends(
        granularity=interval,
        series={
            "created": created_series,
            "completed": completed_series,
            "reviews": review_series,
        },
    )
