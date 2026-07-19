"""Prometheus operational metrics beyond request latency.

The counters in :mod:`app.main` cover request traffic.  This module adds
release-operations signals that are useful for dashboards and alerts:
business object counts and Celery queue depth.
"""

from __future__ import annotations

import logging
from typing import Any, Final

from prometheus_client import Gauge
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.contract import Contract
from app.models.enums import ContractStatus, NotificationStatus, ReviewStatus, WorkflowStepStatus
from app.models.legal_review import LegalReview
from app.models.notification import Notification
from app.models.workflow import WorkflowStep

logger = logging.getLogger(__name__)

_CONTRACTS_BY_STATUS: Final[Gauge] = Gauge(
    "legalops_contracts_by_status",
    "Number of non-deleted contracts grouped by status.",
    ("status",),
)

_LEGAL_REVIEWS_BY_STATUS: Final[Gauge] = Gauge(
    "legalops_legal_reviews_by_status",
    "Number of non-deleted legal reviews grouped by status.",
    ("status",),
)

_WORKFLOW_STEPS_BY_STATUS: Final[Gauge] = Gauge(
    "legalops_workflow_steps_by_status",
    "Number of non-deleted workflow steps grouped by status.",
    ("status",),
)

_NOTIFICATIONS_BY_STATUS: Final[Gauge] = Gauge(
    "legalops_notifications_by_status",
    "Number of non-deleted notifications grouped by status.",
    ("status",),
)

_CELERY_QUEUE_LENGTH: Final[Gauge] = Gauge(
    "celery_queue_length",
    "Redis-backed Celery queue length. A value of -1 means the broker was unreachable.",
    ("queue",),
)


async def update_operational_metrics(session: AsyncSession) -> None:
    """Refresh business and queue gauges.

    Metrics scraping must never become a production availability dependency,
    so each collection family is isolated and logs failures at debug level.
    """
    try:
        await _update_grouped_count(
            session,
            model=Contract,
            status_column=Contract.status,
            known_statuses=[status.value for status in ContractStatus],
            gauge=_CONTRACTS_BY_STATUS,
        )
        await _update_grouped_count(
            session,
            model=LegalReview,
            status_column=LegalReview.status,
            known_statuses=[status.value for status in ReviewStatus],
            gauge=_LEGAL_REVIEWS_BY_STATUS,
        )
        await _update_grouped_count(
            session,
            model=WorkflowStep,
            status_column=WorkflowStep.status,
            known_statuses=[status.value for status in WorkflowStepStatus],
            gauge=_WORKFLOW_STEPS_BY_STATUS,
        )
        await _update_grouped_count(
            session,
            model=Notification,
            status_column=Notification.status,
            known_statuses=[status.value for status in NotificationStatus],
            gauge=_NOTIFICATIONS_BY_STATUS,
        )
    except Exception:
        logger.debug("business_metrics_update_failed", exc_info=True)

    await _update_celery_queue_metrics()


async def _update_grouped_count(
    session: AsyncSession,
    *,
    model: Any,
    status_column: Any,
    known_statuses: list[str],
    gauge: Gauge,
) -> None:
    """Set a labeled gauge from ``GROUP BY status`` query results."""
    for status in known_statuses:
        gauge.labels(status=status).set(0)

    stmt = (
        select(status_column, func.count())
        .where(model.deleted_at.is_(None))
        .group_by(status_column)
    )
    rows = (await session.execute(stmt)).all()
    for status, count in rows:
        gauge.labels(status=str(status)).set(float(count))


async def _update_celery_queue_metrics() -> None:
    """Update Redis list lengths for configured Celery queues."""
    queue_names = settings.celery_queue_names or ["legalops.default"]
    try:
        import redis.asyncio as aioredis  # type: ignore[import-untyped]

        client = aioredis.from_url(
            settings.redis_url.get_secret_value(),
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        try:
            for queue_name in queue_names:
                length = await client.llen(queue_name)
                _CELERY_QUEUE_LENGTH.labels(queue=queue_name).set(float(length))
        finally:
            close = getattr(client, "aclose", client.close)
            await close()
    except Exception:
        logger.debug("celery_queue_metrics_update_failed", exc_info=True)
        for queue_name in queue_names:
            _CELERY_QUEUE_LENGTH.labels(queue=queue_name).set(-1)


__all__ = ["update_operational_metrics"]
