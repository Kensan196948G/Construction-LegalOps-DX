"""Authentication-related Pydantic schemas.

Mirrors ``docs/api_design.md`` section 3. Most flows are driven by Entra ID
OIDC; the schemas below cover the callback exchange and the API surface
exposed to the SPA.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Optional

from pydantic import BaseModel, EmailStr, Field

from .user import UserMe


class TokenResponse(BaseModel):
    """OAuth-style token envelope returned to backend-internal callers."""

    access_token: str
    token_type: Annotated[str, Field(pattern="^[Bb]earer$")] = "Bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    id_token: Optional[str] = None
    scope: Optional[str] = None


class SSOCallback(BaseModel):
    """Query parameters delivered by Entra ID to ``/auth/sso/callback``."""

    code: Annotated[str, Field(min_length=1)]
    state: Annotated[str, Field(min_length=1)]
    session_state: Optional[str] = None


class LoginRequest(BaseModel):
    """Optional username/password login (dev / break-glass only)."""

    email: EmailStr
    password: Annotated[str, Field(min_length=8, max_length=256)]


class RefreshRequest(BaseModel):
    """Body of ``POST /auth/refresh``."""

    refresh_token: Annotated[str, Field(min_length=1)]


class MeResponse(BaseModel):
    """Compact response for ``GET /auth/me``.

    The shape intentionally matches Loop 4 frontend expectations:
    ``{id, email, role, department_id}``. ``my_number`` and other PII
    columns are never echoed — the sensitive-masking middleware would
    drop them even if they leaked.
    """

    id: Any
    email: Optional[EmailStr] = None
    role: str
    department_id: Optional[str] = None

    @classmethod
    def from_user(cls, user: Any) -> "MeResponse":
        """Build the response from a :class:`app.deps.CurrentUser` principal.

        Falls back gracefully when the caller passes a SQLAlchemy ``User``
        row (e.g. test doubles) by reading ``department_id`` directly.
        """
        # CurrentUser exposes a ``department_ids`` tuple; fall back to the
        # ORM ``department_id`` attribute for legacy paths.
        dept_attr = getattr(user, "department_ids", None)
        dept: str | None
        if dept_attr:
            dept = str(dept_attr[0])
        else:
            raw_dept = getattr(user, "department_id", None)
            dept = str(raw_dept) if raw_dept is not None else None
        return cls(
            id=getattr(user, "id", None),
            email=getattr(user, "email", None),
            role=getattr(user, "role", "guest"),
            department_id=dept,
        )


class LoginResponse(BaseModel):
    """Response for ``GET /auth/sso/login`` — Entra authorize URL bundle."""

    authorize_url: str
    state: str
    redirect_to: Optional[str] = None


class RefreshResponse(BaseModel):
    """Response for ``POST /auth/refresh`` — fresh access token."""

    access_token: str
    token_type: Annotated[str, Field(pattern="^[Bb]earer$")] = "Bearer"
    expires_in: int
    issued_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
