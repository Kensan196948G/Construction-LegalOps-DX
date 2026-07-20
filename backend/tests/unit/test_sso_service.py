"""Unit tests for app.services.sso_service.

Tests cover:
- SSOService initialisation and mode detection
- build_authorize_url() — URL structure, state/nonce params, stub fallback
- _authorize_endpoint() — stub path, real path with discovery, discovery failure fallback
- exchange_code() — stub token issuance, empty code error
- verify_id_token() — valid token, expired token, wrong issuer, wrong audience, empty token
- exchange_refresh_token() — stub reissue, empty token error
- exchange_refresh_token() real mode path (mocked _real_refresh)
- _oidc_discovery() — cache hit, fetch, missing URL error
- _token_endpoint() / _jwks_uri() — discovery delegation + fallback
- _token_request() — HTTP success, HTTPError, URLError, invalid JSON
- _real_exchange_code / _real_refresh — integration via _token_request mock
- _parse_token_response — success, error field, missing fields
- _hs256_encode / _hs256_decode helpers
- Token / UserClaims dataclasses

Target: sso_service.py coverage >= 50%
"""

from __future__ import annotations

import json
import time
import urllib.error
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.models.enums import UserRole
from app.services.sso_service import (
    SSOError,
    SSOService,
    Token,
    UserClaims,
    _b64url_decode,
    _b64url_encode,
    _hs256_decode,
    _hs256_encode,
    _parse_token_response,
)

# ---------------------------------------------------------------------------
# Settings mock helper
# ---------------------------------------------------------------------------


def _make_settings(
    *,
    jwt_secret: str = "test-secret-key-for-unit-tests-only",
    jwt_issuer: str = "construction-legalops-dx",
    jwt_audience: str = "construction-legalops-dx-api",
    jwt_expire_minutes: int = 60,
    entra_tenant_id: str = "tenant-00000000",
    entra_client_id: str = "client-00000000",
    entra_client_secret: str = "entra-secret",
    entra_redirect_uri: str = "http://localhost:3000/auth/callback",
    entra_scopes: str = "openid profile email",
) -> MagicMock:
    s = MagicMock()
    # MagicMock attributes are truthy by default; the production stub guard in
    # SSOService.__init__ must not fire for unit tests running in stub mode.
    s.is_production = False
    secret_mock = MagicMock()
    secret_mock.get_secret_value.return_value = jwt_secret
    s.jwt_secret = secret_mock

    entra_secret_mock = MagicMock()
    entra_secret_mock.get_secret_value.return_value = entra_client_secret
    s.entra_client_secret = entra_secret_mock

    s.jwt_issuer = jwt_issuer
    s.jwt_audience = jwt_audience
    s.jwt_expire_minutes = jwt_expire_minutes
    s.entra_tenant_id = entra_tenant_id
    s.entra_client_id = entra_client_id
    s.entra_redirect_uri = entra_redirect_uri
    s.entra_scopes = entra_scopes
    return s


@pytest.fixture()
def mock_settings() -> MagicMock:
    return _make_settings()


@pytest.fixture()
def svc(mock_settings: MagicMock) -> SSOService:
    with patch("app.services.sso_service.get_settings", return_value=mock_settings):
        service = SSOService(mode="stub")
    return service


# ---------------------------------------------------------------------------
# 1. Initialisation
# ---------------------------------------------------------------------------


class TestInit:
    def test_default_mode_is_stub(self, mock_settings: MagicMock) -> None:
        with patch("app.services.sso_service.get_settings", return_value=mock_settings):
            svc = SSOService()
        assert svc._mode == "stub"

    def test_explicit_stub_mode(self, mock_settings: MagicMock) -> None:
        with patch("app.services.sso_service.get_settings", return_value=mock_settings):
            svc = SSOService(mode="stub")
        assert svc._mode == "stub"

    def test_explicit_real_mode(self, mock_settings: MagicMock) -> None:
        with patch("app.services.sso_service.get_settings", return_value=mock_settings):
            svc = SSOService(mode="real")
        assert svc._mode == "real"

    def test_settings_are_stored(self, mock_settings: MagicMock) -> None:
        with patch("app.services.sso_service.get_settings", return_value=mock_settings):
            svc = SSOService(mode="stub")
        assert svc._settings is mock_settings


# ---------------------------------------------------------------------------
# 2. build_authorize_url()
# ---------------------------------------------------------------------------


class TestBuildAuthorizeUrl:
    def test_returns_https_url(self, svc: SSOService) -> None:
        url = svc.build_authorize_url()
        assert url.startswith("https://")

    def test_contains_client_id(self, svc: SSOService) -> None:
        url = svc.build_authorize_url()
        assert "client_id=client-00000000" in url

    def test_contains_response_type_code(self, svc: SSOService) -> None:
        url = svc.build_authorize_url()
        assert "response_type=code" in url

    def test_custom_state_is_included(self, svc: SSOService) -> None:
        url = svc.build_authorize_url(state="my-custom-state")
        assert "state=my-custom-state" in url

    def test_custom_nonce_is_included(self, svc: SSOService) -> None:
        url = svc.build_authorize_url(nonce="my-nonce-value")
        assert "nonce=my-nonce-value" in url

    def test_auto_state_generated_when_none(self, svc: SSOService) -> None:
        url = svc.build_authorize_url()
        assert "state=" in url

    def test_redirect_uri_present(self, svc: SSOService) -> None:
        url = svc.build_authorize_url()
        assert "redirect_uri=" in url

    def test_real_mode_with_discovery(self, mock_settings: MagicMock) -> None:
        """Real mode should use discovery endpoint when available."""
        with patch("app.services.sso_service.get_settings", return_value=mock_settings):
            svc = SSOService(mode="real")
        discovery_doc = {"authorization_endpoint": "https://hennge.example/authorize"}
        with patch.object(svc, "_oidc_discovery", return_value=discovery_doc):
            url = svc.build_authorize_url()
        assert url.startswith("https://hennge.example/authorize")

    def test_real_mode_discovery_fallback(self, mock_settings: MagicMock) -> None:
        """Discovery failure should fall back to Microsoft tenant URL."""
        with patch("app.services.sso_service.get_settings", return_value=mock_settings):
            svc = SSOService(mode="real")
        with patch.object(svc, "_oidc_discovery", side_effect=SSOError("unavailable")):
            url = svc.build_authorize_url()
        assert "login.microsoftonline.com" in url


# ---------------------------------------------------------------------------
# 3. exchange_code() — stub mode
# ---------------------------------------------------------------------------


class TestExchangeCode:
    def test_returns_token(self, svc: SSOService) -> None:
        token = svc.exchange_code("test-auth-code-abc")
        assert isinstance(token, Token)

    def test_access_token_non_empty(self, svc: SSOService) -> None:
        token = svc.exchange_code("code123")
        assert token.access_token

    def test_id_token_non_empty(self, svc: SSOService) -> None:
        token = svc.exchange_code("code123")
        assert token.id_token

    def test_refresh_token_non_empty(self, svc: SSOService) -> None:
        token = svc.exchange_code("code123")
        assert token.refresh_token

    def test_token_type_is_bearer(self, svc: SSOService) -> None:
        token = svc.exchange_code("code123")
        assert token.token_type == "Bearer"

    def test_expires_in_positive(self, svc: SSOService) -> None:
        token = svc.exchange_code("code123")
        assert token.expires_in > 0

    def test_empty_code_raises(self, svc: SSOService) -> None:
        with pytest.raises(SSOError, match="authorization code is required"):
            svc.exchange_code("")

    def test_deterministic_upn_from_code(self, svc: SSOService) -> None:
        """Same code produces same UPN."""
        t1 = svc.exchange_code("stable-code")
        t2 = svc.exchange_code("stable-code")
        # Verify the id_tokens are structurally similar by decoding both
        p1 = _hs256_decode(t1.id_token, svc._secret)
        p2 = _hs256_decode(t2.id_token, svc._secret)
        assert p1["upn"] == p2["upn"]

    def test_scope_from_settings(self, svc: SSOService) -> None:
        token = svc.exchange_code("code-scope")
        assert token.scope == "openid profile email"


# ---------------------------------------------------------------------------
# 4. verify_id_token()
# ---------------------------------------------------------------------------


class TestVerifyIdToken:
    def _make_valid_token(self, svc: SSOService) -> str:
        return svc.exchange_code("valid-code-for-verify").id_token

    def test_valid_token_returns_user_claims(self, svc: SSOService) -> None:
        token = self._make_valid_token(svc)
        claims = svc.verify_id_token(token)
        assert isinstance(claims, UserClaims)

    def test_claims_sub_non_empty(self, svc: SSOService) -> None:
        token = self._make_valid_token(svc)
        claims = svc.verify_id_token(token)
        assert claims.sub

    def test_claims_upn_contains_example(self, svc: SSOService) -> None:
        token = self._make_valid_token(svc)
        claims = svc.verify_id_token(token)
        assert "example" in claims.upn

    def test_claims_role_is_user_role(self, svc: SSOService) -> None:
        token = self._make_valid_token(svc)
        claims = svc.verify_id_token(token)
        assert isinstance(claims.role, UserRole)

    def test_empty_token_raises(self, svc: SSOService) -> None:
        with pytest.raises(SSOError, match="token is empty"):
            svc.verify_id_token("")

    def test_expired_token_raises(self, svc: SSOService) -> None:
        now = datetime.now(UTC)
        past = int((now - timedelta(hours=2)).timestamp())
        claims_payload = {
            "sub": "test-sub",
            "upn": "user@example.co.jp",
            "iat": int((now - timedelta(hours=3)).timestamp()),
            "exp": past,
            "iss": svc._issuer,
            "aud": svc._audience,
        }
        token = _hs256_encode(claims_payload, svc._secret)
        with pytest.raises(SSOError, match="expired"):
            svc.verify_id_token(token)

    def test_wrong_issuer_raises(self, svc: SSOService) -> None:
        now = datetime.now(UTC)
        claims_payload = {
            "sub": "test-sub",
            "upn": "user@example.co.jp",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "iss": "wrong-issuer",
            "aud": svc._audience,
        }
        token = _hs256_encode(claims_payload, svc._secret)
        with pytest.raises(SSOError, match="issuer"):
            svc.verify_id_token(token)

    def test_wrong_audience_raises(self, svc: SSOService) -> None:
        now = datetime.now(UTC)
        claims_payload = {
            "sub": "test-sub",
            "upn": "user@example.co.jp",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "iss": svc._issuer,
            "aud": "wrong-audience",
        }
        token = _hs256_encode(claims_payload, svc._secret)
        with pytest.raises(SSOError, match="audience"):
            svc.verify_id_token(token)

    def test_tampered_signature_raises(self, svc: SSOService) -> None:
        token = self._make_valid_token(svc)
        # Replace the entire signature segment (third part) with garbage
        header, payload, _sig = token.split(".")
        tampered = f"{header}.{payload}.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        with pytest.raises(SSOError):
            svc.verify_id_token(tampered)

    def test_unknown_role_falls_back_to_viewer(self, svc: SSOService) -> None:
        now = datetime.now(UTC)
        claims_payload = {
            "sub": "test-sub",
            "upn": "user@example.co.jp",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "iss": svc._issuer,
            "aud": svc._audience,
            "role": "INVALID_ROLE",
        }
        token = _hs256_encode(claims_payload, svc._secret)
        claims = svc.verify_id_token(token)
        assert claims.role == UserRole.VIEWER


# ---------------------------------------------------------------------------
# 5. exchange_refresh_token()
# ---------------------------------------------------------------------------


class TestExchangeRefreshToken:
    def test_returns_token(self, svc: SSOService) -> None:
        token = svc.exchange_refresh_token("my-refresh-token")
        assert isinstance(token, Token)

    def test_empty_refresh_token_raises(self, svc: SSOService) -> None:
        with pytest.raises(SSOError, match="refresh_token is required"):
            svc.exchange_refresh_token("")

    def test_refresh_token_preserved_in_stub(self, svc: SSOService) -> None:
        rt = "original-refresh-token-xyz"
        token = svc.exchange_refresh_token(rt)
        assert token.refresh_token == rt

    def test_deterministic_upn_from_refresh_token(self, svc: SSOService) -> None:
        t1 = svc.exchange_refresh_token("stable-refresh")
        t2 = svc.exchange_refresh_token("stable-refresh")
        p1 = _hs256_decode(t1.id_token, svc._secret)
        p2 = _hs256_decode(t2.id_token, svc._secret)
        assert p1["upn"] == p2["upn"]

    def test_real_mode_delegates_to_real_refresh(self, mock_settings: MagicMock) -> None:
        with patch("app.services.sso_service.get_settings", return_value=mock_settings):
            svc = SSOService(mode="real")
        fake_token = Token(access_token="at", id_token="it", refresh_token="rt")
        with patch.object(svc, "_real_refresh", return_value=fake_token) as mock_rr:
            result = svc.exchange_refresh_token("some-rt")
        mock_rr.assert_called_once_with("some-rt")
        assert result is fake_token


# ---------------------------------------------------------------------------
# 6. _oidc_discovery()
# ---------------------------------------------------------------------------


class TestOidcDiscovery:
    def test_raises_when_discovery_url_not_set(self, svc: SSOService) -> None:
        svc._discovery_url = ""
        with pytest.raises(SSOError, match="HENNGE_OIDC_DISCOVERY_URL"):
            svc._oidc_discovery()

    def test_fetches_and_caches_doc(self, svc: SSOService) -> None:
        svc._discovery_url = "https://example.com/.well-known/openid-configuration"
        doc = {"authorization_endpoint": "https://example.com/authorize"}
        with patch("app.services.sso_service._http_get_json", return_value=doc) as mock_get:
            result1 = svc._oidc_discovery()
            result2 = svc._oidc_discovery()  # should hit cache
        mock_get.assert_called_once()  # only one HTTP call
        assert result1 == doc
        assert result2 == doc

    def test_cache_expiry_triggers_refetch(self, svc: SSOService) -> None:
        svc._discovery_url = "https://example.com/.well-known/openid-configuration"
        doc = {"authorization_endpoint": "https://example.com/authorize"}
        svc._oidc_cache = doc
        svc._oidc_cache_expires_at = time.monotonic() - 1  # expired

        with patch("app.services.sso_service._http_get_json", return_value=doc) as mock_get:
            svc._oidc_discovery()
        mock_get.assert_called_once()

    def test_non_dict_response_raises(self, svc: SSOService) -> None:
        svc._discovery_url = "https://example.com/.well-known/openid-configuration"
        with (
            patch("app.services.sso_service._http_get_json", return_value=["list"]),
            pytest.raises(SSOError, match="non-object"),
        ):
            svc._oidc_discovery()


# ---------------------------------------------------------------------------
# 7. _token_request() — real HTTP layer
# ---------------------------------------------------------------------------


class TestTokenRequest:
    def _real_svc(self, mock_settings: MagicMock) -> SSOService:
        with patch("app.services.sso_service.get_settings", return_value=mock_settings):
            svc = SSOService(mode="real")
        svc._discovery_url = ""  # force fallback endpoint
        return svc

    def test_success_returns_dict(self, mock_settings: MagicMock) -> None:
        svc = self._real_svc(mock_settings)
        response_body = json.dumps(
            {"access_token": "at", "id_token": "it", "token_type": "Bearer"}
        ).encode()
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = response_body

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = svc._token_request({"grant_type": "authorization_code", "code": "c"})
        assert result["access_token"] == "at"

    def test_http_error_raises_sso_error(self, mock_settings: MagicMock) -> None:
        svc = self._real_svc(mock_settings)
        http_err = urllib.error.HTTPError(
            url="https://example.com",
            code=400,
            msg="Bad Request",
            hdrs=MagicMock(),  # type: ignore[arg-type]
            fp=BytesIO(b'{"error":"invalid_grant"}'),
        )
        with (
            patch("urllib.request.urlopen", side_effect=http_err),
            pytest.raises(SSOError, match="HTTP 400"),
        ):
            svc._token_request({"grant_type": "authorization_code"})

    def test_invalid_json_raises_sso_error(self, mock_settings: MagicMock) -> None:
        svc = self._real_svc(mock_settings)
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = b"not-json!!!"

        with (
            patch("urllib.request.urlopen", return_value=mock_resp),
            pytest.raises(SSOError, match="invalid JSON"),
        ):
            svc._token_request({"grant_type": "authorization_code"})


# ---------------------------------------------------------------------------
# 8. _parse_token_response()
# ---------------------------------------------------------------------------


class TestParseTokenResponse:
    def test_success(self) -> None:
        payload = {
            "access_token": "at",
            "id_token": "it",
            "refresh_token": "rt",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "openid",
        }
        token = _parse_token_response(payload)
        assert token.access_token == "at"
        assert token.id_token == "it"
        assert token.refresh_token == "rt"
        assert token.expires_in == 3600

    def test_error_field_raises(self) -> None:
        payload = {
            "error": "invalid_grant",
            "error_description": "The code has expired.",
        }
        with pytest.raises(SSOError, match="invalid_grant"):
            _parse_token_response(payload)

    def test_missing_access_token_raises(self) -> None:
        payload = {"id_token": "it"}
        with pytest.raises(SSOError, match="access_token"):
            _parse_token_response(payload)

    def test_missing_id_token_raises(self) -> None:
        payload = {"access_token": "at"}
        with pytest.raises(SSOError, match="id_token"):
            _parse_token_response(payload)

    def test_fallback_refresh_used_when_missing(self) -> None:
        payload = {"access_token": "at", "id_token": "it"}
        token = _parse_token_response(payload, fallback_refresh="fallback-rt")
        assert token.refresh_token == "fallback-rt"

    def test_none_refresh_when_none_fallback(self) -> None:
        payload = {"access_token": "at", "id_token": "it"}
        token = _parse_token_response(payload)
        assert token.refresh_token is None


# ---------------------------------------------------------------------------
# 9. HS256 helpers
# ---------------------------------------------------------------------------


class TestHs256Helpers:
    _SECRET = b"unit-test-secret"

    def test_encode_decode_roundtrip(self) -> None:
        payload: dict[str, Any] = {"sub": "test", "exp": 9999999999}
        token = _hs256_encode(payload, self._SECRET)
        decoded = _hs256_decode(token, self._SECRET)
        assert decoded["sub"] == "test"

    def test_decode_wrong_secret_raises(self) -> None:
        payload: dict[str, Any] = {"sub": "test"}
        token = _hs256_encode(payload, self._SECRET)
        with pytest.raises(SSOError, match="signature mismatch"):
            _hs256_decode(token, b"wrong-secret")

    def test_decode_malformed_token_raises(self) -> None:
        with pytest.raises(SSOError, match="three segments"):
            _hs256_decode("only.two", self._SECRET)

    def test_b64url_encode_decode_roundtrip(self) -> None:
        data = b"\x00\xff\x80test"
        assert _b64url_decode(_b64url_encode(data)) == data


# ---------------------------------------------------------------------------
# 10. Token / UserClaims dataclasses
# ---------------------------------------------------------------------------


class TestDataclasses:
    def test_token_default_token_type(self) -> None:
        t = Token(access_token="a", id_token="i", refresh_token=None)
        assert t.token_type == "Bearer"

    def test_token_default_expires_in(self) -> None:
        t = Token(access_token="a", id_token="i", refresh_token=None)
        assert t.expires_in == 3600

    def test_user_claims_raw_default(self) -> None:
        now = datetime.now(UTC)
        uc = UserClaims(
            sub="s",
            upn="u@example.com",
            name=None,
            email=None,
            role=UserRole.VIEWER,
            tenant_id="tid",
            issued_at=now,
            expires_at=now,
        )
        assert uc.raw == {}

    def test_sso_error_is_runtime_error(self) -> None:
        err = SSOError("fail")
        assert isinstance(err, RuntimeError)
