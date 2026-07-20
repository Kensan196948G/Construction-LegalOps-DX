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

    with pytest.raises(RuntimeError, match="SSO_MODE=stub is disabled"):
        SSOService(mode="stub")


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
