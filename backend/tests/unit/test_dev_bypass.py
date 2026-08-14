"""Fail-closed dev/MVP authentication bypass guards."""

from __future__ import annotations

from app import deps
from app.core.exceptions import UnauthorizedError


def _env(app_env: str, bypass: str = "true") -> dict[str, str]:
    return {
        "APP_ENV": app_env,
        "AUTH_DEV_BYPASS": bypass,
        "DEV_USER_ID": "00000000-0000-0000-0000-000000000001",
        "DEV_USER_EMAIL": "demo@legalops-mvp.example.com",
        "DEV_USER_ROLE": "admin",
    }


def test_dev_bypass_disabled_by_default(monkeypatch) -> None:
    for key in ("APP_ENV", "AUTH_DEV_BYPASS"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.delenv("AUTH_DEV_BYPASS", raising=False)
    assert deps._dev_bypass_enabled() is False


def test_dev_bypass_never_active_in_production(monkeypatch) -> None:
    for key, value in _env("production").items():
        monkeypatch.setenv(key, value)
    assert deps._dev_bypass_enabled() is False


def test_dev_bypass_active_in_staging_with_explicit_flag(monkeypatch) -> None:
    for key, value in _env("staging", "1").items():
        monkeypatch.setenv(key, value)
    assert deps._dev_bypass_enabled() is True
    claims = deps._dev_bypass_claims()
    assert claims["sub"] == "00000000-0000-0000-0000-000000000001"
    assert claims["email"] == "demo@legalops-mvp.example.com"
    assert claims["role"] == "admin"


def test_dev_bypass_rejects_unknown_role_with_fallback(monkeypatch) -> None:
    for key, value in _env("staging").items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("DEV_USER_ROLE", "superuser")
    claims = deps._dev_bypass_claims()
    assert claims["role"] == "admin"


def test_dev_bypass_requires_dev_user_id(monkeypatch) -> None:
    for key, value in _env("staging").items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("DEV_USER_ID", raising=False)
    try:
        deps._dev_bypass_claims()
    except UnauthorizedError as exc:
        assert "DEV_USER_ID" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected UnauthorizedError")
