"""公共工事特化 API スキーマ（#41-#43・#54-#57・#60）."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import AgencyType

from .common import ORMModel


class ContractingAgencyCreate(BaseModel):
    """#41/#42 発注機関の登録."""

    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=256)
    agency_type: AgencyType
    prefecture: str | None = Field(default=None, max_length=16)
    contact_email: str | None = Field(default=None, max_length=256)
    phone: str | None = Field(default=None, max_length=64)
    payment_deadline_days: int | None = Field(default=None, ge=1)
    advance_payment_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    warranty_period_months: int | None = Field(default=None, ge=0)
    requires_slide_clause: bool = False
    notes: str | None = Field(default=None, max_length=4000)


class ContractingAgencyOut(ORMModel):
    id: int
    code: str
    name: str
    agency_type: str
    prefecture: str | None
    contact_email: str | None
    phone: str | None
    payment_deadline_days: int | None
    advance_payment_ratio: float | None
    warranty_period_months: int | None
    requires_slide_clause: bool
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class OwnerNotificationCreate(BaseModel):
    """#54 発注者通知の登録."""

    notification_type: str = Field(..., min_length=1, max_length=32)
    title: str = Field(..., min_length=1, max_length=256)
    contract_id: int | None = None
    agency_id: int | None = None
    detail: str | None = Field(default=None, max_length=8000)
    due_date: date | None = None


class OwnerNotificationOut(ORMModel):
    id: int
    notification_no: str
    contract_id: int | None
    agency_id: int | None
    notification_type: str
    status: str
    title: str
    detail: str | None
    due_date: date | None
    notified_at: datetime | None
    notified_by: int | None
    cancel_reason: str | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime


class OwnerNotificationCancel(BaseModel):
    reason: str = Field(..., min_length=1, max_length=2000)


class PublicWorksConsultationCreate(BaseModel):
    """#55/#56/#57 発注者との協議の申出."""

    consultation_type: str = Field(..., min_length=1, max_length=32)
    title: str = Field(..., min_length=1, max_length=256)
    contract_id: int | None = None
    agency_id: int | None = None
    detail: str | None = Field(default=None, max_length=8000)
    requested_at: date | None = None
    due_date: date | None = None
    claimed_days: int | None = Field(default=None, ge=1)
    claimed_amount_jpy: int | None = Field(default=None, ge=0)


class PublicWorksConsultationRespond(BaseModel):
    """#55/#56/#57 協議の回答・結果."""

    response_note: str = Field(..., min_length=1, max_length=8000)
    resolved_days: int | None = Field(default=None, ge=1)
    resolved_amount_jpy: int | None = Field(default=None, ge=0)


class PublicWorksConsultationCancel(BaseModel):
    reason: str = Field(..., min_length=1, max_length=2000)


class PublicWorksConsultationOut(ORMModel):
    id: int
    consultation_no: str
    contract_id: int | None
    agency_id: int | None
    consultation_type: str
    status: str
    title: str
    detail: str | None
    requested_at: date | None
    due_date: date | None
    claimed_days: int | None
    claimed_amount_jpy: int | None
    resolved_days: int | None
    resolved_amount_jpy: int | None
    responded_at: datetime | None
    response_note: str | None
    cancel_reason: str | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime


class StandardClauseCheckOut(BaseModel):
    """#43 標準請負約款差分チェック結果."""

    contract_id: int
    contract_no: str | None
    title: str | None
    total_categories: int
    covered_categories: int
    missing_categories: int
    categories: list[dict[str, object]]


class PublicWorksDashboardOut(BaseModel):
    """#60 公共工事ダッシュボード集計."""

    agencies_active: int
    notifications_open: int
    notifications_overdue: int
    consultations_open: int
    consultations_by_type: dict[str, int] = Field(default_factory=dict)


__all__ = [
    "ContractingAgencyCreate",
    "ContractingAgencyOut",
    "OwnerNotificationCreate",
    "OwnerNotificationOut",
    "PublicWorksConsultationCreate",
    "PublicWorksConsultationOut",
    "PublicWorksConsultationRespond",
    "StandardClauseCheckOut",
]
