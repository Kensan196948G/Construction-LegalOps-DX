"""Cloudflare Access JWT verification for Access-only production auth.

Cloudflare Access adds ``Cf-Access-Jwt-Assertion`` to origin requests. The
origin still has to verify that JWT against the Access application AUD and
team-domain issuer; otherwise a directly reachable origin could be spoofed by
headers alone.
"""

from __future__ import annotations

import time
from typing import Any, Final

import httpx
import jwt

from app.core.config import settings

_CERTS_TTL_SECONDS: Final[int] = 300

_cached_certs: dict[str, str] = {}
_cached_until: float = 0.0


def _certs_url() -> str:
    if settings.cloudflare_access_certs_url:
        return settings.cloudflare_access_certs_url
    if not settings.cloudflare_access_issuer:
        raise ValueError("CLOUDFLARE_ACCESS_ISSUER is required")
    issuer = settings.cloudflare_access_issuer.rstrip("/")
    return f"{issuer}/cdn-cgi/access/certs"


def _required_config() -> tuple[str, str]:
    issuer = settings.cloudflare_access_issuer
    audience = settings.cloudflare_access_audience
    if not issuer:
        raise ValueError("CLOUDFLARE_ACCESS_ISSUER is required")
    if not audience:
        raise ValueError("CLOUDFLARE_ACCESS_AUD is required")
    return issuer.rstrip("/"), audience


async def _load_certs() -> dict[str, str]:
    global _cached_certs, _cached_until

    now = time.monotonic()
    if _cached_certs and now < _cached_until:
        return _cached_certs

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(_certs_url())
        response.raise_for_status()
    payload = response.json()
    certs: dict[str, str] = {}
    for item in payload.get("public_certs", []):
        if not isinstance(item, dict):
            continue
        kid = item.get("kid")
        cert = item.get("cert")
        if isinstance(kid, str) and isinstance(cert, str) and kid and cert:
            certs[kid] = cert
    if not certs:
        raise ValueError("Cloudflare Access cert endpoint returned no public_certs")
    _cached_certs = certs
    _cached_until = now + _CERTS_TTL_SECONDS
    return certs


async def verify_access_jwt(token: str) -> dict[str, Any]:
    """Verify a Cloudflare Access JWT and return its claims.

    Raises ``ValueError`` for every authentication failure. Callers should map
    it to 401 without leaking token or cert details.
    """
    if not token:
        raise ValueError("missing Cloudflare Access JWT")
    issuer, audience = _required_config()
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise ValueError(f"invalid Cloudflare Access JWT header: {exc}") from exc
    kid = header.get("kid")
    if not isinstance(kid, str) or not kid:
        raise ValueError("Cloudflare Access JWT is missing kid")

    cert = (await _load_certs()).get(kid)
    if cert is None:
        raise ValueError("Cloudflare Access JWT kid is unknown")

    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            cert,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
        )
    except jwt.PyJWTError as exc:
        raise ValueError(f"invalid Cloudflare Access JWT: {exc}") from exc
    return claims


def clear_certs_cache() -> None:
    """Reset the in-process cert cache; intended for tests and key rotation drills."""
    global _cached_certs, _cached_until
    _cached_certs = {}
    _cached_until = 0.0
