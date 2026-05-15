"""FastAPI authorization dependencies.

Loop 2 scope: JWT decoding only. Entra ID OIDC integration arrives in
Loop 4. The principal is built directly from the decoded JWT claims.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Final

from fastapi import Depends, Header, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token

# Roles defined by docs/api_design.md §1 (3).
type Role = str

ROLE_VIEWER: Final[Role] = "viewer"
ROLE_DRAFTER: Final[Role] = "drafter"
ROLE_REVIEWER: Final[Role] = "reviewer"
ROLE_APPROVER: Final[Role] = "approver"
ROLE_ADMIN: Final[Role] = "admin"
ROLE_AUDITOR: Final[Role] = "auditor"
ROLE_GUEST: Final[Role] = "guest"

ALL_ROLES: Final[frozenset[str]] = frozenset(
    {
        ROLE_VIEWER,
        ROLE_DRAFTER,
        ROLE_REVIEWER,
        ROLE_APPROVER,
        ROLE_ADMIN,
        ROLE_AUDITOR,
        ROLE_GUEST,
    }
)


@dataclass(frozen=True, slots=True)
class CurrentUser:
    """Decoded principal attached to a request after authentication."""

    id: uuid.UUID | str
    email: str | None
    role: Role
    department_ids: tuple[str, ...]
    raw_claims: dict[str, object]

    def has_role(self, *roles: Role) -> bool:
        return self.role in roles

    def can_access_department(self, department_id: str | uuid.UUID) -> bool:
        """Admin/auditor can see all; others only assigned departments."""
        if self.role in {ROLE_ADMIN, ROLE_AUDITOR}:
            return True
        return str(department_id) in self.department_ids


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


_bearer_scheme: Final[HTTPBearer] = HTTPBearer(auto_error=False)


def _coerce_user_id(value: object) -> uuid.UUID | str:
    if isinstance(value, str):
        try:
            return uuid.UUID(value)
        except ValueError:
            return value
    return str(value)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CurrentUser:
    """Decode the bearer token and build a :class:`CurrentUser`.

    Loop 2: claims come straight from the JWT. Loop 4 will replace this
    with Entra ID OIDC + DB lookup.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError("Missing or malformed Authorization header.")

    try:
        claims = decode_token(credentials.credentials)
    except ValueError as exc:
        raise UnauthorizedError(f"Invalid token: {exc}") from exc

    subject = claims.get("sub")
    if not subject:
        raise UnauthorizedError("Token is missing 'sub' claim.")

    role_claim = claims.get("role") or claims.get("roles")
    if isinstance(role_claim, list):
        role = str(role_claim[0]) if role_claim else ROLE_GUEST
    elif isinstance(role_claim, str):
        role = role_claim
    else:
        role = ROLE_GUEST

    if role not in ALL_ROLES:
        # Unknown role — degrade to guest rather than fail outright.
        role = ROLE_GUEST

    dept_claim = claims.get("department_ids") or claims.get("departments") or []
    if isinstance(dept_claim, list):
        department_ids = tuple(str(d) for d in dept_claim)
    elif isinstance(dept_claim, str):
        department_ids = (dept_claim,)
    else:
        department_ids = ()

    email = claims.get("email")
    email_str = email if isinstance(email, str) else None

    return CurrentUser(
        id=_coerce_user_id(subject),
        email=email_str,
        role=role,
        department_ids=department_ids,
        raw_claims=claims,
    )


# ---------------------------------------------------------------------------
# Authorization helpers
# ---------------------------------------------------------------------------


def require_role(*roles: Role):  # noqa: ANN201 — returns FastAPI dependency
    """Build a FastAPI dependency that allows only the given roles.

    Usage::

        @router.get("/admin", dependencies=[Depends(require_role("admin"))])
    """
    if not roles:
        raise ValueError("require_role expects at least one role")
    allowed: frozenset[str] = frozenset(roles)

    async def _checker(
        user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if user.role not in allowed:
            raise ForbiddenError(
                detail=f"Requires one of roles: {sorted(allowed)}.",
            )
        return user

    return _checker


def require_department_access(contract_id_param: str = "contract_id"):  # noqa: ANN201
    """Build a dependency that enforces department-scoped access.

    The actual contract→department mapping requires a DB lookup
    (implemented in the contracts service in Loop 3). For Loop 2 we
    perform a best-effort claim check: admins/auditors pass; others
    must have ``contract_id`` in ``allowed_contract_ids`` or the
    derived department in ``department_ids``. The full RLS-backed
    check will live in the service layer.
    """

    async def _checker(
        user: CurrentUser = Depends(get_current_user),
        contract_id: str | None = Header(default=None, alias="X-Contract-Id"),
    ) -> CurrentUser:
        if user.role in {ROLE_ADMIN, ROLE_AUDITOR}:
            return user
        if contract_id is None:
            # No contract context provided at the header level — defer to
            # the service layer, which has the row available.
            return user
        allowed_contracts = user.raw_claims.get("allowed_contract_ids", [])
        if (
            isinstance(allowed_contracts, list)
            and str(contract_id) in {str(c) for c in allowed_contracts}
        ):
            return user
        raise ForbiddenError(
            detail=f"No access to contract {contract_id} ({contract_id_param}).",
        )

    return _checker


# Re-exports for convenience.
__all__ = [
    "ALL_ROLES",
    "CurrentUser",
    "ROLE_ADMIN",
    "ROLE_APPROVER",
    "ROLE_AUDITOR",
    "ROLE_DRAFTER",
    "ROLE_GUEST",
    "ROLE_REVIEWER",
    "ROLE_VIEWER",
    "get_current_user",
    "require_department_access",
    "require_role",
]

# Silence unused-import lint for status (kept for potential future use).
_ = status
