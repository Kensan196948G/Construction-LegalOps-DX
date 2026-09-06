"""内部通報・調査管理 API スキーマ（Issue #123・ロードマップ #125〜#135）."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.enums import (
    WhistleblowerActionCategory,
    WhistleblowerActionStatus,
    WhistleblowerCaseRole,
    WhistleblowerCategory,
    WhistleblowerEvidenceType,
    WhistleblowerIntervieweeType,
    WhistleblowerReportStatus,
    WhistleblowerSeverity,
)

from .common import ORMModel


class WhistleblowerReportCreate(BaseModel):
    """通報受付（#125/#126）."""

    category: WhistleblowerCategory
    title: str = Field(..., min_length=1, max_length=256)
    description: str = Field(..., min_length=1, max_length=8000)
    severity: WhistleblowerSeverity = Field(default=WhistleblowerSeverity.MEDIUM)
    is_anonymous: bool = Field(default=False, description="匿名通報（#126）")
    occurred_at: date | None = None
    lead_investigator_id: int | None = Field(default=None, description="主任調査担当 user id")

    # 匿名でない場合のみ許可される通報者識別情報（isolate 先テーブルへ保存）
    reporter_name: str | None = Field(default=None, max_length=128)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=32)
    department: str | None = Field(default=None, max_length=128)
    relationship_to_subject: str | None = Field(default=None, max_length=64)
    consent_identity_disclosure: bool = Field(default=False)

    @model_validator(mode="after")
    def _validate_anonymous(self) -> WhistleblowerReportCreate:
        if self.is_anonymous and any(
            (
                self.reporter_name,
                self.contact_email,
                self.contact_phone,
                self.department,
                self.relationship_to_subject,
            )
        ):
            raise ValueError("匿名通報では通報者を特定できる情報を登録できません。")
        return self


class WhistleblowerReportOut(ORMModel):
    """通報 1 件（本体・非識別情報のみ）."""

    id: int
    report_no: str
    category: str
    title: str
    description: str
    status: str
    severity: str
    is_anonymous: bool
    occurred_at: date | None
    received_at: datetime
    matter_id: int | None
    lead_investigator_id: int | None
    substantiated: bool | None
    closed_at: datetime | None
    close_note: str | None
    created_at: datetime
    updated_at: datetime


class WhistleblowerReporterProfileOut(ORMModel):
    """通報者識別情報（調査担当者限定・#127）."""

    id: int
    report_id: int
    reporter_name: str | None
    contact_email: str | None
    contact_phone: str | None
    department: str | None
    relationship_to_subject: str | None
    consent_identity_disclosure: bool


class WhistleblowerStatusIn(BaseModel):
    """通報状態遷移."""

    status: WhistleblowerReportStatus
    note: str | None = Field(default=None, max_length=2000)


class WhistleblowerCaseAccessGrantIn(BaseModel):
    """調査担当者限定 ACL 付与（#127）."""

    user_id: int
    role_in_case: WhistleblowerCaseRole = Field(default=WhistleblowerCaseRole.INVESTIGATOR)
    can_view_reporter_identity: bool = Field(default=True)
    expires_at: datetime | None = None


class WhistleblowerCaseAccessOut(ORMModel):
    id: int
    report_id: int
    user_id: int
    role_in_case: str
    can_view_reporter_identity: bool
    granted_by: int | None
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class WhistleblowerEvidenceIn(BaseModel):
    """証拠保全（#129）."""

    evidence_type: WhistleblowerEvidenceType
    description: str | None = Field(default=None, max_length=4000)
    occurred_at: date | None = None
    attachment_id: int | None = None
    preserved: bool = Field(default=False)
    chain_of_custody: str | None = Field(default=None, max_length=4000)


class WhistleblowerEvidenceOut(ORMModel):
    id: int
    report_id: int
    evidence_type: str
    description: str | None
    occurred_at: date | None
    attachment_id: int | None
    preserved: bool
    chain_of_custody: str | None
    created_by: int | None
    created_at: datetime


class WhistleblowerInterviewIn(BaseModel):
    """ヒアリング記録（#130）."""

    interviewee_type: WhistleblowerIntervieweeType
    conducted_at: datetime
    interviewee_name: str | None = Field(default=None, max_length=128)
    summary: str | None = Field(default=None, max_length=8000)


class WhistleblowerInterviewOut(ORMModel):
    id: int
    report_id: int
    interviewee_type: str
    interviewee_name: str | None
    conducted_at: datetime
    conducted_by: int | None
    summary: str | None
    created_at: datetime


class WhistleblowerTimelineEventOut(ORMModel):
    """調査タイムライン（#131）."""

    id: int
    report_id: int
    event_type: str
    note: str | None
    payload: dict[str, object] | None
    actor_id: int | None
    created_at: datetime


class WhistleblowerNoteIn(BaseModel):
    note: str = Field(..., min_length=1, max_length=4000)


class WhistleblowerActionIn(BaseModel):
    """是正措置・再発防止管理（#132/#133）."""

    action_category: WhistleblowerActionCategory
    title: str = Field(..., min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=4000)
    owner_id: int | None = None
    due_date: date | None = None


class WhistleblowerActionStatusIn(BaseModel):
    status: WhistleblowerActionStatus
    verification_note: str | None = Field(default=None, max_length=2000)


class WhistleblowerActionOut(ORMModel):
    id: int
    report_id: int
    action_category: str
    title: str
    description: str | None
    owner_id: int | None
    due_date: date | None
    status: str
    completed_at: datetime | None
    verified_by: int | None
    verified_at: datetime | None
    verification_note: str | None
    created_at: datetime
    updated_at: datetime


class WhistleblowerAggregateOut(BaseModel):
    """経営報告匿名集計（#134/#135・個人特定不可能）."""

    total: int
    anonymous_count: int
    substantiated_count: int
    dismissed_count: int
    by_category: dict[str, int]
    by_status: dict[str, int]
    by_severity: dict[str, int]
    avg_days_to_close: float | None
    date_from: str | None
    date_to: str | None
