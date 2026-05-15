"""Audit-log Pydantic schemas.

Mirrors ``docs/api_design.md`` section 12.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .common import ORMModel


class AuditActor(BaseModel):
    """Slim user reference embedded in audit-log responses."""

    id: int
    display_name: Optional[str] = None


class AuditLogRead(ORMModel):
    """Read schema for ``GET /audit-logs``."""

    id: int
    occurred_at: datetime
    actor: Optional[AuditActor] = None
    actor_id: Optional[int] = None
    actor_role: Optional[str] = None
    action: str
    target_type: str
    target_id: Optional[int] = None
    request_id: Optional[UUID] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    previous_hash: Optional[str] = None
    hash_chain: str


class AuditLogVerifyResult(BaseModel):
    """Response of ``POST /audit-logs/verify``."""

    verified: bool
    total: int
    broken_at: Optional[int] = Field(
        default=None,
        description="ID of the first row whose hash does not match (None if intact).",
    )
    checked_at: datetime
