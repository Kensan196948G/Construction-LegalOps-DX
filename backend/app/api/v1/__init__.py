"""API v1 package.

`api_router` を `app.main` から `app.include_router(api_router)` でマウントする。
各 sub-router を機能単位で include する。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    antitrust,
    audit_logs,
    auth,
    business,
    compliance,
    contract_search,
    contracts,
    dashboard,
    dispute_ext,
    evidence,
    governance,
    health,
    ip,
    joint_venture,
    knowledge,
    labor_commitment,
    labor_wage,
    legal_ai,
    matters,
    negotiations,
    notifications,
    obligations,
    outside_counsel,
    partner_ext,
    price_consultation,
    public_works,
    reviews,
    risks,
    security,
    signing,
    templates,
    uploads,
    users,
    whistleblower,
    workflows,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(admin.router)
api_router.include_router(contracts.router)
api_router.include_router(contract_search.router)
api_router.include_router(matters.router)
api_router.include_router(negotiations.negotiations_router)
api_router.include_router(negotiations.clauses_router)
api_router.include_router(reviews.router)
api_router.include_router(workflows.router)
api_router.include_router(risks.router)
api_router.include_router(compliance.router)
api_router.include_router(templates.router)
api_router.include_router(signing.router)
api_router.include_router(knowledge.router)
api_router.include_router(labor_wage.router)
api_router.include_router(labor_commitment.router)
api_router.include_router(price_consultation.router)
api_router.include_router(public_works.router)
api_router.include_router(audit_logs.router)
api_router.include_router(uploads.router)
api_router.include_router(notifications.router)
api_router.include_router(outside_counsel.router)
api_router.include_router(partner_ext.router)
api_router.include_router(obligations.obligations_router)
api_router.include_router(obligations.contract_obligations_router)
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
api_router.include_router(ip.ip_router)
api_router.include_router(joint_venture.router)
api_router.include_router(legal_ai.applicable_laws_router)
api_router.include_router(legal_ai.evidence_router)
api_router.include_router(legal_ai.impact_router)
api_router.include_router(dispute_ext.router)
api_router.include_router(antitrust.router)
api_router.include_router(whistleblower.router)
api_router.include_router(evidence.router)


__all__ = ["api_router"]
