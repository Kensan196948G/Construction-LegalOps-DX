"""認証エンドポイント。

Entra ID OIDC SSO を中心とした認証フロー。
- `/auth/sso/login`: 認可エンドポイント URL 発行
- `/auth/sso/callback`: 認可コード受領と HttpOnly Cookie 設定
- `/auth/refresh`: アクセストークン更新
- `/auth/me`: 現在のユーザー情報
- `/auth/logout`: セッション破棄
"""

from __future__ import annotations

import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.deps import CurrentUser, get_current_user
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
        "Entra ID の認可エンドポイントへリダイレクトするための URL を発行する。"
    ),
)
async def sso_login(
    redirect_to: str | None = Query(default="/", description="ログイン後の遷移先"),
) -> LoginResponse:
    """Build the Entra ID authorization URL."""
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
    summary="SSO コールバック",
    description=(
        "Entra ID の認可コードを受領しトークンを取得する。"
        " 取得したセッション token を HttpOnly Cookie に設定する。"
    ),
)
async def sso_callback(
    code: str = Query(..., description="Entra ID 発行の認可コード"),
    state: str = Query(..., description="CSRF 対策の state"),
    session: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Exchange an authorization code and set the session cookie."""
    try:
        token_bundle = await auth_service.exchange_code(session, code=code, state=state)
    except Exception as exc:
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
    description=(
        "リフレッシュトークン (JWT) を検証し、新しいアクセストークンを払い出す。"
        " 認証は fail-closed: 検証失敗時は 401 を返す。"
    ),
)
async def refresh_token(
    payload: RefreshRequest,
) -> RefreshResponse:
    """Validate the refresh JWT and mint a fresh access token.

    The Loop 4 auth core (:mod:`app.core.security`) provides
    :func:`decode_token` and :func:`create_access_token`; the router is
    intentionally storage-free so it can run before the persistent
    session store ships.
    """
    from app.core.security import create_access_token, decode_token

    try:
        claims = decode_token(payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid refresh token: {exc}",
        ) from exc

    if claims.get("type") not in (None, "refresh"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token is not a refresh token",
        )
    subject = claims.get("sub")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="refresh token missing subject",
        )

    extra = {k: v for k, v in claims.items() if k in {"role", "department_ids", "email", "oid"}}
    new_access = create_access_token(subject=str(subject), extra_claims=extra)
    return RefreshResponse(
        access_token=new_access,
        token_type="Bearer",
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.get(
    "/me",
    response_model=MeResponse,
    summary="現在のユーザー情報",
    description="JWT で認証されたユーザーのプロファイル・ロール・部署を返す。",
)
async def get_me(
    current_user: CurrentUser = Depends(get_current_user),
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
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    await auth_service.revoke_session(session, user_id=current_user.db_id)
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="auth.logout",
        target_type="users",
        target_id=current_user.db_id,
        request=request,
    )
    response.delete_cookie("lo_session")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
