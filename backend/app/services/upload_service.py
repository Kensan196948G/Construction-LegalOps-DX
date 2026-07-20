"""Upload service with signed sessions and attachment metadata persistence."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.deps import CurrentUser
from app.models.attachment import Attachment
from app.models.contract import Contract
from app.models.enums import AttachmentStorage
from app.schemas.upload import (
    UploadCompleteRequest,
    UploadInitRequest,
    UploadInitResponse,
)
from app.services.sharepoint_service import SharePointService

ALLOWED_MIME_TYPES: Final[frozenset[str]] = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)
UPLOAD_TOKEN_TTL_SECONDS: Final[int] = 3600


def _secret() -> bytes:
    return settings.jwt_secret.get_secret_value().encode("utf-8")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def _sign(payload: bytes) -> str:
    return _b64(hmac.new(_secret(), payload, hashlib.sha256).digest())


def _issue_token(claims: dict[str, Any]) -> str:
    payload = json.dumps(claims, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return f"{_b64(payload)}.{_sign(payload)}"


def _verify_token(token: str) -> dict[str, Any]:
    try:
        encoded_payload, signature = token.split(".", 1)
        payload = _unb64(encoded_payload)
    except ValueError as exc:
        raise ValueError("invalid upload token") from exc

    if not hmac.compare_digest(signature, _sign(payload)):
        raise ValueError("invalid upload token signature")
    parsed = json.loads(payload.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("invalid upload token payload")
    claims: dict[str, Any] = parsed
    expires_at = datetime.fromtimestamp(int(claims["exp"]), tz=UTC)
    if expires_at < datetime.now(UTC):
        raise ValueError("upload token expired")
    return claims


async def _ensure_contract(session: AsyncSession, contract_id: int | None) -> None:
    if contract_id is None:
        return
    exists = (
        await session.execute(
            select(Contract.id).where(
                Contract.id == contract_id,
                Contract.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if exists is None:
        raise LookupError("contract not found")


async def create_upload_session(
    session: AsyncSession,
    *,
    requester: CurrentUser,
    payload: UploadInitRequest,
) -> UploadInitResponse:
    """Return a signed upload token for a later completion callback.

    Until the approved SharePoint/Graph direct-upload route is configured,
    do not expose pseudo external URLs to callers. The completion token remains
    auditable, while ``upload_url=None`` makes the missing external write path
    explicit at the API boundary.
    """
    if payload.mime_type not in ALLOWED_MIME_TYPES:
        raise ValueError(f"unsupported mime type: {payload.mime_type}")
    await _ensure_contract(session, payload.contract_id)

    now = datetime.now(UTC)
    upload_id = secrets.token_urlsafe(16)
    claims = {
        "jti": upload_id,
        "contract_id": payload.contract_id,
        "filename": payload.filename,
        "mime_type": payload.mime_type,
        "size_bytes": payload.size_bytes,
        "is_primary": payload.is_primary,
        "requested_by": requester.db_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=UPLOAD_TOKEN_TTL_SECONDS)).timestamp()),
    }
    token = _issue_token(claims)
    return UploadInitResponse(
        upload_id=upload_id,
        upload_url=None,
        upload_token=token,
        storage=AttachmentStorage.SHAREPOINT,
        expires_in=UPLOAD_TOKEN_TTL_SECONDS,
    )


async def complete_upload(
    session: AsyncSession,
    *,
    actor: CurrentUser,
    payload: UploadCompleteRequest,
) -> Attachment:
    """Persist attachment metadata after a direct upload completes."""
    claims = _verify_token(payload.upload_token)
    contract_id = payload.contract_id or claims.get("contract_id")
    if contract_id is None:
        raise ValueError("contract_id is required")
    await _ensure_contract(session, int(contract_id))

    requested_by = claims.get("requested_by")
    if actor.role not in {"admin", "reviewer", "approver"} and requested_by != actor.db_id:
        raise PermissionError("upload token belongs to another user")

    attachment = Attachment(
        contract_id=int(contract_id),
        filename=str(claims["filename"]),
        mime_type=str(claims["mime_type"]),
        size_bytes=int(claims["size_bytes"]),
        sharepoint_item_id=payload.sharepoint_item_id,
        storage=AttachmentStorage.SHAREPOINT.value,
        checksum_sha256=payload.checksum_sha256.lower(),
        is_primary=payload.is_primary or bool(claims.get("is_primary")),
        uploaded_by=actor.db_id or int(requested_by or 0),
        version=1,
    )
    session.add(attachment)
    await session.flush()
    await session.refresh(attachment)
    return attachment


async def get_upload(
    session: AsyncSession,
    *,
    upload_id: int,
    viewer: CurrentUser,
) -> Attachment | None:
    """Return visible attachment metadata."""
    stmt = select(Attachment).where(
        Attachment.id == upload_id,
        Attachment.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    attachment = result.scalar_one_or_none()
    if attachment is None:
        return None
    if viewer.role in {"admin", "auditor", "reviewer", "approver"}:
        return attachment
    if attachment.uploaded_by == viewer.db_id:
        return attachment
    return None


async def create_download_url(
    session: AsyncSession,
    *,
    upload_id: int,
    viewer: CurrentUser,
) -> str:
    """Return a SharePoint view URL for a visible attachment."""
    attachment = await get_upload(session, upload_id=upload_id, viewer=viewer)
    if attachment is None:
        raise LookupError("upload not found")
    return await SharePointService().get_url(attachment.sharepoint_item_id)


async def soft_delete(
    session: AsyncSession,
    *,
    upload_id: int,
    actor: CurrentUser,
) -> None:
    """Soft-delete an attachment when the actor is admin or uploader."""
    attachment = await get_upload(session, upload_id=upload_id, viewer=actor)
    if attachment is None:
        raise LookupError("upload not found")
    if actor.role != "admin" and attachment.uploaded_by != actor.db_id:
        raise PermissionError("forbidden")
    attachment.deleted_at = datetime.now(UTC)
    await session.flush()
