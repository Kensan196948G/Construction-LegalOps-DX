from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.services import cloudflare_access


def _key_pair() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


def _token(private_pem: str, *, kid: str = "kid-1", email: str = "user@example.com") -> str:
    now = datetime.now(tz=UTC)
    return str(
        jwt.encode(
            {
                "sub": "cf-subject-1",
                "email": email,
                "iss": "https://team.cloudflareaccess.com",
                "aud": "legalops-aud",
                "iat": int(now.timestamp()),
                "nbf": int(now.timestamp()),
                "exp": int((now + timedelta(minutes=5)).timestamp()),
            },
            private_pem,
            algorithm="RS256",
            headers={"kid": kid},
        )
    )


def _certificate_pem(private_key: rsa.RSAPrivateKey) -> str:
    """Self-signed X.509 certificate PEM, mirroring Cloudflare's cert endpoint."""
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "cf-test")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(tz=UTC) - timedelta(minutes=1))
        .not_valid_after(datetime.now(tz=UTC) + timedelta(days=1))
        .sign(private_key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")


@pytest.mark.asyncio
async def test_verify_access_jwt_validates_signature_issuer_and_audience(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_pem, public_pem = _key_pair()
    monkeypatch.setattr(
        cloudflare_access.settings,
        "cloudflare_access_issuer",
        "https://team.cloudflareaccess.com",
    )
    monkeypatch.setattr(cloudflare_access.settings, "cloudflare_access_audience", "legalops-aud")
    monkeypatch.setattr(
        cloudflare_access.settings,
        "cloudflare_access_certs_url",
        "https://team.cloudflareaccess.com/certs",
    )
    cloudflare_access.clear_certs_cache()
    async_client = httpx.AsyncClient

    async def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://team.cloudflareaccess.com/certs"
        return httpx.Response(200, json={"public_certs": [{"kid": "kid-1", "cert": public_pem}]})

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *args, **kwargs: async_client(transport=httpx.MockTransport(handler)),
    )

    claims = await cloudflare_access.verify_access_jwt(_token(private_pem))

    assert claims["email"] == "user@example.com"


@pytest.mark.asyncio
async def test_verify_access_jwt_accepts_pem_certificate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cloudflare serves PEM X.509 certificates; verify they are accepted."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    monkeypatch.setattr(
        cloudflare_access.settings,
        "cloudflare_access_issuer",
        "https://team.cloudflareaccess.com",
    )
    monkeypatch.setattr(cloudflare_access.settings, "cloudflare_access_audience", "legalops-aud")
    monkeypatch.setattr(
        cloudflare_access.settings,
        "cloudflare_access_certs_url",
        "https://team.cloudflareaccess.com/certs",
    )
    cloudflare_access.clear_certs_cache()
    async_client = httpx.AsyncClient

    async def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://team.cloudflareaccess.com/certs"
        return httpx.Response(
            200,
            json={"public_certs": [{"kid": "kid-1", "cert": _certificate_pem(private_key)}]},
        )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *args, **kwargs: async_client(transport=httpx.MockTransport(handler)),
    )

    claims = await cloudflare_access.verify_access_jwt(_token(private_pem))

    assert claims["email"] == "user@example.com"


@pytest.mark.asyncio
async def test_verify_access_jwt_rejects_unknown_kid(monkeypatch: pytest.MonkeyPatch) -> None:
    private_pem, public_pem = _key_pair()
    monkeypatch.setattr(
        cloudflare_access.settings,
        "cloudflare_access_issuer",
        "https://team.cloudflareaccess.com",
    )
    monkeypatch.setattr(cloudflare_access.settings, "cloudflare_access_audience", "legalops-aud")
    monkeypatch.setattr(
        cloudflare_access.settings,
        "cloudflare_access_certs_url",
        "https://team.cloudflareaccess.com/certs",
    )
    cloudflare_access.clear_certs_cache()
    async_client = httpx.AsyncClient

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"public_certs": [{"kid": "other-kid", "cert": public_pem}]},
        )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *args, **kwargs: async_client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(ValueError, match="kid is unknown"):
        await cloudflare_access.verify_access_jwt(_token(private_pem))
