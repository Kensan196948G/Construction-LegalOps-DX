"""署名プロバイダアダプタ層の単体テスト（fail-closed 保証）."""

from __future__ import annotations

import pytest

from app.core.exceptions import ValidationError
from app.models.enums import SigningProviderId
from app.services.signing_provider import (
    SigningProviderUnavailableError,
    get_provider,
)


def test_demo_provider_is_default_and_needs_no_configuration() -> None:
    provider = get_provider("demo")
    assert provider.provider == SigningProviderId.DEMO
    # 設定不要で利用可能（fail-closed 対象外）
    provider.validate_config()


def test_manual_provider_needs_no_configuration() -> None:
    provider = get_provider(SigningProviderId.MANUAL)
    provider.validate_config()


def test_cloudsign_without_credentials_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLOUDSIGN_API_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDSIGN_API_KEY", raising=False)
    provider = get_provider("cloudsign")
    with pytest.raises(SigningProviderUnavailableError):
        provider.validate_config()


def test_docusign_without_credentials_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOCUSIGN_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("DOCUSIGN_INTEGRATION_KEY", raising=False)
    provider = get_provider("docusign")
    with pytest.raises(SigningProviderUnavailableError):
        provider.validate_config()


def test_unknown_provider_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        get_provider("not-a-provider")


async def test_demo_create_envelope_returns_external_reference() -> None:
    provider = get_provider("demo")
    external = await provider.create_envelope(
        provider_envelope_id="ES-ext-ABC", counterparty_email="x@example.jp"
    )
    assert external == "ES-ext-ABC"
