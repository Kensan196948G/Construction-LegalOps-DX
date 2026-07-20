"""アップロードエンドポイント (SharePoint 連携)。

- POST `/uploads/init` : 署名付き upload token 発行
- POST `/uploads/complete` : アップロード完了報告とメタデータ登録
- GET `/uploads/{id}` : メタデータ取得
- GET `/uploads/{id}/download` : ダウンロード URL リダイレクト
- DELETE `/uploads/{id}` : 論理削除 (admin / 起案者・未署名段階)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, get_current_user, require_role
from app.schemas.upload import (
    UploadCompleteRequest,
    UploadInitRequest,
    UploadInitResponse,
    UploadOut,
)
from app.services import audit_service, upload_service
from app.services.sharepoint_service import SharePointError

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post(
    "/init",
    response_model=UploadInitResponse,
    summary="アップロード署名 token 発行",
    description=(
        "ファイルメタデータを検証し、完了報告に使う署名付き upload token を返す。"
        "本番 SharePoint/Graph 実アップロードは承認済み secret 投入後に外部経路で実施する。"
    ),
)
async def init_upload(
    payload: UploadInitRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_role("drafter", "reviewer", "admin")),
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
    try:
        response = await upload_service.create_upload_session(
            session, requester=current_user, payload=payload
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="contract not found")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="upload.init",
        target_type="uploads",
        target_id=response.upload_id,
        payload={"filename": payload.filename, "size": payload.size_bytes},
        request=request,
    )
    return response


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
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_role("drafter", "reviewer", "admin")),
) -> UploadOut:
    try:
        upload = await upload_service.complete_upload(session, actor=current_user, payload=payload)
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="upload session not found"
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    await audit_service.log(
        session,
        actor_id=current_user.db_id,
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
    current_user: CurrentUser = Depends(get_current_user),
) -> UploadOut:
    upload = await upload_service.get_upload(session, upload_id=upload_id, viewer=current_user)
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
    current_user: CurrentUser = Depends(get_current_user),
) -> RedirectResponse:
    try:
        url = await upload_service.create_download_url(
            session, upload_id=upload_id, viewer=current_user
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="upload not found")
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    except SharePointError:
        # Failed downloads are audit-relevant too: record before surfacing 502.
        await audit_service.log(
            session,
            actor_id=current_user.db_id,
            action="upload.download",
            target_type="uploads",
            target_id=upload_id,
            payload={"external_url_resolved": False, "external_write": False},
            request=request,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="sharepoint url unavailable",
        )

    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="upload.download",
        target_type="uploads",
        target_id=upload_id,
        payload={"external_url_resolved": True, "external_write": False},
        request=request,
    )
    return RedirectResponse(url=url, status_code=302)


@router.delete(
    "/{upload_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="アップロード論理削除",
)
async def delete_upload(
    upload_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    try:
        await upload_service.soft_delete(session, upload_id=upload_id, actor=current_user)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="upload not found")
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="upload.delete",
        target_type="uploads",
        target_id=upload_id,
        request=request,
    )
