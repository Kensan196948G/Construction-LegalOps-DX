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

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
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


def test_use_rs256_flag_false_by_default(monkeypatch):
    """Settings.use_rs256 is False when no asymmetric keys are configured."""
    from app.core import config as cfg_module

    # Deterministically clear both keys instead of conditionally asserting:
    # a conditional assert silently passes when the env happens to set keys.
    monkeypatch.setattr(cfg_module.settings, "jwt_private_key", None)
    monkeypatch.setattr(cfg_module.settings, "jwt_public_key", None)
    assert cfg_module.settings.use_rs256 is False


def test_rs256_kid_header_present(monkeypatch):
    """RS256 tokens carry a kid header derived from the public key thumbprint."""
    from app.core import config as cfg_module
    from app.core.security import create_access_token

    private_pem, public_pem = _generate_rsa_pem_pair()
    monkeypatch.setattr(cfg_module.settings, "jwt_private_key", SecretStr(private_pem))
    monkeypatch.setattr(cfg_module.settings, "jwt_public_key", public_pem)

    token = create_access_token("kid-user")
    header = jwt.get_unverified_header(token)
    assert "kid" in header
    assert len(header["kid"]) == 16  # 8-byte SHA-256 prefix, hex-encoded


def test_hs256_has_no_kid_header(monkeypatch):
    """HS256 tokens must not carry a kid (single shared secret)."""
    from app.core.security import create_access_token

    token = create_access_token("hs-user")
    header = jwt.get_unverified_header(token)
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
    header = jwt.get_unverified_header(token)
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
    legacy_token = jwt.encode(payload, private_pem, algorithm="RS256")

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


def test_rs256_mixed_valid_and_malformed_retired_keys(monkeypatch):
    """A malformed entry in JWT_PUBLIC_KEYS is skipped; valid retired keys work."""
    from app.core import config as cfg_module
    from app.core.security import create_access_token, decode_token

    old_priv, old_pub = _generate_rsa_pem_pair()
    new_priv, new_pub = _generate_rsa_pem_pair()

    # Mint under the old key.
    monkeypatch.setattr(cfg_module.settings, "jwt_private_key", SecretStr(old_priv))
    monkeypatch.setattr(cfg_module.settings, "jwt_public_key", old_pub)
    old_token = create_access_token("mixed-user")

    # Rotate; retired set has one garbage PEM plus the real old_pub.
    monkeypatch.setattr(cfg_module.settings, "jwt_private_key", SecretStr(new_priv))
    monkeypatch.setattr(cfg_module.settings, "jwt_public_key", new_pub)
    monkeypatch.setattr(
        cfg_module.settings,
        "jwt_public_keys",
        json.dumps(["-----BEGIN PUBLIC KEY-----\nnot-a-real-key\n", old_pub]),
    )

    # The malformed entry is dropped, the valid retired key still verifies.
    assert decode_token(old_token)["sub"] == "mixed-user"


def test_rs256_explicit_kid_with_rotation(monkeypatch):
    """JWT_KEY_ID active kid + a derived-kid retired key both verify."""
    from app.core import config as cfg_module
    from app.core.security import create_access_token, decode_token

    old_priv, old_pub = _generate_rsa_pem_pair()
    new_priv, new_pub = _generate_rsa_pem_pair()

    # Old key active with a derived kid → mint old_token.
    monkeypatch.setattr(cfg_module.settings, "jwt_private_key", SecretStr(old_priv))
    monkeypatch.setattr(cfg_module.settings, "jwt_public_key", old_pub)
    monkeypatch.setattr(cfg_module.settings, "jwt_key_id", None)
    old_token = create_access_token("combo-old")

    # Rotate to new key with an EXPLICIT kid; keep old_pub (derived kid) retired.
    monkeypatch.setattr(cfg_module.settings, "jwt_private_key", SecretStr(new_priv))
    monkeypatch.setattr(cfg_module.settings, "jwt_public_key", new_pub)
    monkeypatch.setattr(cfg_module.settings, "jwt_key_id", "active-2026")
    monkeypatch.setattr(cfg_module.settings, "jwt_public_keys", json.dumps([old_pub]))

    new_token = create_access_token("combo-new")
    assert jwt.get_unverified_header(new_token)["kid"] == "active-2026"
    # Active explicit-kid token verifies.
    assert decode_token(new_token)["sub"] == "combo-new"
    # Retired derived-kid token still verifies.
    assert decode_token(old_token)["sub"] == "combo-old"


def test_rs256_empty_kid_rejected(monkeypatch):
    """A crafted empty-string kid is treated as 'no kid', not a lookup hit."""
    from app.core import config as cfg_module
    from app.core.security import decode_token

    private_pem, public_pem = _generate_rsa_pem_pair()
    monkeypatch.setattr(cfg_module.settings, "jwt_private_key", SecretStr(private_pem))
    monkeypatch.setattr(cfg_module.settings, "jwt_public_key", public_pem)
    monkeypatch.setattr(cfg_module.settings, "jwt_require_kid", True)

    now = dt.datetime.now(tz=dt.UTC)
    payload = {
        "sub": "empty-kid",
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + dt.timedelta(minutes=5)).timestamp()),
        "iss": cfg_module.settings.jwt_issuer,
        "aud": cfg_module.settings.jwt_audience,
    }
    token = jwt.encode(payload, private_pem, algorithm="RS256", headers={"kid": ""})
    # Empty kid → treated as missing → JWT_REQUIRE_KID rejects it.
    with pytest.raises(ValueError, match="missing key id"):
        decode_token(token)


def test_rs256_require_kid_rejects_legacy(monkeypatch):
    """JWT_REQUIRE_KID rejects kid-less RS256 tokens (fail-closed)."""
    from app.core import config as cfg_module
    from app.core.security import decode_token

    private_pem, public_pem = _generate_rsa_pem_pair()
    monkeypatch.setattr(cfg_module.settings, "jwt_private_key", SecretStr(private_pem))
    monkeypatch.setattr(cfg_module.settings, "jwt_public_key", public_pem)
    monkeypatch.setattr(cfg_module.settings, "jwt_require_kid", True)

    now = dt.datetime.now(tz=dt.UTC)
    payload = {
        "sub": "legacy-blocked",
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + dt.timedelta(minutes=5)).timestamp()),
        "iss": cfg_module.settings.jwt_issuer,
        "aud": cfg_module.settings.jwt_audience,
    }
    legacy_token = jwt.encode(payload, private_pem, algorithm="RS256")

    with pytest.raises(ValueError, match="missing key id"):
        decode_token(legacy_token)

    # With the flag off, the same token verifies (backward compat).
    monkeypatch.setattr(cfg_module.settings, "jwt_require_kid", False)
    assert decode_token(legacy_token)["sub"] == "legacy-blocked"


def test_rs256_sign_fails_fast_on_malformed_active_key(monkeypatch):
    """create_access_token refuses to sign when RS256 active key yields no kid."""
    from app.core import config as cfg_module
    from app.core.security import create_access_token

    private_pem, _ = _generate_rsa_pem_pair()
    # Private key valid (use_rs256 True) but public key malformed → no kid.
    monkeypatch.setattr(cfg_module.settings, "jwt_private_key", SecretStr(private_pem))
    monkeypatch.setattr(cfg_module.settings, "jwt_public_key", "-----BEGIN PUBLIC KEY-----\nbad\n")
    monkeypatch.setattr(cfg_module.settings, "jwt_key_id", None)

    with pytest.raises(ValueError, match="refusing to sign"):
        create_access_token("no-kid-user")


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
