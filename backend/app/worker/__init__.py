"""Celery worker package.

Provides the shared :data:`app.worker.celery_app.celery_app` instance used by
the ``celery worker`` / ``celery beat`` processes defined in
``infra/docker/docker-compose.yml`` under the ``worker`` profile.
"""

from __future__ import annotations

from app.worker.celery_app import celery_app

__all__ = ["celery_app"]
