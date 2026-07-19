"""Audit-log Pydantic schemas.

Mirrors ``docs/api_design.md`` section 12.
"""

from __future__ import annotations

from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .common import ORMModel


class AuditActor(BaseModel):
    """Slim user reference embedded in audit-log responses."""

    id: int
    display_name: str | None = None


class AuditLogRead(ORMModel):
    """Read schema for ``GET /audit-logs``."""

    id: int
    occurred_at: datetime
    actor: AuditActor | None = None
    actor_id: int | None = None
    actor_role: str | None = None
    action: str
    target_type: str
    target_id: int | None = None
    request_id: UUID | None = None
    ip_address: str | None = None
    user_agent: str | None = None

    @field_validator("ip_address", mode="before")
    @classmethod
    def _coerce_ip_address(cls, value: Any) -> Any:
        """Coerce PostgreSQL INET values to ``str``.

        Under PostgreSQL the ``audit_logs.ip_address`` column is ``INET`` and
        asyncpg returns :class:`ipaddress.IPv4Address` / ``IPv6Address``
        objects, which would fail the plain ``str`` validation (SQLite stores
        the same column as TEXT, so the mismatch only surfaces on the
        production-parity stack).
        """
        if isinstance(value, (IPv4Address, IPv6Address)):
            return str(value)
        return value
    payload: dict[str, Any] = Field(default_factory=dict)
    prev_hash: str | None = None
    hash_chain: str


class AuditLogVerifyResult(BaseModel):
    """Response of ``POST /audit-logs/verify``."""

    verified: bool
    total: int
    broken_at: int | None = Field(
        default=None,
        description="ID of the first row whose hash does not match (None if intact).",
    )
    checked_at: datetime


# v1 API alias names (used by ``app.api.v1.audit_logs``). Kept as plain
# subclasses so OpenAPI surfaces the friendly ``Out`` / ``Response`` names.
class AuditLogOut(AuditLogRead):
    """Public read schema for ``GET /audit-logs`` (v1 alias)."""


class AuditVerifyResponse(AuditLogVerifyResult):
    """Public response for ``POST /audit-logs/verify`` (v1 alias)."""

    ok: bool = True
