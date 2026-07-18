"""Security primitives: password hashing, JWT, CSRF, hash chain, masking.

This module is *pure* (no DB / no FastAPI imports). It is intentionally
lightweight so it can be reused from workers and CLI utilities.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Final

import jwt
from passlib.context import CryptContext

from app.core.config import settings

# Stdlib logger (no structlog dependency) keeps this module import-light so it
# stays usable from workers / CLI. Key-config problems are logged loudly so a
# malformed key never silently breaks authentication without a trace.
logger = logging.getLogger(__name__)

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


def _jwt_sign_key() -> str:
    """Return the signing key (RS256 private PEM or HS256 secret)."""
    if settings.use_rs256 and settings.jwt_private_key:
        return settings.jwt_private_key.get_secret_value()
    return settings.jwt_secret.get_secret_value()


def _jwt_verify_key() -> str:
    """Return the verification key (RS256 public PEM or HS256 secret)."""
    if settings.use_rs256 and settings.jwt_public_key:
        return settings.jwt_public_key
    return settings.jwt_secret.get_secret_value()


def _jwt_algorithm() -> str:
    """Return the active JWT algorithm (RS256 when keys are configured)."""
    return "RS256" if settings.use_rs256 else settings.jwt_algorithm


def _derive_kid(public_pem: str) -> str:
    """Derive a stable key id (kid) from an RSA public key.

    The kid is the first 16 hex chars of the SHA-256 digest over the key's
    DER ``SubjectPublicKeyInfo`` encoding. It is deterministic, so the signer
    and every verifier compute the same kid for a given key without any extra
    coordination (RFC 7638-style thumbprint, taken over DER for simplicity).

    ``cryptography`` is imported lazily to keep this module import-light.
    """
    from cryptography.hazmat.primitives import serialization

    public_key = serialization.load_pem_public_key(public_pem.encode("utf-8"))
    der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(der).hexdigest()[:16]


def _jwt_active_kid() -> str | None:
    """Return the kid for the active signing key, or ``None`` for HS256.

    Uses the explicit ``JWT_KEY_ID`` when set (e.g. to match an external IdP),
    else derives it from the active public key thumbprint. HS256 tokens carry
    no kid. Returns ``None`` (no kid header) if the kid cannot be derived.
    """
    if not settings.use_rs256:
        return None
    if settings.jwt_key_id:
        return settings.jwt_key_id
    if settings.jwt_public_key:
        try:
            return _derive_kid(settings.jwt_public_key)
        except Exception:
            # Malformed active public key: we cannot derive a kid. Return None
            # here (so verify-set building stays resilient and retired keys can
            # still verify), but log loudly. The sign path in
            # create_access_token turns this into a hard failure so we never
            # mint a kid-less token while RS256 rotation is expected.
            logger.warning("JWT active public key is malformed; cannot derive kid", exc_info=True)
            return None
    return None


def _jwt_public_key_set() -> dict[str, str]:
    """Build the ``{kid: public_pem}`` RS256 verification set.

    Combines the active public key (indexed by its possibly-overridden kid)
    with any retired keys from ``JWT_PUBLIC_KEYS`` (indexed by their derived
    thumbprint). Retired keys never override the active kid. Keys whose kid
    cannot be derived (malformed PEM) are skipped fail-closed.
    """
    key_set: dict[str, str] = {}
    active_kid = _jwt_active_kid()
    if active_kid and settings.jwt_public_key:
        key_set[active_kid] = settings.jwt_public_key
    for pem in settings.jwt_public_keys_list:
        try:
            kid = _derive_kid(pem)
        except Exception:
            # A malformed retired key is dropped from the verify set rather than
            # failing the whole build, so one bad entry in JWT_PUBLIC_KEYS does
            # not break verification of every other (valid) key. Logged so the
            # misconfiguration is visible instead of silently swallowed.
            logger.warning("Skipping malformed retired key in JWT_PUBLIC_KEYS", exc_info=True)
            continue
        key_set.setdefault(kid, pem)
    return key_set


def _jwt_resolve_verify_key(token: str) -> str:
    """Select the verification key for a token (kid-aware for RS256).

    - HS256: the shared secret (tokens carry no kid).
    - RS256 with a ``kid`` header: the matching public key, raising
      :class:`ValueError` (fail-closed) when the kid is unknown.
    - RS256 legacy token without a kid: falls back to the active public key,
      so tokens minted before rotation was introduced still verify — unless
      ``JWT_REQUIRE_KID`` is set, which rejects kid-less tokens (fail-closed)
      once a deployment has fully migrated to rotation.
    """
    if not settings.use_rs256:
        return _jwt_verify_key()
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise ValueError(f"invalid token: {exc}") from exc
    # Treat an empty-string kid the same as a missing one ("" is not a usable
    # key id), so a crafted {"kid": ""} cannot slip past the lookup branch.
    kid = header.get("kid")
    if kid:
        key = _jwt_public_key_set().get(kid)
        if key is None:
            raise ValueError("invalid token: unknown key id")
        return key
    if settings.jwt_require_kid:
        raise ValueError("invalid token: missing key id")
    return _jwt_verify_key()


def create_access_token(
    subject: str,
    *,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token.

    Uses RS256 (asymmetric) when ``JWT_PRIVATE_KEY`` / ``JWT_PUBLIC_KEY`` are
    configured; falls back to HS256 otherwise.  ``subject`` is set as ``sub``;
    ``extra_claims`` are merged but cannot override reserved claims.
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

    # Stamp a kid header for RS256 so verifiers can pick the exact key that
    # signed the token, enabling zero-downtime key rotation. HS256 tokens
    # carry no kid (single shared secret).
    active_kid = _jwt_active_kid()
    if settings.use_rs256 and active_kid is None:
        # Fail-fast on the sign path: RS256 is configured but we could not
        # derive a kid (malformed public key / bad JWT_KEY_ID config). Minting
        # a kid-less RS256 token here would quietly defeat rotation and could
        # be rejected later by JWT_REQUIRE_KID verifiers — better to refuse to
        # sign than to emit an un-rotatable token.
        raise ValueError(
            "RS256 is configured but no kid could be derived; refusing to sign "
            "a kid-less token (check JWT_PUBLIC_KEY / JWT_KEY_ID)"
        )
    headers = {"kid": active_kid} if active_kid else None
    return str(
        jwt.encode(
            payload,
            _jwt_sign_key(),
            algorithm=_jwt_algorithm(),
            headers=headers,
        )
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT. Raises :class:`ValueError` on failure."""
    if not token:
        raise ValueError("token must not be empty")
    # Resolve the verification key first (kid-aware for RS256); an unknown kid
    # fails closed with ValueError before any signature work is attempted.
    verify_key = _jwt_resolve_verify_key(token)
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            verify_key,
            algorithms=[_jwt_algorithm()],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
        return payload
    except jwt.PyJWTError as exc:
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
    total_digits = len(match.group(1)) + len(match.group(2)) + len(match.group(3))
    if total_digits < 10:
        return match.group(0)  # too short to be a real Japanese phone number
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
