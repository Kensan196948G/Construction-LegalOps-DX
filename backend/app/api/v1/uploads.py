"""アップロードエンドポイント (SharePoint 連携)。

- POST `/uploads/init` : 署名 URL 発行 (stub: SharePoint upload session を発行)
- POST `/uploads/complete` : アップロード完了報告とメタデータ登録
- GET `/uploads/{id}` : メタデータ取得
- GET `/uploads/{id}/download` : ダウンロード URL リダイレクト
- DELETE `/uploads/{id}` : 論理削除 (admin / 起案者・未署名段階)

Loop 5 で Microsoft Graph API による署名 URL 発行・チャンク UL を完全実装する。
"""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import get_current_user, require_role
from app.models.user import User
from app.schemas.upload import (
    UploadCompleteRequest,
    UploadInitRequest,
    UploadInitResponse,
    UploadOut,
)
from app.services import audit_service, upload_service

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post(
    "/init",
    response_model=UploadInitResponse,
    summary="アップロード署名 URL 発行 (stub)",
    description=(
        "SharePoint upload session を発行し、フロントが直接 PUT 可能な署名 URL を返す stub。"
        " Loop 5 で Microsoft Graph 連携を完全実装。"
    ),
)
async def init_upload(
    payload: UploadInitRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_role("site", "legal", "admin")),
) -> UploadInitResponse:
    if payload.size_bytes > 100 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="file exceeds 100 MB limit",
        )
    if payload.mime_type not in upload_service.ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"unsupported mime type: {payload.mime_type}",
        )
    response = await upload_service.create_upload_session(
        session, requester=current_user, payload=payload
    )
    await audit_service.log(
        session,
        actor_id=current_user.id,
        action="upload.init",
        target_type="uploads",
        target_id=response.upload_id,
        payload={"filename": payload.filename, "size": payload.size_bytes},
        request=request,
    )
    return cast(UploadInitResponse, response)


@router.post(
    "/complete",
    response_model=UploadOut,
    status_code=status.HTTP_201_CREATED,
    summary="アップロード完了",
    description="フロントがアップロードを完了した後、メタデータと SharePoint item ID を登録する。",
)
async def complete_upload(
    payload: UploadCompleteRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_role("site", "legal", "admin")),
) -> UploadOut:
    try:
        upload = await upload_service.complete_upload(
            session, actor=current_user, payload=payload
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="upload session not found"
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    await audit_service.log(
        session,
        actor_id=current_user.id,
        action="upload.complete",
        target_type="uploads",
        target_id=upload.id,
        payload={"contract_id": upload.contract_id, "checksum": upload.checksum_sha256},
        request=request,
    )
    return UploadOut.model_validate(upload)


@router.get(
    "/{upload_id}",
    response_model=UploadOut,
    summary="アップロードメタデータ取得",
)
async def get_upload(
    upload_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UploadOut:
    upload = await upload_service.get_upload(
        session, upload_id=upload_id, viewer=current_user
    )
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="upload not found")
    return UploadOut.model_validate(upload)


@router.get(
    "/{upload_id}/download",
    summary="ダウンロード署名 URL リダイレクト",
)
async def download_upload(
    upload_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RedirectResponse:
    try:
        url = await upload_service.create_download_url(
            session, upload_id=upload_id, viewer=current_user
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="upload not found")
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    await audit_service.log(
        session,
        actor_id=current_user.id,
        action="upload.download",
        target_type="uploads",
        target_id=upload_id,
        request=request,
    )
    return RedirectResponse(url=url, status_code=302)


@router.delete(
    "/{upload_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="アップロード論理削除",
)
async def delete_upload(
    upload_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    try:
        await upload_service.soft_delete(
            session, upload_id=upload_id, actor=current_user
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="upload not found")
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    await audit_service.log(
        session,
        actor_id=current_user.id,
        action="upload.delete",
        target_type="uploads",
        target_id=upload_id,
        request=request,
    )
