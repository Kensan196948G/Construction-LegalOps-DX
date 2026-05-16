"""Security primitives: password hashing, JWT, CSRF, hash chain, masking.

This module is *pure* (no DB / no FastAPI imports). It is intentionally
lightweight so it can be reused from workers and CLI utilities.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Final, cast

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# ---------------------------------------------------------------------------
# RBAC role taxonomy
# ---------------------------------------------------------------------------
#
# The canonical list lives in ``app.models.enums.UserRole`` but is duplicated
# here as a *flat tuple* so this module stays import-light (no SQLAlchemy /
# Pydantic dependency). Tests assert the two stay in lock-step.

ROLE_VIEWER: Final[str] = "viewer"
ROLE_DRAFTER: Final[str] = "drafter"
ROLE_REVIEWER: Final[str] = "reviewer"
ROLE_APPROVER: Final[str] = "approver"
ROLE_ADMIN: Final[str] = "admin"
ROLE_AUDITOR: Final[str] = "auditor"
ROLE_GUEST: Final[str] = "guest"

ALL_ROLES: Final[tuple[str, ...]] = (
    ROLE_VIEWER,
    ROLE_DRAFTER,
    ROLE_REVIEWER,
    ROLE_APPROVER,
    ROLE_ADMIN,
    ROLE_AUDITOR,
    ROLE_GUEST,
)


class AuthorizationError(PermissionError):
    """Raised when an RBAC check fails. Always maps to HTTP 403."""


def role_can(user_role: str | None, allowed: tuple[str, ...] | set[str]) -> bool:
    """Fail-closed RBAC predicate.

    Returns ``True`` only when ``user_role`` is one of ``allowed``. Empty /
    unknown roles always fail. ``admin`` is *not* automatically wildcarded —
    each endpoint must list it explicitly so the matrix in
    ``docs/security_policy.md`` stays authoritative.
    """
    if not user_role:
        return False
    if user_role not in ALL_ROLES:
        return False
    return user_role in set(allowed)


def ensure_role(user_role: str | None, allowed: tuple[str, ...] | set[str]) -> None:
    """Fail-closed companion to :func:`role_can` that raises on denial."""
    if not role_can(user_role, allowed):
        raise AuthorizationError(f"role '{user_role or '<anonymous>'}' is not authorized")


# ---------------------------------------------------------------------------
# Password hashing (bcrypt via passlib)
# ---------------------------------------------------------------------------

_pwd_context: Final[CryptContext] = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)


def hash_password(plain_password: str) -> str:
    """Hash a password using bcrypt with a sensible work factor."""
    if not plain_password:
        raise ValueError("password must not be empty")
    return str(_pwd_context.hash(plain_password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash. Returns False on any error."""
    if not plain_password or not hashed_password:
        return False
    try:
        return bool(_pwd_context.verify(plain_password, hashed_password))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# JWT encode / decode
# ---------------------------------------------------------------------------


def create_access_token(
    subject: str,
    *,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token.

    ``subject`` is set as ``sub``; ``extra_claims`` are merged but cannot
    override reserved claims (``sub``, ``exp``, ``iat``, ``nbf``, ``iss``,
    ``aud``).
    """
    if not subject:
        raise ValueError("subject must not be empty")

    now = datetime.now(tz=UTC)
    expire = now + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))

    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    if extra_claims:
        reserved = {"sub", "exp", "iat", "nbf", "iss", "aud"}
        for key, value in extra_claims.items():
            if key in reserved:
                continue
            payload[key] = value

    return str(
        jwt.encode(
            payload,
            settings.jwt_secret.get_secret_value(),
            algorithm=settings.jwt_algorithm,
        )
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT. Raises :class:`ValueError` on failure."""
    if not token:
        raise ValueError("token must not be empty")
    try:
        return cast(
            dict[str, Any],
            jwt.decode(
                token,
                settings.jwt_secret.get_secret_value(),
                algorithms=[settings.jwt_algorithm],
                audience=settings.jwt_audience,
                issuer=settings.jwt_issuer,
            ),
        )
    except JWTError as exc:
        raise ValueError(f"invalid token: {exc}") from exc


# ---------------------------------------------------------------------------
# API key verification (constant-time compare)
# ---------------------------------------------------------------------------


def verify_api_key(provided: str, expected: str) -> bool:
    """Constant-time comparison of two API keys."""
    if not provided or not expected:
        return False
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


# ---------------------------------------------------------------------------
# CSRF token
# ---------------------------------------------------------------------------


def generate_csrf_token(num_bytes: int = 32) -> str:
    """Generate a URL-safe CSRF token."""
    if num_bytes < 16:
        raise ValueError("CSRF token must be at least 16 bytes of entropy")
    return secrets.token_urlsafe(num_bytes)


def verify_csrf_token(provided: str, expected: str) -> bool:
    """Constant-time comparison of CSRF tokens."""
    if not provided or not expected:
        return False
    return hmac.compare_digest(provided, expected)


# ---------------------------------------------------------------------------
# Hash chain (audit log tamper detection)
# ---------------------------------------------------------------------------

_GENESIS_HASH: Final[str] = "0" * 64


def _canonical_json(payload: Any) -> bytes:
    """Stable, key-sorted JSON encoding for hashing."""
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def compute_hash_chain(prev_hash: str | None, payload: Any) -> str:
    """Compute the next ``hash_chain`` link.

    ``hash_N = HMAC-SHA256(secret, prev_hash || canonical_json(payload))``

    The secret is :attr:`Settings.hash_chain_secret` and ``prev_hash`` for
    the genesis row is 64 zeros.
    """
    previous = prev_hash if prev_hash else _GENESIS_HASH
    if not re.fullmatch(r"[0-9a-fA-F]{64}", previous):
        raise ValueError("prev_hash must be a 64-char hex digest")

    canonical = _canonical_json(payload)
    message = previous.encode("ascii") + b"|" + canonical
    secret = settings.hash_chain_secret.get_secret_value().encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def verify_hash_chain(prev_hash: str | None, payload: Any, expected_hash: str) -> bool:
    """Recompute the chain link and compare in constant time."""
    try:
        actual = compute_hash_chain(prev_hash, payload)
    except ValueError:
        return False
    return hmac.compare_digest(actual, expected_hash)


# ---------------------------------------------------------------------------
# Sensitive data masking
# ---------------------------------------------------------------------------

_MY_NUMBER_RE: Final[re.Pattern[str]] = re.compile(r"(?<!\d)(\d{4})\d{4}(\d{4})(?!\d)")
_PHONE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<!\d)(0\d{1,4})[-\s]?(\d{1,4})[-\s]?(\d{3,4})(?!\d)"
)
_EMAIL_RE: Final[re.Pattern[str]] = re.compile(
    r"([A-Za-z0-9._%+\-]+)@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})"
)


def _mask_my_number(match: re.Match[str]) -> str:
    return f"{match.group(1)}-****-{match.group(2)}"


def _mask_phone(match: re.Match[str]) -> str:
    return f"{match.group(1)}-****-{match.group(3)}"


def _mask_email(match: re.Match[str]) -> str:
    local = match.group(1)
    domain = match.group(2)
    head = local[0]
    tail = local[-1] if len(local) > 2 else ""
    middle = "*" * max(1, len(local) - 2)
    return f"{head}{middle}{tail}@{domain}"


def mask_sensitive(text: str) -> str:
    """Mask My Number (12 digits), phone numbers, and email local-parts.

    Designed for log output: never raise; pass through on non-string.
    """
    if not isinstance(text, str) or not text:
        return text
    masked = _MY_NUMBER_RE.sub(_mask_my_number, text)
    masked = _PHONE_RE.sub(_mask_phone, masked)
    masked = _EMAIL_RE.sub(_mask_email, masked)
    return masked


# ---------------------------------------------------------------------------
# Structured (recursive) masking — used by the response middleware
# ---------------------------------------------------------------------------


# Field-name allowlist that the middleware will completely drop from
# responses regardless of value. The DB layer is *already* expected to
# omit My Number from contract responses; this is the defence-in-depth
# net that ensures the literal column never escapes accidentally.
DROP_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "my_number",
        "myNumber",
        "individual_number",
        "mynumber",
    }
)

# Field-name allowlist whose *string* value will be passed through
# :func:`mask_sensitive` even if the value itself doesn't match a regex
# (e.g. an already-normalised phone column).
MASK_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "phone",
        "phone_number",
        "phoneNumber",
        "tel",
        "email",
        "mail",
        "contact",
    }
)


def mask_value(value: Any, *, _depth: int = 0) -> Any:
    """Recursively mask PII inside arbitrary JSON-like structures.

    * Strings are routed through :func:`mask_sensitive`.
    * ``dict`` keys in :data:`DROP_FIELDS` are removed wholesale.
    * ``dict`` keys in :data:`MASK_FIELDS` are forcibly masked even when
      the raw regex would have missed them (e.g. ``"taro"`` in an
      ``email`` field).
    * ``list`` / ``tuple`` / ``set`` are recursed element-wise.
    * Everything else is returned untouched.

    Recursion is bounded at 64 levels to fail-closed against pathological
    payloads (cycles aren't expected in JSON but a safety net is cheap).
    """
    if _depth > 64:
        return None
    if isinstance(value, str):
        return mask_sensitive(value)
    if isinstance(value, dict):
        out: dict[Any, Any] = {}
        for key, child in value.items():
            if isinstance(key, str) and key in DROP_FIELDS:
                # Drop the field entirely; never echo even a masked form.
                continue
            if isinstance(key, str) and key in MASK_FIELDS and isinstance(child, str):
                out[key] = mask_sensitive(child)
            else:
                out[key] = mask_value(child, _depth=_depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        return type(value)(mask_value(v, _depth=_depth + 1) for v in value)
    if isinstance(value, set):
        return {mask_value(v, _depth=_depth + 1) for v in value}
    return value


__all__ = [
    "ALL_ROLES",
    "DROP_FIELDS",
    "MASK_FIELDS",
    "ROLE_ADMIN",
    "ROLE_APPROVER",
    "ROLE_AUDITOR",
    "ROLE_DRAFTER",
    "ROLE_GUEST",
    "ROLE_REVIEWER",
    "ROLE_VIEWER",
    "AuthorizationError",
    "compute_hash_chain",
    "create_access_token",
    "decode_token",
    "ensure_role",
    "generate_csrf_token",
    "hash_password",
    "mask_sensitive",
    "mask_value",
    "role_can",
    "verify_api_key",
    "verify_csrf_token",
    "verify_hash_chain",
    "verify_password",
]
