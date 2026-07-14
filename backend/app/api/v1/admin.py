"""管理者向け設定エンドポイント（ハイブリッド AI レビュー基盤・Issue #28）。

管理画面の「AI設定」パネルを駆動する 3 つの操作を提供する:

- GET  `/admin/ai-settings`            : 両プロバイダのマスク済み設定を取得（一覧表示）
- PUT  `/admin/ai-settings/{provider}` : APIキー・モデル・有効化を保存（「保存・設定」）
- POST `/admin/ai-settings/{provider}/test` : 接続確認（「設定テスト」）

セキュリティ不変条件:

* すべて ``require_role("admin")`` で保護する（管理者のみ）。
* 暗号化・復号・プロバイダ通信は :mod:`app.services.settings_service` に集約され、
  本ルーターは平文APIキーを一切扱わない（保存も読み出しもサービス層が境界）。
* 監査ログには「鍵が変更されたか」「有効/無効」「モデル」のみを残し、
  **APIキーの値そのものは決して記録しない**（平文流出ゼロ）。
* ``provider`` は ``Literal`` パスパラメータなので、不正値は DB の
  ``CheckConstraint`` に到達する前に HTTP 422 で拒否される（多層防御）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, get_current_user, require_role
from app.schemas.settings import (
    AiProvider,
    AiProviderConfigOut,
    AiSettingsOut,
    AiSettingsUpdateIn,
    ConnectionTestOut,
)
from app.services import audit_service
from app.services.settings_service import settings_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/ai-settings",
    response_model=AiSettingsOut,
    summary="AI設定の取得（マスク済み）",
    description=(
        "admin のみ。Perplexity / Claude 両プロバイダの設定を返す。"
        "APIキーは ``has_key`` と末尾マスク (``••••abcd``) のみで、平文は返さない。"
    ),
)
async def get_ai_settings(
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_role("admin")),
) -> AiSettingsOut:
    """両プロバイダのマスク済み設定行を返す（未保存は空行を合成）。"""
    return await settings_service.get_view(session)


@router.put(
    "/ai-settings/{provider}",
    response_model=AiProviderConfigOut,
    summary="AI設定の保存（保存・設定）",
    description=(
        "admin のみ。指定プロバイダの APIキー・モデル・有効化を保存する。"
        "``api_key`` 省略時は既存キーを維持、空文字でクリア、値ありで暗号化保存。"
    ),
)
async def upsert_ai_settings(
    provider: AiProvider,
    body: AiSettingsUpdateIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_role("admin")),
) -> AiProviderConfigOut:
    """プロバイダ設定を upsert し、変更証跡を監査ログに残す。

    監査 payload には鍵の値を含めず、「変更有無」「有効化」「モデル」のみ記録する。
    """
    # ``api_key`` がリクエストに含まれていれば鍵の変更（設定 or クリア）が発生する。
    key_changed = body.api_key is not None
    result = await settings_service.upsert(session, provider, body)

    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="ai_settings.update",
        target_type="ai_provider_settings",
        target_id=None,
        request=request,
        payload={
            "provider": provider,
            "key_changed": key_changed,
            "is_active": result.is_active,
            "model": result.model,
        },
    )
    return result


@router.post(
    "/ai-settings/{provider}/test",
    response_model=ConnectionTestOut,
    summary="AI設定の接続テスト（設定テスト）",
    description=(
        "admin のみ。保存済みキーでプロバイダへ疎通確認する。機密本文は送信しない。"
        "Claude は 2026-07-01 まで ``unavailable`` を返す（エラーにはしない）。"
    ),
)
async def test_ai_settings(
    provider: AiProvider,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_role("admin")),
) -> ConnectionTestOut:
    """保存済みキーで疎通確認し、結果（ok/failed/unavailable）を返す。"""
    result = await settings_service.test_connection(session, provider)

    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="ai_settings.test",
        target_type="ai_provider_settings",
        target_id=None,
        request=request,
        payload={"provider": provider, "status": result.status},
    )
    return result
