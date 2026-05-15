"""Compliance-check Pydantic schemas.

Mirrors ``docs/api_design.md`` section 9. Covers 建設業法 / 下請法 et al.
mechanical compliance rule evaluation. The disclaimer enforced here is
the project-wide guard rail: AI / rule output is *advisory*; the final
call rests with the legal team and outside counsel.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .common import ORMModel


_DISCLAIMER: str = (
    "本チェック結果は機械的判定の参考情報です。最終判断は法務担当者および"
    "顧問弁護士が行ってください。"
)


class ComplianceChecklist(ORMModel):
    """One applicable checklist (e.g. ``建設業法 第19条``)."""

    id: int
    code: Annotated[str, Field(max_length=64)]
    name: Annotated[str, Field(max_length=256)]
    category: Annotated[str, Field(max_length=64)]
    contract_type: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True


class ComplianceFinding(BaseModel):
    """A single rule outcome inside a check run."""

    rule_id: str
    rule_name: str
    severity: Annotated[str, Field(pattern="^(info|low|medium|high|critical)$")]
    status: Annotated[str, Field(pattern="^(pass|fail|warning|skipped)$")]
    message: str
    clause_seq: Optional[int] = None
    citations: List[str] = Field(default_factory=list)


class ComplianceCheckResult(BaseModel):
    """Response of ``GET /compliance/checks/{contract_id}``.

    Carries the project-wide disclaimer so downstream UIs cannot omit it
    accidentally.
    """

    model_config = ConfigDict(from_attributes=True)

    contract_id: int
    checked_at: datetime
    overall_status: Annotated[str, Field(pattern="^(pass|fail|warning|skipped)$")]
    findings: List[ComplianceFinding] = Field(default_factory=list)
    disclaimer: str = _DISCLAIMER


class ComplianceRunResponse(BaseModel):
    """Response of ``POST /compliance/checks/{contract_id}/run``.

    The run is asynchronous; clients should poll ``GET`` for the result.
    """

    job_id: str
    contract_id: int
    accepted_at: datetime
    status: Annotated[str, Field(pattern="^(queued|running|done|failed)$")] = "queued"
    disclaimer: str = _DISCLAIMER


__all__ = [
    "ComplianceCheckResult",
    "ComplianceChecklist",
    "ComplianceFinding",
    "ComplianceRunResponse",
]
