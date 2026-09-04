"""Legal Matter Management API スキーマ（Issue #101）."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import MatterPriority, MatterStatus, MatterType

from .common import ORMModel


class MatterCreate(BaseModel):
    """Matter 作成（#71〜#74）."""

    title: str = Field(..., min_length=1, max_length=256)
    matter_type: MatterType
    description: str | None = Field(default=None, max_length=8000)
    priority: MatterPriority = Field(default=MatterPriority.MEDIUM)
    assignee_id: int | None = Field(default=None, description="担当法務 user id")
    source_type: str | None = Field(
        default=None, description="昇格元種別: dispute / manual / review / other（#73）"
    )
    source_id: int | None = Field(default=None, description="昇格元レコード id")
    contract_ids: list[int] = Field(default_factory=list, description="関係契約リンク（#79）")
    legal_hold_case_id: int | None = Field(default=None, description="Legal Hold 連動（#82）")


class MatterUpdate(BaseModel):
    """Matter の基本情報更新."""

    title: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=8000)
    priority: MatterPriority | None = None


class MatterStatusIn(BaseModel):
    """Matter 状態遷移."""

    status: MatterStatus
    note: str | None = Field(default=None, max_length=2000)


class MatterAssignIn(BaseModel):
    """担当法務アサイン（#74）."""

    assignee_id: int | None = Field(default=None, description="null で担当解除")
    note: str | None = Field(default=None, max_length=2000)


class MatterContractIn(BaseModel):
    """関係契約リンク（#79）."""

    contract_id: int


class MatterLegalHoldIn(BaseModel):
    """Legal Hold 連動（#82・null で解除）."""

    legal_hold_case_id: int | None = None


class MatterNoteIn(BaseModel):
    """タイムラインへのメモ追記（#78）."""

    note: str = Field(..., min_length=1, max_length=4000)


class MatterOut(ORMModel):
    """Matter 1 件."""

    id: int
    matter_no: str
    title: str
    description: str | None
    matter_type: str
    status: str
    priority: str
    assignee_id: int | None
    source_type: str | None
    source_id: int | None
    legal_hold_case_id: int | None
    opened_at: datetime
    closed_at: datetime | None
    close_note: str | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime


class MatterEventOut(ORMModel):
    """Matter タイムラインイベント 1 件."""

    id: int
    matter_id: int
    event_type: str
    note: str | None
    payload: dict[str, object] | None
    actor_id: int | None
    created_at: datetime


class MatterContractOut(BaseModel):
    """関係契約の要約."""

    contract_id: int
    contract_no: str | None
    title: str
