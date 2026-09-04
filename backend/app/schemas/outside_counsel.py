"""顧問弁護士・外部法律事務所管理 API スキーマ（Issue #102）."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from .common import ORMModel


# ---------------------------------------------------------------- 台帳 ---
class LawFirmCreate(BaseModel):
    firm_name: str = Field(..., min_length=1, max_length=256)
    contact_email: str | None = Field(default=None, max_length=256)
    phone: str | None = Field(default=None, max_length=64)
    address: str | None = Field(default=None, max_length=512)
    notes: str | None = Field(default=None, max_length=4000)


class LawFirmOut(ORMModel):
    id: int
    firm_name: str
    contact_email: str | None
    phone: str | None
    address: str | None
    notes: str | None
    is_active: bool


class CounselLawyerCreate(BaseModel):
    firm_id: int
    lawyer_name: str = Field(..., min_length=1, max_length=128)
    email: str | None = Field(default=None, max_length=256)
    bar_number: str | None = Field(default=None, max_length=64)
    specialties: str | None = Field(default=None, max_length=512)


class CounselLawyerOut(ORMModel):
    id: int
    firm_id: int
    lawyer_name: str
    email: str | None
    bar_number: str | None
    specialties: str | None
    is_active: bool


# ---------------------------------------------------------------- 依頼 ---
class EngagementCreate(BaseModel):
    firm_id: int
    lawyer_id: int | None = None
    matter_id: int | None = None
    title: str = Field(..., min_length=1, max_length=256)
    question: str = Field(..., min_length=1, max_length=20000)
    due_date: date | None = Field(default=None, description="回答期限（#90）")
    conflict_of_interest: bool = Field(default=False, description="利益相反（#91）")
    conflict_note: str | None = Field(default=None, max_length=2000)
    confidential: bool = Field(default=False, description="Confidential 分類（#92）")
    fee_estimate_jpy: int | None = Field(default=None, ge=0, description="費用見込み（#93）")


class EngagementUpdate(BaseModel):
    due_date: date | None = None
    conflict_of_interest: bool | None = None
    conflict_note: str | None = Field(default=None, max_length=2000)
    confidential: bool | None = None
    fee_estimate_jpy: int | None = Field(default=None, ge=0)


class EngagementAnswerIn(BaseModel):
    answer: str = Field(..., min_length=1, max_length=40000)


class EngagementCancelIn(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class EngagementOut(ORMModel):
    id: int
    engagement_no: str
    firm_id: int
    lawyer_id: int | None
    matter_id: int | None
    title: str
    question: str
    answer: str | None
    status: str
    due_date: date | None
    answered_at: datetime | None
    answered_by: int | None
    conflict_of_interest: bool
    conflict_note: str | None
    confidential: bool
    fee_estimate_jpy: int | None
    notes: str | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime
