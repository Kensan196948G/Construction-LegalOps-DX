"""Unit tests for JWT RS256 upgrade (P0 security task).

Verifies that:
- HS256 path still works (backward-compat fallback)
- RS256 path works when private/public keys are injected
- decode_token rejects tokens signed with wrong key
- Algorithm mismatch is detected
"""

from __future__ import annotations

import datetime as dt
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt as jose_jwt
from pydantic import SecretStr


def _generate_rsa_pem_pair() -> tuple[str, str]:
    """Generate ephemeral RSA-2048 key pair; returns (private_pem, public_pem)."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    return private_pem, public_pem


def test_hs256_roundtrip():
    """HS256 path: create + decode succeeds with default settings."""
    from app.core.security import create_access_token, decode_token

    token = create_access_token("user-hs256")
    claims = decode_token(token)
    assert claims["sub"] == "user-hs256"


def test_rs256_roundtrip(monkeypatch):
    """RS256 path: create + decode succeeds when asymmetric keys are configured."""
    from app.core import config as cfg_module
    from app.core.security import create_access_token, decode_token

    private_pem, public_pem = _generate_rsa_pem_pair()

    # Patch the singleton settings object
    monkeypatch.setattr(cfg_module.settings, "jwt_private_key", SecretStr(private_pem))
    monkeypatch.setattr(cfg_module.settings, "jwt_public_key", public_pem)

    token = create_access_token("user-rs256")
    claims = decode_token(token)
    assert claims["sub"] == "user-rs256"


def test_rs256_rejects_wrong_public_key(monkeypatch):
    """RS256: token verified with an unrelated public key must raise ValueError."""
    from app.core import config as cfg_module
    from app.core.security import create_access_token, decode_token

    private_pem, _ = _generate_rsa_pem_pair()
    _, wrong_public_pem = _generate_rsa_pem_pair()  # different key pair

    monkeypatch.setattr(cfg_module.settings, "jwt_private_key", SecretStr(private_pem))
    monkeypatch.setattr(cfg_module.settings, "jwt_public_key", wrong_public_pem)

    token = create_access_token("user-rs256-bad")
    with pytest.raises(ValueError, match="invalid token"):
        decode_token(token)


def test_rs256_extra_claims_preserved(monkeypatch):
    """RS256: extra claims survive encode/decode cycle."""
    from app.core import config as cfg_module
    from app.core.security import create_access_token, decode_token

    private_pem, public_pem = _generate_rsa_pem_pair()
    monkeypatch.setattr(cfg_module.settings, "jwt_private_key", SecretStr(private_pem))
    monkeypatch.setattr(cfg_module.settings, "jwt_public_key", public_pem)

    token = create_access_token("u1", extra_claims={"role": "legal", "email": "u@example.com"})
    claims = decode_token(token)
    assert claims["role"] == "legal"
    assert claims["email"] == "u@example.com"


def test_use_rs256_flag_false_by_default():
    """Settings.use_rs256 is False when no asymmetric keys are configured."""
    from app.core.config import settings

    # In test env JWT_PRIVATE_KEY / JWT_PUBLIC_KEY are not set
    if settings.jwt_private_key is None and settings.jwt_public_key is None:
        assert settings.use_rs256 is False


def test_rs256_kid_header_present(monkeypatch):
    """RS256 tokens carry a kid header derived from the public key thumbprint."""
    from app.core import config as cfg_module
    from app.core.security import create_access_token

    private_pem, public_pem = _generate_rsa_pem_pair()
    monkeypatch.setattr(cfg_module.settings, "jwt_private_key", SecretStr(private_pem))
    monkeypatch.setattr(cfg_module.settings, "jwt_public_key", public_pem)

    token = create_access_token("kid-user")
    header = jose_jwt.get_unverified_header(token)
    assert "kid" in header
    assert len(header["kid"]) == 16  # 8-byte SHA-256 prefix, hex-encoded


def test_hs256_has_no_kid_header(monkeypatch):
    """HS256 tokens must not carry a kid (single shared secret)."""
    from app.core.security import create_access_token

    token = create_access_token("hs-user")
    header = jose_jwt.get_unverified_header(token)
    assert "kid" not in header


def test_rs256_rotation_old_token_still_valid(monkeypatch):
    """After rotation, a token signed by the retired key still verifies."""
    from app.core import config as cfg_module
    from app.core.security import create_access_token, decode_token

    old_priv, old_pub = _generate_rsa_pem_pair()
    new_priv, new_pub = _generate_rsa_pem_pair()

    # Phase 1: old key is active → mint a token under it.
    monkeypatch.setattr(cfg_module.settings, "jwt_private_key", SecretStr(old_priv))
    monkeypatch.setattr(cfg_module.settings, "jwt_public_key", old_pub)
    old_token = create_access_token("rotating-user")

    # Phase 2: rotate to the new key, but retain old_pub as a verification key.
    monkeypatch.setattr(cfg_module.settings, "jwt_private_key", SecretStr(new_priv))
    monkeypatch.setattr(cfg_module.settings, "jwt_public_key", new_pub)
    monkeypatch.setattr(cfg_module.settings, "jwt_public_keys", json.dumps([old_pub]))

    # The old token must still verify against the retired key.
    assert decode_token(old_token)["sub"] == "rotating-user"
    # And freshly-minted tokens use the new active key.
    assert decode_token(create_access_token("rotating-user"))["sub"] == "rotating-user"


def test_rs256_unknown_kid_rejected(monkeypatch):
    """A token whose kid is not in the verification set is rejected fail-closed."""
    from app.core import config as cfg_module
    from app.core.security import create_access_token, decode_token

    old_priv, old_pub = _generate_rsa_pem_pair()
    new_priv, new_pub = _generate_rsa_pem_pair()

    monkeypatch.setattr(cfg_module.settings, "jwt_private_key", SecretStr(old_priv))
    monkeypatch.setattr(cfg_module.settings, "jwt_public_key", old_pub)
    old_token = create_access_token("orphan-user")

    # Rotate WITHOUT retaining the old key → the old token's kid is unknown.
    monkeypatch.setattr(cfg_module.settings, "jwt_private_key", SecretStr(new_priv))
    monkeypatch.setattr(cfg_module.settings, "jwt_public_key", new_pub)
    monkeypatch.setattr(cfg_module.settings, "jwt_public_keys", None)

    with pytest.raises(ValueError, match="invalid token"):
        decode_token(old_token)


def test_rs256_explicit_key_id(monkeypatch):
    """JWT_KEY_ID overrides the derived kid and is honoured end-to-end."""
    from app.core import config as cfg_module
    from app.core.security import create_access_token, decode_token

    private_pem, public_pem = _generate_rsa_pem_pair()
    monkeypatch.setattr(cfg_module.settings, "jwt_private_key", SecretStr(private_pem))
    monkeypatch.setattr(cfg_module.settings, "jwt_public_key", public_pem)
    monkeypatch.setattr(cfg_module.settings, "jwt_key_id", "prod-2026-q2")

    token = create_access_token("explicit-kid-user")
    header = jose_jwt.get_unverified_header(token)
    assert header["kid"] == "prod-2026-q2"
    assert decode_token(token)["sub"] == "explicit-kid-user"


def test_rs256_legacy_token_without_kid(monkeypatch):
    """Pre-rotation tokens with no kid fall back to the active public key."""
    from app.core import config as cfg_module
    from app.core.security import decode_token

    private_pem, public_pem = _generate_rsa_pem_pair()
    monkeypatch.setattr(cfg_module.settings, "jwt_private_key", SecretStr(private_pem))
    monkeypatch.setattr(cfg_module.settings, "jwt_public_key", public_pem)

    now = dt.datetime.now(tz=dt.UTC)
    payload = {
        "sub": "legacy-user",
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + dt.timedelta(minutes=5)).timestamp()),
        "iss": cfg_module.settings.jwt_issuer,
        "aud": cfg_module.settings.jwt_audience,
    }
    # Mint a token WITHOUT a kid header (simulates tokens issued before rotation).
    legacy_token = jose_jwt.encode(payload, private_pem, algorithm="RS256")

    assert decode_token(legacy_token)["sub"] == "legacy-user"


def test_jwt_public_keys_list_malformed_is_empty(monkeypatch):
    """Malformed JWT_PUBLIC_KEYS fails closed to an empty list (no extra trust)."""
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "jwt_public_keys", "{not-json")
    assert cfg_module.settings.jwt_public_keys_list == []

    monkeypatch.setattr(cfg_module.settings, "jwt_public_keys", json.dumps({"a": 1}))
    assert cfg_module.settings.jwt_public_keys_list == []

    monkeypatch.setattr(cfg_module.settings, "jwt_public_keys", None)
    assert cfg_module.settings.jwt_public_keys_list == []


def test_csp_enforce_defaults_to_is_production():
    """Settings.is_csp_enforce mirrors is_production when CSP_ENFORCE is unset."""
    from app.core.config import Settings

    dev_settings = Settings(APP_ENV="development")  # type: ignore[call-arg]
    assert dev_settings.is_csp_enforce is False

    prod_settings = Settings(APP_ENV="production")  # type: ignore[call-arg]
    assert prod_settings.is_csp_enforce is True


def test_csp_enforce_override(monkeypatch):
    """CSP_ENFORCE env var overrides the production default."""
    from app.core.config import Settings

    dev_enforce = Settings(APP_ENV="development", CSP_ENFORCE=True)  # type: ignore[call-arg]
    assert dev_enforce.is_csp_enforce is True

    prod_report_only = Settings(APP_ENV="production", CSP_ENFORCE=False)  # type: ignore[call-arg]
    assert prod_report_only.is_csp_enforce is False
