"""JV（共同企業体）管理 API スキーマ（#61〜#70）."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from .common import ORMModel


class JvCreate(BaseModel):
    """#61 JV の登録."""

    name: str = Field(..., min_length=1, max_length=256)
    representative_name: str | None = Field(default=None, max_length=256)
    works_title: str | None = Field(default=None, max_length=256)
    contract_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    notes: str | None = Field(default=None, max_length=8000)


class JvStatusIn(BaseModel):
    """#61 JV の状態遷移."""

    status: str = Field(..., min_length=1, max_length=16)


class JvMemberCreate(BaseModel):
    """#63/#64/#65 構成員の追加."""

    company_name: str = Field(..., min_length=1, max_length=256)
    role: str = Field(default="member", max_length=16)
    equity_ratio: float | None = Field(default=None, ge=0, le=100)
    profit_share_ratio: float | None = Field(default=None, ge=0, le=100)
    contact_email: str | None = Field(default=None, max_length=256)
    notes: str | None = Field(default=None, max_length=4000)


class JvMemberOut(ORMModel):
    id: int
    jv_id: int
    role: str
    company_name: str
    equity_ratio: float | None
    profit_share_ratio: float | None
    contact_email: str | None
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class JvAgreementCreate(BaseModel):
    """#62 JV 協定書の登録."""

    title: str = Field(..., min_length=1, max_length=256)
    summary: str | None = Field(default=None, max_length=8000)
    signed_at: date | None = None
    document_url: str | None = Field(default=None, max_length=512)


class JvAgreementOut(ORMModel):
    id: int
    jv_id: int
    agreement_no: str
    status: str
    title: str
    summary: str | None
    signed_at: date | None
    terminated_at: date | None
    document_url: str | None
    created_at: datetime
    updated_at: datetime


class JvDisputeCreate(BaseModel):
    """#69 JV 内紛争・請求の記録."""

    title: str = Field(..., min_length=1, max_length=256)
    claimant_name: str | None = Field(default=None, max_length=256)
    respondent_name: str | None = Field(default=None, max_length=256)
    amount_claimed_jpy: int | None = Field(default=None, ge=0)
    detail: str | None = Field(default=None, max_length=8000)


class JvDisputeRespond(BaseModel):
    response_note: str = Field(..., min_length=1, max_length=8000)


class JvDisputeOut(ORMModel):
    id: int
    jv_id: int
    dispute_no: str
    status: str
    title: str
    claimant_name: str | None
    respondent_name: str | None
    amount_claimed_jpy: int | None
    detail: str | None
    raised_at: date | None
    responded_at: datetime | None
    response_note: str | None
    cancel_reason: str | None
    created_at: datetime
    updated_at: datetime


class JvSettlementCreate(BaseModel):
    """#70 終了・清算の記録."""

    title: str = Field(..., min_length=1, max_length=256)
    settlement_amount_jpy: int | None = Field(default=None, ge=0)
    detail: str | None = Field(default=None, max_length=8000)


class JvSettlementOut(ORMModel):
    id: int
    jv_id: int
    settlement_no: str
    status: str
    title: str
    settled_at: date | None
    settlement_amount_jpy: int | None
    detail: str | None
    created_at: datetime
    updated_at: datetime


class JvOut(ORMModel):
    """#61 JV 1 件."""

    id: int
    jv_no: str
    name: str
    status: str
    representative_name: str | None
    works_title: str | None
    contract_id: int | None
    start_date: date | None
    end_date: date | None
    notes: str | None
    dissolved_at: datetime | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime


class JvDashboardOut(BaseModel):
    """JV サマリー."""

    jvs_by_status: dict[str, int] = Field(default_factory=dict)
    agreements_signed: int
    disputes_open: int
    settlements_pending: int
