"""API v1 package.

`api_router` を `app.main` から `app.include_router(api_router)` でマウントする。
各 sub-router を機能単位で include する。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    audit_logs,
    auth,
    compliance,
    contracts,
    dashboard,
    knowledge,
    notifications,
    reviews,
    risks,
    templates,
    uploads,
    users,
    workflows,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(contracts.router)
api_router.include_router(reviews.router)
api_router.include_router(workflows.router)
api_router.include_router(risks.router)
api_router.include_router(compliance.router)
api_router.include_router(templates.router)
api_router.include_router(knowledge.router)
api_router.include_router(audit_logs.router)
api_router.include_router(uploads.router)
api_router.include_router(notifications.router)
api_router.include_router(dashboard.router)


__all__ = ["api_router"]
