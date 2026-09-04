"""契約交渉・Redline 管理の API スキーマ（ロードマップ #5〜#8 / Issue #98）."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import (
    ClauseNegotiationAction,
    ClauseNegotiationStatus,
    ClauseOwner,
)

from .common import ORMModel


class NegotiationEventIn(BaseModel):
    """交渉イベント（comment / demand / concession / redline）の記録."""

    action: ClauseNegotiationAction = Field(
        ..., description="redline / demand / concession / comment"
    )
    clause_id: int | None = Field(default=None, description="対象条項（任意）")
    round_no: int | None = Field(default=None, ge=1, description="交渉ラウンド番号")
    note: str | None = Field(default=None, max_length=2000, description="メモ（要求内容・背景等）")
    proposed_text: str | None = Field(
        default=None, max_length=20000, description="redline 時の修正提案テキスト"
    )


class ClauseStatusIn(BaseModel):
    """条項ステータス更新（#7 Accepted / Rejected / Negotiating）."""

    status: ClauseNegotiationStatus
    note: str | None = Field(default=None, max_length=2000)


class ClauseOwnerIn(BaseModel):
    """条項オーナー割当（#8 法務・工事・営業・購買 等）."""

    owner: ClauseOwner
    note: str | None = Field(default=None, max_length=2000)


class NegotiationEventOut(ORMModel):
    """交渉イベント 1 件（証跡・読み取りのみ）."""

    id: int
    contract_id: int
    clause_id: int | None
    round_no: int | None
    action: str
    status_from: str | None
    status_to: str | None
    owner_from: str | None
    owner_to: str | None
    note: str | None
    proposed_text: str | None
    actor_id: int | None
    created_at: datetime


class ClauseNegotiationStateOut(ORMModel):
    """更新後の条項（negotiation_status / clause_owner / negotiated_text を含む）."""

    id: int
    contract_id: int
    seq: int
    title: str | None
    body: str
    risk_level: str | None
    negotiation_status: str | None
    clause_owner: str | None
    negotiated_text: str | None
