"""Celery application factory.

Minimum implementation required by the ``worker`` / ``beat`` services in
``infra/docker/docker-compose.yml``. Concrete task modules (AI review,
SharePoint sync, daily audit verification, notification dispatch) will
register against this app in later loops via ``celery_app.autodiscover_tasks``.

The broker and result-backend URLs are sourced from the application
settings (``REDIS_URL``) so dev / staging / prod share a single config
surface and secrets stay out of source.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import settings

_redis_url = settings.redis_url.get_secret_value()

celery_app: Celery = Celery(
    "legalops",
    broker=_redis_url,
    backend=_redis_url,
    include=[],  # Task modules will be appended as they ship.
)

# Sane defaults: timezone-aware JST, deterministic serialization, and
# short visibility timeouts so failed workers don't hold long leases.
celery_app.conf.update(
    timezone="Asia/Tokyo",
    enable_utc=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    task_default_queue="legalops.default",
)

# Auto-discover tasks under ``app.tasks`` once that package exists.
celery_app.autodiscover_tasks(["app.tasks"], related_name="tasks")


__all__ = ["celery_app"]
