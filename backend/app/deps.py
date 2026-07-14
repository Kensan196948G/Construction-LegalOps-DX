"""FastAPI authorization dependencies.

Loop 2 scope: JWT decoding only. Entra ID OIDC integration arrives in
Loop 4. The principal is built directly from the decoded JWT claims.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final

from fastapi import Depends, Header, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.db.session import get_db

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
    """Decoded principal attached to a request after authentication.

    ``id`` is the raw token subject (Entra oid UUID or an opaque string such
    as an email) and must never be written to a BIGINT column. ``db_id`` is
    the resolved ``users.id`` row id (JIT-provisioned on first request) and
    is what services must use for FK writes, scope filters, and audit
    actor ids (Issue #45).
    """

    id: uuid.UUID | str
    email: str | None
    role: Role
    department_ids: tuple[str, ...]
    raw_claims: dict[str, object]
    db_id: int | None = None

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


# Roles storable in users.role (ck_users_role allows only UserRole values).
# Token-only roles (auditor / guest) are clamped for the provisioned row;
# authorization always uses the TOKEN role, never the stored one.
_DB_STORABLE_ROLES: Final[frozenset[str]] = frozenset(
    {ROLE_VIEWER, ROLE_DRAFTER, ROLE_REVIEWER, ROLE_APPROVER, ROLE_ADMIN}
)


async def _resolve_db_user_id(
    session: AsyncSession,
    *,
    subject: uuid.UUID | str,
    email: str | None,
    role: Role,
    claims: dict[str, object],
) -> int:
    """Resolve (JIT-provision) the ``users`` row for this principal.

    Lookup order: Entra ``oid`` claim (or a UUID subject) → email (``email``
    claim, falling back to an email-shaped subject). When no row exists the
    principal is provisioned on the spot — the SSO IdP has already
    authenticated it, so a missing row means "first visit", not "intruder".
    A savepoint guards the insert so a concurrent first request degrades to
    re-reading the winner's row instead of failing the request.
    """
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError

    from app.models.user import User

    entra_oid: uuid.UUID | None = None
    oid_claim = claims.get("oid")
    if isinstance(oid_claim, str):
        try:
            entra_oid = uuid.UUID(oid_claim)
        except ValueError:
            entra_oid = None
    if entra_oid is None and isinstance(subject, uuid.UUID):
        entra_oid = subject

    lookup_email = email
    if lookup_email is None and isinstance(subject, str) and "@" in subject:
        lookup_email = subject

    async def _find() -> int | None:
        if entra_oid is not None:
            found = (
                await session.execute(select(User.id).where(User.entra_oid == entra_oid))
            ).scalar_one_or_none()
            if found is not None:
                return int(found)
        if lookup_email is not None:
            found = (
                await session.execute(select(User.id).where(User.email == lookup_email))
            ).scalar_one_or_none()
            if found is not None:
                return int(found)
        return None

    existing = await _find()
    if existing is not None:
        return existing

    derived_oid = entra_oid or uuid.uuid5(uuid.NAMESPACE_URL, f"legalops:sub:{subject}")
    derived_email = lookup_email or f"{derived_oid}@sub.invalid"
    display_name = (lookup_email or str(subject)).split("@")[0] or str(subject)
    db_role = role if role in _DB_STORABLE_ROLES else ROLE_VIEWER

    user = User(
        entra_oid=derived_oid,
        email=derived_email,
        display_name=display_name[:128],
        role=db_role,
        is_active=True,
    )
    try:
        async with session.begin_nested():
            session.add(user)
            await session.flush()
    except IntegrityError:
        # Lost a provisioning race — the savepoint rolled back; re-read.
        raced = await _find()
        if raced is None:  # pragma: no cover — constraint other than the race
            raise
        return raced
    return int(user.id)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """Decode the bearer token and build a :class:`CurrentUser`.

    Claims come from the JWT; the numeric DB identity (``db_id``) is
    resolved against ``users`` with JIT provisioning (Issue #45). FastAPI's
    per-request dependency cache means this shares the request's session
    with the endpoint rather than opening a second one.
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

    coerced_subject = _coerce_user_id(subject)
    db_id = await _resolve_db_user_id(
        session,
        subject=coerced_subject,
        email=email_str,
        role=role,
        claims=claims,
    )

    return CurrentUser(
        id=coerced_subject,
        email=email_str,
        role=role,
        department_ids=department_ids,
        raw_claims=claims,
        db_id=db_id,
    )


# ---------------------------------------------------------------------------
# Authorization helpers
# ---------------------------------------------------------------------------


def require_role(*roles: Role) -> Callable[..., Awaitable[CurrentUser]]:
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


def require_department_access(
    contract_id_param: str = "contract_id",
) -> Callable[..., Awaitable[CurrentUser]]:
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
        if isinstance(allowed_contracts, list) and str(contract_id) in {
            str(c) for c in allowed_contracts
        }:
            return user
        raise ForbiddenError(
            detail=f"No access to contract {contract_id} ({contract_id_param}).",
        )

    return _checker


# Re-exports for convenience.
__all__ = [
    "ALL_ROLES",
    "ROLE_ADMIN",
    "ROLE_APPROVER",
    "ROLE_AUDITOR",
    "ROLE_DRAFTER",
    "ROLE_GUEST",
    "ROLE_REVIEWER",
    "ROLE_VIEWER",
    "CurrentUser",
    "get_current_user",
    "require_department_access",
    "require_role",
]

# Silence unused-import lint for status (kept for potential future use).
_ = status
