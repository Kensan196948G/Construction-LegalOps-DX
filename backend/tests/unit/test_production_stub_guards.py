"""Production fail-closed guards for local/stub service adapters."""

from __future__ import annotations

import pytest
from pydantic import SecretStr


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    """Keep APP_ENV monkeypatches isolated from the cached settings singleton."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_sso_stub_mode_is_disabled_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.sso_service import SSOService

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("EDGE_AUTH_BOUNDARY", raising=False)

    with pytest.raises(RuntimeError, match="SSO_MODE=stub is disabled"):
        SSOService(mode="stub")


def test_sso_stub_mode_allowed_behind_cloudflare_access_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit EDGE_AUTH_BOUNDARY opt-in accepts stub identities in production.

    Approved by user decision 2026-07-20: Cloudflare Access is the sole
    authentication boundary (no Entra ID in this deployment).
    """
    from unittest.mock import MagicMock

    from app.services import sso_service

    settings = MagicMock()
    settings.is_production = True
    secret = MagicMock()
    secret.get_secret_value.return_value = "test-secret-key-for-unit-tests-only"
    settings.jwt_secret = secret
    settings.jwt_issuer = "test-issuer"
    settings.jwt_audience = "test-audience"
    settings.jwt_expire_minutes = 60

    monkeypatch.setenv("EDGE_AUTH_BOUNDARY", "cloudflare-access")
    monkeypatch.setattr(sso_service, "get_settings", lambda: settings)

    svc = sso_service.SSOService(mode="stub")
    assert svc._mode == "stub"


def test_sharepoint_stub_mode_is_disabled_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.sharepoint_service import SharePointService

    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(RuntimeError, match="SHAREPOINT_MODE=stub is disabled"):
        SharePointService(mode="stub")


def test_ai_review_stub_mode_is_disabled_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.ai_review import AIReviewService

    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(RuntimeError, match="AI_REVIEW_MODE=stub is disabled"):
        AIReviewService(mode="stub")


def test_ai_review_requires_real_key_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import ai_review

    class ProductionSettings:
        is_production = True
        claude_api_key = SecretStr("sk-ant-replace-me")
        claude_model = "test-model"
        claude_max_tokens = 1024
        claude_timeout_seconds = 10

    monkeypatch.setattr(ai_review, "get_settings", lambda: ProductionSettings())

    with pytest.raises(RuntimeError, match="CLAUDE_API_KEY must be configured"):
        ai_review.AIReviewService(mode="real")


def test_notification_stub_mode_is_disabled_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import notification_service

    class ProductionSettings:
        is_production = True

    monkeypatch.setattr(notification_service, "get_settings", lambda: ProductionSettings())

    with pytest.raises(RuntimeError, match="NOTIFY_MODE=stub is disabled"):
        notification_service.NotificationService(mode="stub")


def test_sharepoint_disabled_mode_constructs_but_rejects_operations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    from app.services import sharepoint_service

    class ProductionSettings:
        is_production = True

    monkeypatch.setattr(sharepoint_service, "get_settings", lambda: ProductionSettings())

    svc = sharepoint_service.SharePointService(mode="disabled")
    with pytest.raises(sharepoint_service.SharePointError, match="disabled"):
        asyncio.run(svc.upload(b"data", "a.txt"))
    with pytest.raises(sharepoint_service.SharePointError, match="disabled"):
        asyncio.run(svc.get_url("doc-1"))


def test_notification_disabled_mode_records_in_app_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    from app.services import notification_service

    class ProductionSettings:
        is_production = True

    monkeypatch.setattr(notification_service, "get_settings", lambda: ProductionSettings())

    svc = notification_service.NotificationService(mode="disabled")
    record = asyncio.run(svc.send_email(["user@example.com"], "件名", "本文"))
    # In-app record is delivered immediately; no external Graph call is made.
    assert record.status == notification_service.NotificationStatus.SENT


def test_unknown_modes_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import notification_service, sharepoint_service

    class DevSettings:
        is_production = False

    monkeypatch.setattr(sharepoint_service, "get_settings", lambda: DevSettings())
    monkeypatch.setattr(notification_service, "get_settings", lambda: DevSettings())

    with pytest.raises(RuntimeError, match="SHAREPOINT_MODE must be"):
        sharepoint_service.SharePointService(mode="reall")
    with pytest.raises(RuntimeError, match="NOTIFY_MODE must be"):
        notification_service.NotificationService(mode="reall")
