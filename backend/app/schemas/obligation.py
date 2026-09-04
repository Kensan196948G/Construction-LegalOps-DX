"""契約義務（Obligations Calendar）API スキーマ（Issue #99）."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import ObligationStatus, ObligationType

from .common import ORMModel


class ObligationCreate(BaseModel):
    """義務の登録."""

    obligation_type: ObligationType
    title: str = Field(..., min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=4000)
    due_date: date | None = Field(default=None, description="期限（Obligations Calendar 用）")
    assignee_id: int | None = Field(default=None, description="担当ユーザー id")
    status: ObligationStatus = Field(default=ObligationStatus.OPEN)


class ObligationUpdate(BaseModel):
    """義務の更新（完了・放棄は専用エンドポイント）."""

    title: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=4000)
    due_date: date | None = None
    assignee_id: int | None = None
    status: ObligationStatus | None = Field(
        default=None, description="open / in_progress のみ（サービス側で検証）"
    )


class ObligationOut(ORMModel):
    """義務 1 件."""

    id: int
    contract_id: int
    obligation_type: str
    title: str
    description: str | None
    due_date: date | None
    status: str
    assignee_id: int | None
    completed_at: datetime | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime


class RenewalCheckOut(BaseModel):
    """自動更新判定結果（#12）."""

    contract_id: int
    contract_no: str
    title: str
    end_date: date | None
    auto_renewal: bool
    renewal_notice_days: int
    notice_deadline: date | None
    days_left: int | None
    state: str
