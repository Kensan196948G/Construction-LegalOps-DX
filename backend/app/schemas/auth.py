"""Authentication-related Pydantic schemas.

Mirrors ``docs/api_design.md`` section 3. Most flows are driven by Entra ID
OIDC; the schemas below cover the callback exchange and the API surface
exposed to the SPA.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

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
    """Envelope for ``GET /auth/me``."""

    data: UserMe
    issued_at: datetime
