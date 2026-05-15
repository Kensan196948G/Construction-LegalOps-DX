"""認証エンドポイント。

Entra ID OIDC SSO を中心とした認証フロー。
- `/auth/sso/login`: 認可エンドポイント URL 発行 (現状 stub: Loop 4 で完全実装)
- `/auth/sso/callback`: 認可コード受領 (現状 stub: Loop 4 で完全実装)
- `/auth/refresh`: アクセストークン更新
- `/auth/me`: 現在のユーザー情報
- `/auth/logout`: セッション破棄
"""

from __future__ import annotations

import secrets
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginResponse,
    MeResponse,
    RefreshRequest,
    RefreshResponse,
)
from app.services import audit_service, auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get(
    "/sso/login",
    response_model=LoginResponse,
    summary="SSO ログイン開始",
    description=(
        "Entra ID の認可エンドポイントへリダイレクトするための URL を発行する (stub)。"
        " 本実装は Loop 4 で完全対応予定。"
    ),
)
async def sso_login(
    redirect_to: Optional[str] = Query(default="/", description="ログイン後の遷移先"),
) -> LoginResponse:
    """Entra ID 認可エンドポイントへの URL を組み立てる stub。"""
    state = secrets.token_urlsafe(24)
    params = {
        "client_id": settings.entra_client_id,
        "response_type": "code",
        "redirect_uri": settings.entra_redirect_uri,
        "scope": "openid profile email offline_access",
        "state": state,
        "response_mode": "query",
    }
    authorize_url = (
        f"https://login.microsoftonline.com/{settings.entra_tenant_id}"
        f"/oauth2/v2.0/authorize?{urlencode(params)}"
    )
    return LoginResponse(authorize_url=authorize_url, state=state, redirect_to=redirect_to)


@router.get(
    "/sso/callback",
    summary="SSO コールバック (stub)",
    description=(
        "Entra ID の認可コードを受領しトークンを取得する。"
        " 現状は HttpOnly Cookie を仮設定する stub。Loop 4 で完全実装。"
    ),
)
async def sso_callback(
    code: str = Query(..., description="Entra ID 発行の認可コード"),
    state: str = Query(..., description="CSRF 対策の state"),
    session: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Stub: 実装は Loop 4 にて Entra ID トークン交換 + Cookie 設定を行う。"""
    try:
        token_bundle = await auth_service.exchange_code(session, code=code, state=state)
    except Exception as exc:  # pragma: no cover - stub
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    response = RedirectResponse(url=token_bundle.redirect_to or "/", status_code=302)
    response.set_cookie(
        key="lo_session",
        value=token_bundle.session_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.session_cookie_max_age,
    )
    return response


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    summary="アクセストークン更新",
    description="リフレッシュトークンを用いて新しいアクセストークンを払い出す。",
)
async def refresh_token(
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_db),
) -> RefreshResponse:
    try:
        return await auth_service.refresh(session, refresh_token=payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@router.get(
    "/me",
    response_model=MeResponse,
    summary="現在のユーザー情報",
    description="JWT で認証されたユーザーのプロファイル・ロール・部署を返す。",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> MeResponse:
    return MeResponse.from_user(current_user)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="ログアウト",
    description="セッション Cookie を破棄し、Entra ID end_session への誘導 URL を返却。",
)
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    await auth_service.revoke_session(session, user_id=current_user.id)
    await audit_service.log(
        session,
        actor_id=current_user.id,
        action="auth.logout",
        target_type="users",
        target_id=current_user.id,
        request=request,
    )
    response.delete_cookie("lo_session")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
