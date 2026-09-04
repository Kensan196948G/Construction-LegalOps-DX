"""外部電子契約プロバイダのアダプタ層（ロードマップ #1 電子契約連携）.

方針（docs/LEGALOPS_BUSINESS_OS_ROADMAP_2026-09.md §3.2-5 と同じ fail-closed）:
* 既定は ``demo``（外部送信なし）。MVP/ローカルでは demo / manual のみ利用可能。
* CloudSign / DocuSign は実資格情報（環境変数）が設定されている場合のみ
  インスタンス化でき、未設定で利用を試みると :class:`SigningProviderUnavailableError`
  （503）を送出する。実 HTTP 送信は本ロードマップ Phase 1 の後続 Issue で実装し、
  本スライスでは IF と設定ゲートを固定する。
"""

from __future__ import annotations

import os
from typing import Protocol

from app.core.exceptions import AppError, ValidationError
from app.models.enums import SigningProviderId


class SigningProviderUnavailableError(AppError):
    """実プロバイダが未設定（fail-closed）で利用できないことを表す."""

    status_code = 503
    title = "Signing Provider Not Configured"
    type_slug = "signing-provider-not-configured"


class SigningProvider(Protocol):
    """外部電子契約サービスとの最小インターフェース."""

    provider: SigningProviderId

    def validate_config(self) -> None:
        """実プロバイダの設定を検証し、未設定なら例外を送出する."""
        ...

    async def create_envelope(
        self, *, provider_envelope_id: str, counterparty_email: str | None
    ) -> str:
        """外部サービス上にエンベロープを作成し、外部 ID を返す."""
        ...

    async def send(self, *, provider_envelope_id: str) -> None:
        """相手方へ署名依頼を送信する."""
        ...


class _DemoSigningProvider:
    """ローカル/MVP 用デモアダプタ（外部送信しない・決定的 ID）."""

    provider = SigningProviderId.DEMO

    def validate_config(self) -> None:
        return None

    async def create_envelope(
        self, *, provider_envelope_id: str, counterparty_email: str | None
    ) -> str:
        # デモでは外部 ID は受領した参照文字列をそのまま返す。
        return provider_envelope_id

    async def send(self, *, provider_envelope_id: str) -> None:
        return None


class _ManualProvider:
    """書面・手動運用のプレースホルダ（状態のみ管理）."""

    provider = SigningProviderId.MANUAL

    def validate_config(self) -> None:
        return None

    async def create_envelope(
        self, *, provider_envelope_id: str, counterparty_email: str | None
    ) -> str:
        return provider_envelope_id

    async def send(self, *, provider_envelope_id: str) -> None:
        return None


def _cloudsign_env_configured() -> bool:
    return bool(os.getenv("CLOUDSIGN_API_TOKEN") or os.getenv("CLOUDSIGN_API_KEY"))


def _docusign_env_configured() -> bool:
    return bool(
        os.getenv("DOCUSIGN_ACCESS_TOKEN")
        or os.getenv("DOCUSIGN_INTEGRATION_KEY")
    )


class _CloudSignProvider:
    """CloudSign アダプタ（実送信は後続 Issue・現状は設定ゲートのみ）."""

    provider = SigningProviderId.CLOUDSIGN

    def validate_config(self) -> None:
        if not _cloudsign_env_configured():
            raise SigningProviderUnavailableError(
                "CLOUDSIGN_API_TOKEN / CLOUDSIGN_API_KEY が未設定です。"
                "実連携には資格情報の投入（Human Gate）が必要です。"
            )

    async def create_envelope(
        self, *, provider_envelope_id: str, counterparty_email: str | None
    ) -> str:
        self.validate_config()
        # TODO(Phase 1 後続 Issue): CloudSign REST API 呼び出し実装
        raise SigningProviderUnavailableError(
            "CloudSign の実送信は未実装です（demo モードでは利用できません）。"
        )

    async def send(self, *, provider_envelope_id: str) -> None:
        self.validate_config()
        raise SigningProviderUnavailableError(
            "CloudSign の実送信は未実装です（demo モードでは利用できません）。"
        )


class _DocuSignProvider:
    """DocuSign アダプタ（実送信は後続 Issue・現状は設定ゲートのみ）."""

    provider = SigningProviderId.DOCUSIGN

    def validate_config(self) -> None:
        if not _docusign_env_configured():
            raise SigningProviderUnavailableError(
                "DOCUSIGN_ACCESS_TOKEN / DOCUSIGN_INTEGRATION_KEY が未設定です。"
                "実連携には資格情報の投入（Human Gate）が必要です。"
            )

    async def create_envelope(
        self, *, provider_envelope_id: str, counterparty_email: str | None
    ) -> str:
        self.validate_config()
        raise SigningProviderUnavailableError(
            "DocuSign の実送信は未実装です（demo モードでは利用できません）。"
        )

    async def send(self, *, provider_envelope_id: str) -> None:
        self.validate_config()
        raise SigningProviderUnavailableError(
            "DocuSign の実送信は未実装です（demo モードでは利用できません）。"
        )


def get_provider(provider: SigningProviderId | str) -> SigningProvider:
    """プロバイダ ID からアダプタを返す（デモモード既定・fail-closed）.

    ``SIGNING_PROVIDER`` 環境変数（既定 ``demo``）が優先される。
    ``production`` 環境で ``demo`` が指定された場合は :class:`SigningProviderUnavailableError`
    を送出する（本番でのデモ締結抑止）。
    """
    from app.core.config import get_settings

    settings = get_settings()
    try:
        resolved = SigningProviderId(str(provider).lower())
    except ValueError as exc:
        raise ValidationError(f"不正な署名プロバイダ: {provider!r}") from exc
    env_override = (os.getenv("SIGNING_PROVIDER") or "").strip().lower()
    if env_override and SigningProviderId(env_override) != resolved:
        resolved = SigningProviderId(env_override)

    if settings.is_production and resolved in {SigningProviderId.DEMO, SigningProviderId.MANUAL}:
        raise SigningProviderUnavailableError(
            f"production 環境では {resolved.value} は利用できません。"
            "実プロバイダ（cloudsign / docusign）を設定してください。"
        )

    registry: dict[SigningProviderId, SigningProvider] = {
        SigningProviderId.DEMO: _DemoSigningProvider(),
        SigningProviderId.MANUAL: _ManualProvider(),
        SigningProviderId.CLOUDSIGN: _CloudSignProvider(),
        SigningProviderId.DOCUSIGN: _DocuSignProvider(),
    }
    adapter = registry.get(resolved)
    if adapter is None:  # pragma: no cover - defensive
        raise SigningProviderUnavailableError(f"未知のプロバイダ: {resolved.value}")
    return adapter


__all__ = [
    "SigningProvider",
    "SigningProviderUnavailableError",
    "get_provider",
]
