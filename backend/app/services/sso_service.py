"""Single sign-on (Entra ID / OIDC) service.

Loop 2 implementation issues short-lived local JWTs so the rest of the
stack (API, frontend) can develop end-to-end without requiring an Entra
tenant. Loop 4 will replace ``exchange_code`` and ``verify_id_token``
with MSAL-backed implementations that validate against the real OIDC
JWKS.

Public surface (stable across loops):

* :meth:`SSOService.build_authorize_url` — produces the redirect URL.
* :meth:`SSOService.exchange_code` — exchanges an OIDC code for a
  token bundle.
* :meth:`SSOService.verify_id_token` — decodes and validates the JWT.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Final
from urllib.parse import urlencode

import structlog

from app.core.config import get_settings
from app.models.enums import UserRole

logger = structlog.get_logger(__name__)

_AUTHORIZE_PATH: Final[str] = (
    "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
)


class SSOError(RuntimeError):
    """Raised when authorization / verification fails."""


@dataclass(slots=True)
class Token:
    """OIDC token bundle returned by :meth:`SSOService.exchange_code`."""

    access_token: str
    id_token: str
    refresh_token: str | None
    token_type: str = "Bearer"
    expires_in: int = 3600
    scope: str | None = None


@dataclass(slots=True)
class UserClaims:
    """Validated identity claims extracted from an ID token."""

    sub: str
    upn: str
    name: str | None
    email: str | None
    role: UserRole
    tenant_id: str
    issued_at: datetime
    expires_at: datetime
    raw: dict[str, Any] = field(default_factory=dict)


class SSOService:
    """OIDC / Entra ID façade with a stub backend for Loop 2."""

    def __init__(self, *, mode: str | None = None) -> None:
        self._settings = get_settings()
        self._mode = (mode or os.getenv("SSO_MODE", "stub")).lower()
        self._secret = self._settings.jwt_secret.get_secret_value().encode("utf-8")
        self._issuer = self._settings.jwt_issuer
        self._audience = self._settings.jwt_audience
        self._expire = timedelta(minutes=self._settings.jwt_expire_minutes)

    # ------------------------------------------------------------------
    # Authorize URL
    # ------------------------------------------------------------------

    def build_authorize_url(
        self,
        *,
        state: str | None = None,
        nonce: str | None = None,
    ) -> str:
        """Construct the Entra ID OAuth2 authorize URL.

        Even in stub mode we produce a real-looking URL so the frontend
        can integrate against it; ``exchange_code`` will accept any code
        when ``mode == "stub"``.
        """
        params = {
            "client_id": self._settings.entra_client_id,
            "response_type": "code",
            "redirect_uri": self._settings.entra_redirect_uri,
            "response_mode": "query",
            "scope": self._settings.entra_scopes,
            "state": state or secrets.token_urlsafe(16),
            "nonce": nonce or secrets.token_urlsafe(16),
        }
        return _AUTHORIZE_PATH.format(tenant=self._settings.entra_tenant_id) + "?" + urlencode(params)

    # ------------------------------------------------------------------
    # Code exchange
    # ------------------------------------------------------------------

    def exchange_code(self, code: str) -> Token:
        """Exchange an OIDC ``code`` for a :class:`Token`.

        Stub mode issues a freshly-signed local JWT carrying a test user
        identity so the frontend can hit protected endpoints during
        Loop 2 demos.
        """
        if not code:
            raise SSOError("authorization code is required")

        if self._mode != "stub":  # pragma: no cover - real path in Loop 4
            return self._real_exchange_code(code)

        # Stub: derive a deterministic user from the code so tests can
        # replay scenarios reproducibly.
        sub_seed = hashlib.sha256(code.encode("utf-8")).hexdigest()[:16]
        upn = f"dev-{sub_seed}@example.co.jp"
        now = datetime.now(timezone.utc)
        claims = {
            "sub": sub_seed,
            "upn": upn,
            "name": "Loop 2 開発ユーザー",
            "email": upn,
            "role": UserRole.DRAFTER.value,
            "tid": self._settings.entra_tenant_id,
            "iat": int(now.timestamp()),
            "exp": int((now + self._expire).timestamp()),
            "iss": self._issuer,
            "aud": self._audience,
            "nonce": secrets.token_urlsafe(8),
        }
        id_token = _hs256_encode(claims, self._secret)
        access_token = _hs256_encode(
            {**claims, "typ": "access"}, self._secret
        )
        refresh_token = secrets.token_urlsafe(32)
        logger.info("sso.exchange_code.stub", upn=upn)
        return Token(
            access_token=access_token,
            id_token=id_token,
            refresh_token=refresh_token,
            expires_in=int(self._expire.total_seconds()),
            scope=self._settings.entra_scopes,
        )

    # ------------------------------------------------------------------
    # Token verification
    # ------------------------------------------------------------------

    def verify_id_token(self, token: str) -> UserClaims:
        """Decode and validate an ID token, returning :class:`UserClaims`."""
        if not token:
            raise SSOError("token is empty")
        try:
            payload = _hs256_decode(token, self._secret)
        except SSOError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise SSOError(f"invalid token: {exc}") from exc

        now = datetime.now(timezone.utc)
        exp = datetime.fromtimestamp(int(payload.get("exp", 0)), tz=timezone.utc)
        iat = datetime.fromtimestamp(int(payload.get("iat", 0)), tz=timezone.utc)
        if exp < now:
            raise SSOError("token has expired")
        if payload.get("iss") != self._issuer:
            raise SSOError(f"unexpected issuer: {payload.get('iss')}")
        if payload.get("aud") != self._audience:
            raise SSOError(f"unexpected audience: {payload.get('aud')}")

        try:
            role = UserRole(payload.get("role", UserRole.VIEWER.value))
        except ValueError:
            role = UserRole.VIEWER

        return UserClaims(
            sub=str(payload["sub"]),
            upn=str(payload.get("upn") or payload.get("preferred_username") or ""),
            name=payload.get("name"),
            email=payload.get("email"),
            role=role,
            tenant_id=str(payload.get("tid") or self._settings.entra_tenant_id),
            issued_at=iat,
            expires_at=exp,
            raw=payload,
        )

    # ------------------------------------------------------------------
    # Real (Loop 4) — placeholder
    # ------------------------------------------------------------------

    def _real_exchange_code(self, code: str) -> Token:  # pragma: no cover
        """Replaced in Loop 4 by the MSAL Confidential Client flow."""
        raise SSOError(
            "real OIDC exchange is not implemented in Loop 2 — set SSO_MODE=stub"
        )


# ---------------------------------------------------------------------------
# Minimal JOSE HS256 implementation
# ---------------------------------------------------------------------------
#
# We intentionally avoid importing python-jose at module load: in stub mode
# the dependency may not be present in slim test environments. The fixed
# HS256 + JSON header keeps the surface tiny and inspectable.


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _hs256_encode(payload: dict[str, Any], secret: bytes) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    sig = hmac.new(secret, signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url_encode(sig)}"


def _hs256_decode(token: str, secret: bytes) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise SSOError("token must have three segments")
    header_b64, payload_b64, sig_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected = hmac.new(secret, signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _b64url_decode(sig_b64)):
        raise SSOError("signature mismatch")
    return json.loads(_b64url_decode(payload_b64))
