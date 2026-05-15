"""User-related Pydantic schemas.

Mirrors the response bodies from ``docs/api_design.md`` sections 3.4 and 4.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import UserRole

from .common import ORMModel, TimestampsMixin


class DepartmentBrief(ORMModel):
    """Minimal department reference embedded in user responses."""

    id: int
    name: str
    code: Optional[str] = None


class UserBase(BaseModel):
    """Common fields shared by create / update / read."""

    email: EmailStr
    display_name: Annotated[str, Field(min_length=1, max_length=128)]
    role: UserRole
    department_id: Optional[int] = None
    is_active: bool = True


class UserCreate(UserBase):
    """Payload for ``POST /users`` (admin-only) or post-SSO provisioning."""

    entra_oid: UUID
    attributes: dict[str, Any] = Field(default_factory=dict)


class UserUpdate(BaseModel):
    """Patch payload — every field optional, ``version`` for optimistic lock."""

    display_name: Optional[str] = Field(default=None, max_length=128)
    role: Optional[UserRole] = None
    department_id: Optional[int] = None
    is_active: Optional[bool] = None
    attributes: Optional[dict[str, Any]] = None
    version: Optional[int] = None


class UserRead(UserBase, TimestampsMixin):
    """User read schema returned by ``GET /users`` and ``/users/{id}``."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    entra_oid: UUID
    last_login_at: Optional[datetime] = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    department: Optional[DepartmentBrief] = None


class UserMe(ORMModel):
    """Compact "current user" projection for ``GET /auth/me``."""

    id: int
    entra_oid: UUID
    email: EmailStr
    display_name: str
    role: UserRole
    department: Optional[DepartmentBrief] = None
