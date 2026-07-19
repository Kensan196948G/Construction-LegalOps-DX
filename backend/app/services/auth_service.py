"""Authentication service wrappers used by the v1 auth router."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.sso_service import SSOError, SSOService


@dataclass(slots=True)
class AuthSessionToken:
    """Cookie session payload returned by the SSO callback route."""

    session_token: str
    redirect_to: str | None
    access_token: str
    id_token: str
    refresh_token: str | None
    expires_in: int


async def exchange_code(
    session: Any,
    *,
    code: str,
    state: str,
) -> AuthSessionToken:
    """Exchange an OIDC authorization code for a cookie session token.

    ``session`` is accepted for router compatibility; persistent session
    storage can be added later without changing the API contract.
    """
    _ = session
    if not state:
        raise SSOError("state is required")
    token = SSOService().exchange_code(code)
    return AuthSessionToken(
        session_token=token.access_token,
        redirect_to="/",
        access_token=token.access_token,
        id_token=token.id_token,
        refresh_token=token.refresh_token,
        expires_in=token.expires_in,
    )


async def revoke_session(session: Any, *, user_id: int | None) -> None:
    """Revoke a local session.

    The current release stores no server-side session row, so logout is an
    idempotent no-op after cookie deletion. The function exists to keep the
    route storage-ready and auditable.
    """
    _ = (session, user_id)
    return None
