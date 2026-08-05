"""セキュリティ・内部統制 API スキーマ（P0-6）."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .common import ORMModel, TimestampsMixin


class AccessGrantCreate(BaseModel):
    contract_id: int
    user_id: int
    access_level: str = Field(default="view", pattern="^(view|comment|edit)$")
    ethical_wall: bool = False
    expires_at: datetime | None = None


class AccessGrantOut(ORMModel, TimestampsMixin):
    id: int
    contract_id: int
    user_id: int
    access_level: str
    ethical_wall: bool
    granted_by: int | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None


class LegalHoldCreate(BaseModel):
    contract_id: int
    reason: str = Field(min_length=1, max_length=4096)
    notes: str | None = None


class LegalHoldOut(ORMModel, TimestampsMixin):
    id: int
    contract_id: int
    reason: str
    requested_by: int | None = None
    started_at: datetime
    ended_at: datetime | None = None
    notes: str | None = None


class RetentionSettingsIn(BaseModel):
    settings: dict[str, Any]


class RetentionSettingsOut(BaseModel):
    settings: dict[str, Any]


class AuditExportCreate(BaseModel):
    since: datetime
    until: datetime


class AuditExportOut(BaseModel):
    job_no: str
    file_path: str
    record_count: int
    merkle_root: str
    signature: str | None = None
    status: str


class AuditExportJobOut(ORMModel, TimestampsMixin):
    id: int
    job_no: str
    exported_from: datetime
    exported_to: datetime
    record_count: int
    file_path: str
    signature: str | None = None
    status: str
    error_message: str | None = None
    created_by: int | None = None
