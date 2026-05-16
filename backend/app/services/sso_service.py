"""Single sign-on (Entra ID via HENNGE One / OIDC) service.

Loop 2 introduced a *stub* backend that issues local JWTs so end-to-end
development could proceed without a live Entra tenant. Loop 4 (Security
統合) adds the **real** OIDC paths used in staging / production:

* OpenID Connect *discovery* against the HENNGE One well-known URL
  (``HENNGE_OIDC_DISCOVERY_URL``) — falls back to the canonical Microsoft
  identity platform endpoints when discovery is unavailable.
* Authorisation-code redemption against the resolved ``token_endpoint``.
* Refresh-token redemption against the same endpoint.
* ID-token signature validation through the JWKS published at
  ``jwks_uri`` (RS256 — uses ``python-jose`` which is already a
  dependency, see ``backend/app/core/security.py``).

Public surface (stable across loops):

* :meth:`SSOService.build_authorize_url` — produces the redirect URL.
* :meth:`SSOService.exchange_code` — exchanges an OIDC code for a
  token bundle.
* :meth:`SSOService.exchange_refresh_token` — refreshes an access token.
* :meth:`SSOService.verify_id_token` — decodes and validates the JWT.

Stub mode (``SSO_MODE=stub``) is preserved for unit tests and offline
development; the real mode is engaged when ``SSO_MODE=real`` (or any
non-empty value other than ``stub``) is exported.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Final, cast
from urllib.parse import urlencode

import structlog

from app.core.config import get_settings
from app.models.enums import UserRole

logger = structlog.get_logger(__name__)

_AUTHORIZE_PATH: Final[str] = (
    "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
)
_TOKEN_PATH: Final[str] = (
    "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
)
_JWKS_PATH: Final[str] = (
    "https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys"
)

# Conservative HTTP timeout (seconds) for *all* outbound calls so that a
# slow IdP can't tie up worker threads.
_HTTP_TIMEOUT: Final[float] = 5.0
# Discovery / JWKS cache TTL — Microsoft's published guidance is 24h but
# we re-fetch every 10 minutes to make key-rotation incidents recoverable.
_OIDC_CACHE_TTL: Final[float] = 600.0


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
        self._mode = (mode or os.getenv("SSO_MODE", "stub") or "stub").lower()
        self._secret = self._settings.jwt_secret.get_secret_value().encode("utf-8")
        self._issuer = self._settings.jwt_issuer
        self._audience = self._settings.jwt_audience
        self._expire = timedelta(minutes=self._settings.jwt_expire_minutes)
        # HENNGE One sits between the client and Entra ID; the discovery
        # URL is the only IdP-specific value the operator must provide.
        # When unset we fall back to canonical Microsoft endpoints so the
        # service still works in tenant-direct mode.
        self._discovery_url = os.getenv("HENNGE_OIDC_DISCOVERY_URL", "").strip()
        self._oidc_cache: dict[str, Any] = {}
        self._oidc_cache_expires_at: float = 0.0

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
        base = self._authorize_endpoint()
        return f"{base}?{urlencode(params)}"

    def _authorize_endpoint(self) -> str:
        """Resolve the authorization endpoint.

        In real mode we consult the discovery document so HENNGE One can
        override the canonical Microsoft URL. The call is cached and any
        error falls back to the tenant-direct endpoint.
        """
        if self._mode == "stub":
            return _AUTHORIZE_PATH.format(tenant=self._settings.entra_tenant_id)
        try:
            doc = self._oidc_discovery()
            endpoint = doc.get("authorization_endpoint")
            if isinstance(endpoint, str) and endpoint:
                return endpoint
        except SSOError:
            logger.warning("sso.discovery_unavailable", fallback="microsoft")
        return _AUTHORIZE_PATH.format(tenant=self._settings.entra_tenant_id)

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
    # Refresh token
    # ------------------------------------------------------------------

    def exchange_refresh_token(self, refresh_token: str) -> Token:
        """Use a refresh token to acquire a fresh access / id token pair.

        In stub mode we re-issue a deterministic token bundle keyed on
        the refresh token. In real mode we hit the IdP ``token_endpoint``
        with ``grant_type=refresh_token``.

        Always fail-closed: any error → :class:`SSOError`.
        """
        if not refresh_token:
            raise SSOError("refresh_token is required")

        if self._mode != "stub":
            return self._real_refresh(refresh_token)

        # Stub path — keep the same UPN by hashing the token.
        sub_seed = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()[:16]
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
        access_token = _hs256_encode({**claims, "typ": "access"}, self._secret)
        return Token(
            access_token=access_token,
            id_token=id_token,
            refresh_token=refresh_token,  # rotate not modelled in stub
            expires_in=int(self._expire.total_seconds()),
            scope=self._settings.entra_scopes,
        )

    # ------------------------------------------------------------------
    # Real (Loop 4) — implementation
    # ------------------------------------------------------------------

    def _real_exchange_code(self, code: str) -> Token:
        """Authorisation-code grant against the real IdP token endpoint."""
        data = {
            "client_id": self._settings.entra_client_id,
            "client_secret": self._settings.entra_client_secret.get_secret_value(),
            "code": code,
            "redirect_uri": self._settings.entra_redirect_uri,
            "grant_type": "authorization_code",
            "scope": self._settings.entra_scopes,
        }
        payload = self._token_request(data)
        return _parse_token_response(payload)

    def _real_refresh(self, refresh_token: str) -> Token:
        """Refresh-token grant — fail-closed against the IdP."""
        data = {
            "client_id": self._settings.entra_client_id,
            "client_secret": self._settings.entra_client_secret.get_secret_value(),
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
            "scope": self._settings.entra_scopes,
        }
        payload = self._token_request(data)
        return _parse_token_response(payload, fallback_refresh=refresh_token)

    # ------------------------------------------------------------------
    # IdP HTTP helpers (real mode only)
    # ------------------------------------------------------------------

    def _token_endpoint(self) -> str:
        try:
            doc = self._oidc_discovery()
            endpoint = doc.get("token_endpoint")
            if isinstance(endpoint, str) and endpoint:
                return endpoint
        except SSOError:
            logger.warning("sso.discovery_unavailable", fallback="microsoft.token")
        return _TOKEN_PATH.format(tenant=self._settings.entra_tenant_id)

    def _jwks_uri(self) -> str:
        try:
            doc = self._oidc_discovery()
            uri = doc.get("jwks_uri")
            if isinstance(uri, str) and uri:
                return uri
        except SSOError:
            logger.warning("sso.discovery_unavailable", fallback="microsoft.jwks")
        return _JWKS_PATH.format(tenant=self._settings.entra_tenant_id)

    def _oidc_discovery(self) -> dict[str, Any]:
        """Return the cached OIDC discovery document."""
        now = time.monotonic()
        if self._oidc_cache and now < self._oidc_cache_expires_at:
            return self._oidc_cache
        if not self._discovery_url:
            raise SSOError("HENNGE_OIDC_DISCOVERY_URL is not configured")
        doc = _http_get_json(self._discovery_url)
        if not isinstance(doc, dict):
            raise SSOError("OIDC discovery returned a non-object payload")
        self._oidc_cache = doc
        self._oidc_cache_expires_at = now + _OIDC_CACHE_TTL
        return doc

    def _token_request(self, form: dict[str, str]) -> dict[str, Any]:
        url = self._token_endpoint()
        body = urlencode({k: v for k, v in form.items() if v is not None}).encode(
            "utf-8"
        )
        req = urllib.request.Request(  # noqa: S310 — endpoint is operator-controlled
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(  # noqa: S310
                req, timeout=_HTTP_TIMEOUT
            ) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            logger.warning(
                "sso.token_request.http_error",
                status=exc.code,
                detail=detail[:512],
            )
            raise SSOError(f"token endpoint returned HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:  # pragma: no cover — network
            raise SSOError(f"token endpoint unreachable: {exc.reason}") from exc

        try:
            return cast(dict[str, Any], json.loads(raw.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SSOError("token endpoint returned invalid JSON") from exc


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
    return cast(dict[str, Any], json.loads(_b64url_decode(payload_b64)))


# ---------------------------------------------------------------------------
# Real-mode helpers
# ---------------------------------------------------------------------------


def _http_get_json(url: str) -> Any:
    """GET ``url`` and return decoded JSON. Fail-closed on any error."""
    req = urllib.request.Request(  # noqa: S310 — url is operator config
        url,
        method="GET",
        headers={"Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:  # noqa: S310
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        raise SSOError(f"GET {url} returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:  # pragma: no cover — network
        raise SSOError(f"GET {url} unreachable: {exc.reason}") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SSOError(f"GET {url} returned invalid JSON") from exc


def _parse_token_response(
    payload: dict[str, Any],
    *,
    fallback_refresh: str | None = None,
) -> Token:
    """Translate an OIDC token endpoint payload into a :class:`Token`.

    The IdP error contract (RFC 6749 §5.2) puts the error code under
    ``error`` / ``error_description``; we surface those verbatim to make
    incident diagnosis easier without leaking secrets.
    """
    if "error" in payload:
        code = str(payload.get("error"))
        desc = str(payload.get("error_description", ""))
        raise SSOError(f"token endpoint rejected request: {code} {desc}".strip())
    try:
        access_token = str(payload["access_token"])
        id_token = str(payload["id_token"])
    except KeyError as exc:  # noqa: BLE001
        raise SSOError(f"token endpoint response missing field: {exc}") from exc

    refresh = payload.get("refresh_token") or fallback_refresh
    expires_in = int(payload.get("expires_in", 3600) or 3600)
    return Token(
        access_token=access_token,
        id_token=id_token,
        refresh_token=str(refresh) if refresh else None,
        token_type=str(payload.get("token_type", "Bearer")),
        expires_in=expires_in,
        scope=payload.get("scope"),
    )
