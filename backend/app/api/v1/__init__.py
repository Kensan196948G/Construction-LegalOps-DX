"""API v1 package.

`api_router` を `app.main` から `app.include_router(api_router)` でマウントする。
各 sub-router を機能単位で include する。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    audit_logs,
    auth,
    business,
    compliance,
    contracts,
    dashboard,
    governance,
    health,
    knowledge,
    legal_ai,
    notifications,
    reviews,
    risks,
    security,
    templates,
    uploads,
    users,
    workflows,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(admin.router)
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
api_router.include_router(business.change_orders_router)
api_router.include_router(business.documents_router)
api_router.include_router(business.payment_router)
api_router.include_router(business.partners_router)
api_router.include_router(business.disputes_router)
api_router.include_router(governance.acl_router)
api_router.include_router(governance.legal_holds_router)
api_router.include_router(governance.retention_router)
api_router.include_router(governance.anchor_router)
api_router.include_router(governance.admin_router)
api_router.include_router(security.router)
api_router.include_router(legal_ai.applicable_laws_router)
api_router.include_router(legal_ai.evidence_router)
api_router.include_router(legal_ai.impact_router)


__all__ = ["api_router"]
