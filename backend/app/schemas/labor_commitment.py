"""労務費コミットメント（表明）API スキーマ（#28）."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from .common import ORMModel


class LaborCommitmentCreate(BaseModel):
    """#28 表明の登録."""

    contract_id: int
    commitment_type: str = Field(..., min_length=1, max_length=32)
    title: str = Field(..., min_length=1, max_length=256)
    statement: str | None = Field(default=None, max_length=8000)
    confirmed_at: date | None = None


class LaborCommitmentVerify(BaseModel):
    """#28 履行確認 / 違反確認."""

    outcome: str = Field(..., min_length=1, max_length=16, description="fulfilled / violated")
    verify_note: str | None = Field(default=None, max_length=4000)


class LaborCommitmentOut(ORMModel):
    id: int
    contract_id: int
    commitment_type: str
    status: str
    title: str
    statement: str | None
    confirmed_at: date | None
    verified_at: datetime | None
    verified_by: int | None
    verify_note: str | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime
