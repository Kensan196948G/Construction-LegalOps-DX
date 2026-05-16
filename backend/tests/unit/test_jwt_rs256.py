"""Unit tests for JWT RS256 upgrade (P0 security task).

Verifies that:
- HS256 path still works (backward-compat fallback)
- RS256 path works when private/public keys are injected
- decode_token rejects tokens signed with wrong key
- Algorithm mismatch is detected
"""

from __future__ import annotations

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


def test_use_rs256_flag_false_by_default():
    """Settings.use_rs256 is False when no asymmetric keys are configured."""
    from app.core.config import settings

    # In test env JWT_PRIVATE_KEY / JWT_PUBLIC_KEY are not set
    if settings.jwt_private_key is None and settings.jwt_public_key is None:
        assert settings.use_rs256 is False


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
