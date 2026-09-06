"""独禁法・入札談合コンプライアンス API スキーマ（Issue #122）."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.services.antitrust_service import CONSULTATION_DISCLAIMER

from .common import ORMModel

_CHECK_DISCLAIMER = (
    "本チェック結果は機械的判定の参考情報です。最終判断は法務担当者および"
    "顧問弁護士が行ってください。"
)


# ---------------------------------------------------------------------------
# #113/#114/#117/#118/#119 ルールベースチェック
# ---------------------------------------------------------------------------


class AntitrustFindingOut(BaseModel):
    code: str
    title: str
    severity: str
    description: str
    citation: str
    suggestion: str | None = None
    matched_keywords: list[str] = Field(default_factory=list)


class AntitrustCheckCreate(BaseModel):
    check_type: str = Field(
        ..., description="general / bid_rigging / price_exchange / jv_formation / joint_research"
    )
    subject: str = Field(..., min_length=1, max_length=256)
    context: dict[str, Any] = Field(default_factory=dict)
    contract_id: int | None = None
    jv_id: int | None = None
    notes: str | None = Field(default=None, max_length=4000)


class AntitrustCheckOut(ORMModel):
    id: int
    check_no: str
    check_type: str
    severity: str
    subject: str
    contract_id: int | None
    jv_id: int | None
    input_context: dict[str, Any]
    findings: list[AntitrustFindingOut]
    checked_at: datetime
    notes: str | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime
    disclaimer: str = _CHECK_DISCLAIMER


# ---------------------------------------------------------------------------
# #115/#116/#121/#122/#123 事前申請 → 承認 → 記録
# ---------------------------------------------------------------------------


class AntitrustApplicationCreate(BaseModel):
    application_type: str = Field(
        ...,
        description=(
            "competitor_contact / meeting_social / entertainment_gift / "
            "public_official_contact / donation_sponsorship"
        ),
    )
    title: str = Field(..., min_length=1, max_length=256)
    counterparty_name: str | None = Field(default=None, max_length=256)
    counterparty_organization: str | None = Field(default=None, max_length=256)
    purpose: str | None = Field(default=None, max_length=4000)
    scheduled_at: datetime | None = None
    location: str | None = Field(default=None, max_length=256)
    amount_jpy: int | None = Field(default=None, ge=0)
    attendees: list[str] | None = None
    contract_id: int | None = None
    jv_id: int | None = None


class AntitrustApplicationDecision(BaseModel):
    decision: str = Field(..., description="approved / rejected")
    decision_note: str | None = Field(default=None, max_length=4000)


class AntitrustApplicationComplete(BaseModel):
    outcome_note: str = Field(..., min_length=1, max_length=8000)
    occurred_at: datetime | None = None


class AntitrustApplicationCancel(BaseModel):
    cancel_reason: str = Field(..., min_length=1, max_length=4000)


class AntitrustApplicationOut(ORMModel):
    id: int
    application_no: str
    application_type: str
    status: str
    title: str
    counterparty_name: str | None
    counterparty_organization: str | None
    purpose: str | None
    scheduled_at: datetime | None
    location: str | None
    amount_jpy: int | None
    attendees: list[str] | None
    contract_id: int | None
    jv_id: int | None
    approved_by: int | None
    approved_at: datetime | None
    decision_note: str | None
    occurred_at: datetime | None
    outcome_note: str | None
    reported_at: datetime | None
    cancel_reason: str | None
    notes: str | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# #120 競争法 AI 相談
# ---------------------------------------------------------------------------


class AntitrustConsultationCreate(BaseModel):
    query_text: str = Field(..., min_length=1, max_length=4000)
    contract_id: int | None = None


class AntitrustConsultationOut(ORMModel):
    id: int
    query_text: str
    answer_text: str
    citations: list[dict[str, Any]]
    contract_id: int | None
    created_at: datetime
    disclaimer: str = CONSULTATION_DISCLAIMER


# ---------------------------------------------------------------------------
# #124 コンプライアンス研修履歴
# ---------------------------------------------------------------------------


class ComplianceTrainingCreate(BaseModel):
    training_title: str = Field(..., min_length=1, max_length=256)
    completed_at: date
    user_id: int | None = None
    attendee_name: str | None = Field(default=None, max_length=256)
    category: str = Field(default="antitrust", max_length=64)
    score: int | None = Field(default=None, ge=0, le=100)
    certificate_url: str | None = Field(default=None, max_length=512)
    notes: str | None = Field(default=None, max_length=4000)


class ComplianceTrainingOut(ORMModel):
    id: int
    user_id: int | None
    attendee_name: str | None
    training_title: str
    category: str
    completed_at: date
    score: int | None
    certificate_url: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


__all__ = [
    "AntitrustApplicationCancel",
    "AntitrustApplicationComplete",
    "AntitrustApplicationCreate",
    "AntitrustApplicationDecision",
    "AntitrustApplicationOut",
    "AntitrustCheckCreate",
    "AntitrustCheckOut",
    "AntitrustConsultationCreate",
    "AntitrustConsultationOut",
    "AntitrustFindingOut",
    "ComplianceTrainingCreate",
    "ComplianceTrainingOut",
]
