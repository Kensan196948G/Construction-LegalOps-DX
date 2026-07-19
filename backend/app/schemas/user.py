"""User-related Pydantic schemas.

Mirrors the response bodies from ``docs/api_design.md`` sections 3.4 and 4.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import UserRole

from .common import ORMModel, TimestampsMixin


class DepartmentBrief(ORMModel):
    """Minimal department reference embedded in user responses."""

    id: int
    name: str
    code: str | None = None


class UserBase(BaseModel):
    """Common fields shared by create / update / read."""

    email: EmailStr
    display_name: Annotated[str, Field(min_length=1, max_length=128)]
    role: UserRole
    department_id: int | None = None
    is_active: bool = True


class UserCreate(UserBase):
    """Payload for ``POST /users`` (admin-only) or post-SSO provisioning."""

    entra_oid: UUID
    attributes: dict[str, Any] = Field(default_factory=dict)


class UserUpdate(BaseModel):
    """Patch payload — every field optional, ``version`` for optimistic lock."""

    display_name: str | None = Field(default=None, max_length=128)
    role: UserRole | None = None
    department_id: int | None = None
    is_active: bool | None = None
    attributes: dict[str, Any] | None = None
    version: int | None = None


class UserIdentityLink(BaseModel):
    """Admin-only explicit Entra oid linking request.

    Used when a user was first JIT-provisioned from an opaque subject and
    later receives a real Entra ``oid`` claim. The caller must prove which
    row is being changed by sending the current oid observed from
    ``GET /users/{id}``.
    """

    expected_current_entra_oid: UUID
    new_entra_oid: UUID
    reason: Annotated[str, Field(min_length=8, max_length=512)]


class UserRead(UserBase, TimestampsMixin):
    """User read schema returned by ``GET /users`` and ``/users/{id}``."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    entra_oid: UUID
    last_login_at: datetime | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    department: DepartmentBrief | None = None


class UserMe(ORMModel):
    """Compact "current user" projection for ``GET /auth/me``."""

    id: int
    entra_oid: UUID
    email: EmailStr
    display_name: str
    role: UserRole
    department: DepartmentBrief | None = None


# ---------------------------------------------------------------------------
# v1 public-API aliases (see ``docs/api_design.md`` section 4)
# ---------------------------------------------------------------------------


class UserOut(UserRead):
    """``GET /users`` / ``/users/{id}`` row schema."""


class UserSyncJob(BaseModel):
    """Response of ``POST /users/sync`` (Microsoft Graph delta sync)."""

    job_id: str
    status: Annotated[
        str, Field(pattern="^(queued|running|completed|failed)$")
    ] = "queued"
    triggered_by: int | None = None
    queued_at: datetime
    note: str | None = None


__all__ = [
    "DepartmentBrief",
    "UserBase",
    "UserCreate",
    "UserIdentityLink",
    "UserMe",
    "UserOut",
    "UserRead",
    "UserSyncJob",
    "UserUpdate",
]
