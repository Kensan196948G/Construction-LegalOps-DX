"""Compliance service — checklist definitions + ComplianceChecker integration.

Replaces the Loop 5 stub with concrete implementations for:
- list_checklists : static checklist registry
- get_result      : run ComplianceChecker against a stored Contract
- start_run       : accept an async check request and return a job handle
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract
from app.schemas.compliance import ComplianceCheckResult, ComplianceFinding

_FULL_ACCESS_ROLES = frozenset({"admin", "legal", "auditor", "reviewer", "approver"})

_COMPLIANCE_DISCLAIMER = (
    "本チェック結果は機械的判定の参考情報です。最終判断は法務担当者および"
    "顧問弁護士が行ってください。"
)

# ---------------------------------------------------------------------------
# Static checklist registry
# ---------------------------------------------------------------------------

_STATIC_CHECKLISTS: list[dict[str, Any]] = [
    {
        "id": 1,
        "code": "建設業法19条",
        "name": "建設業法 第19条 書面要件",
        "category": "construction_law",
        "contract_type": None,
        "description": "建設業法第19条に基づく契約書面の必要記載事項を確認します。",
        "is_active": True,
    },
    {
        "id": 2,
        "code": "下請法3条",
        "name": "下請法 第3条 書面交付",
        "category": "subcontract_act",
        "contract_type": "subcontract",
        "description": "下請法第3条に基づく書面交付義務の遵守を確認します。",
        "is_active": True,
    },
    {
        "id": 3,
        "code": "個人情報保護",
        "name": "個人情報保護法 対応",
        "category": "others",
        "contract_type": None,
        "description": "個人情報保護法に基づく利用目的・第三者提供条項の有無を確認します。",
        "is_active": True,
    },
    {
        "id": 4,
        "code": "電子帳簿",
        "name": "電子帳簿保存法 対応",
        "category": "others",
        "contract_type": None,
        "description": "電子帳簿保存法に基づく電子取引・タイムスタンプ要件の記載を確認します。",
        "is_active": True,
    },
]


async def list_checklists(
    session: AsyncSession,
    *,
    contract_type: str | None = None,
    category: str | None = None,
) -> list[dict[str, Any]]:
    """Return the static checklist definitions, optionally filtered."""
    results = list(_STATIC_CHECKLISTS)
    if contract_type is not None:
        results = [
            c for c in results if c["contract_type"] is None or c["contract_type"] == contract_type
        ]
    if category is not None:
        results = [c for c in results if c["category"] == category]
    return results


# ---------------------------------------------------------------------------
# Compliance check result
# ---------------------------------------------------------------------------


def _severity_map(checker_severity: str) -> str:
    """Map ComplianceSeverity → ComplianceFinding.severity pattern."""
    mapping = {
        "block": "high",
        "warn": "medium",
        "info": "info",
    }
    return mapping.get(checker_severity, "low")


def _status_map(checker_severity: str) -> str:
    """Derive finding status from ComplianceSeverity."""
    if checker_severity == "block":
        return "fail"
    if checker_severity == "warn":
        return "warning"
    return "pass"


def _overall_status(findings: list[ComplianceFinding]) -> str:
    statuses = {f.status for f in findings}
    if "fail" in statuses:
        return "fail"
    if "warning" in statuses:
        return "warning"
    return "pass"


async def get_result(
    session: AsyncSession,
    *,
    contract_id: int,
    viewer: Any,
) -> dict[str, Any] | None:
    """Run ComplianceChecker against the stored contract and return the result dict.

    Returns ``None`` when the contract does not exist or is soft-deleted.
    """
    from app.services.compliance_checker import ComplianceChecker, ContractSnapshot

    # Fetch the contract with row-level scope: privileged roles see all, others only their own.
    stmt = select(Contract).where(
        Contract.id == contract_id,
        Contract.deleted_at.is_(None),
    )
    if getattr(viewer, "role", None) not in _FULL_ACCESS_ROLES:
        stmt = stmt.where(Contract.drafter_id == viewer.id)
    row = await session.execute(stmt)
    contract: Contract | None = row.scalar_one_or_none()
    if contract is None:
        return None

    # Build a ContractSnapshot from the ORM model.
    snapshot = ContractSnapshot(
        text=getattr(contract, "text", "") or "",
        contract_type=contract.contract_type,
        amount_jpy=(int(contract.amount) if contract.amount is not None else None),
        is_public_work=bool(
            contract.extra_metadata.get("is_public_work", False)
            if contract.extra_metadata
            else False
        ),
        counterparty_capital_jpy=None,
        our_capital_jpy=None,
        handles_personal_data=bool(
            contract.extra_metadata.get("handles_personal_data", False)
            if contract.extra_metadata
            else False
        ),
    )

    checker = ComplianceChecker()
    raw_findings = await checker.check(snapshot)

    findings: list[ComplianceFinding] = [
        ComplianceFinding(
            rule_id=f.code,
            rule_name=f.title,
            severity=_severity_map(str(f.severity)),
            status=_status_map(str(f.severity)),
            message=f.description,
            clause_seq=None,
            citations=[f.citation] if f.citation else [],
        )
        for f in raw_findings
    ]

    result = ComplianceCheckResult(
        contract_id=contract_id,
        checked_at=datetime.now(UTC),
        overall_status=_overall_status(findings),
        findings=findings,
        disclaimer=_COMPLIANCE_DISCLAIMER,
    )
    return result.model_dump()


# ---------------------------------------------------------------------------
# Start async run (job dispatch stub — future: Celery / ARQ task)
# ---------------------------------------------------------------------------


async def start_run(
    session: AsyncSession,
    *,
    contract_id: int,
    checklist_codes: list[str] | None = None,
    actor: Any,
) -> dict[str, Any]:
    """Accept a compliance check run request and return a job handle.

    The actual async execution is deferred (future implementation).
    Raises ``LookupError`` when the contract does not exist.
    """
    stmt = select(Contract).where(
        Contract.id == contract_id,
        Contract.deleted_at.is_(None),
    )
    row = await session.execute(stmt)
    contract: Contract | None = row.scalar_one_or_none()
    if contract is None:
        raise LookupError(f"Contract id={contract_id} not found")

    return {
        "job_id": str(uuid4()),
        "contract_id": contract_id,
        "accepted_at": datetime.now(UTC),
        "status": "queued",
        "disclaimer": _COMPLIANCE_DISCLAIMER,
    }
