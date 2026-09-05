"""協力会社拡張 API スキーマ（#136〜#152）."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from .common import ORMModel


class PartnerReviewCreate(BaseModel):
    """#147-#149/#151 再審査・incident/violation の起票（partner_id はパスから）."""

    partner_id: int | None = None  # パスパラメータで供給（ボディでは任意）
    review_type: str = Field(..., min_length=1, max_length=32)
    title: str = Field(..., min_length=1, max_length=256)
    safety_score: int | None = Field(default=None, ge=0, le=100)
    findings: str | None = Field(default=None, max_length=8000)
    violation_count: int = Field(default=0, ge=0)
    incident_count: int = Field(default=0, ge=0)
    notes: str | None = Field(default=None, max_length=4000)


class PartnerReviewComplete(BaseModel):
    """#151 再審査の完了（次回期限を Partner へ反映）."""

    safety_score: int | None = Field(default=None, ge=0, le=100)
    findings: str | None = Field(default=None, max_length=8000)
    violation_count: int | None = Field(default=None, ge=0)
    incident_count: int | None = Field(default=None, ge=0)
    next_review_due: date | None = None


class PartnerReviewOut(ORMModel):
    id: int
    partner_id: int
    review_no: str
    review_type: str
    status: str
    title: str
    safety_score: int | None
    findings: str | None
    violation_count: int
    incident_count: int
    extra_data: dict[str, object] | None
    reviewed_at: date | None
    next_review_due: date | None
    reviewed_by: int | None
    notes: str | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime


class PartnerExpiryFlagsOut(BaseModel):
    """#138/#146/#151 期限状態フラグ."""

    partner_id: int
    partner_name: str
    permit_expiry: str | None
    permit_state: str
    insurance_expiry: str | None
    insurance_state: str
    ccus_expiry: str | None
    ccus_state: str
    next_review_due: str | None
    review_state: str
    risk_score: int | None


class PartnerRiskScoreOut(BaseModel):
    """#150 Partner Risk Score."""

    partner_id: int
    partner_name: str
    risk_score: int
    risk_level: str
    base_level: str
    expiry_overdue_count: int
