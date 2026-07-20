"""File-upload Pydantic schemas.

Mirrors ``docs/api_design.md`` section 13. The upload flow is two-step
(``init`` -> direct upload to SharePoint -> ``complete``) so that large
files do not transit the API server.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from app.models.enums import AttachmentStorage

_ACCEPTED_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_MAX_BYTES = 100 * 1024 * 1024  # 100 MB


class UploadInitRequest(BaseModel):
    """Body of ``POST /uploads/init`` — request a pre-signed upload URL."""

    contract_id: int | None = None
    filename: Annotated[str, Field(min_length=1, max_length=256)]
    mime_type: Annotated[str, Field(max_length=128)]
    size_bytes: Annotated[int, Field(ge=0, le=_MAX_BYTES)]
    is_primary: bool = False

    def is_mime_allowed(self) -> bool:
        """True if the MIME type is in the global accept-list."""
        return self.mime_type in _ACCEPTED_MIME


class UploadInitResponse(BaseModel):
    """Response of ``POST /uploads/init``."""

    upload_id: str
    upload_url: str | None = None
    upload_token: str
    storage: AttachmentStorage = AttachmentStorage.SHAREPOINT
    expires_in: int = 3600


class UploadCompleteRequest(BaseModel):
    """Body of ``POST /uploads/complete``."""

    upload_token: Annotated[str, Field(min_length=1)]
    contract_id: int | None = None
    sharepoint_item_id: Annotated[str, Field(min_length=1, max_length=256)]
    checksum_sha256: Annotated[str, Field(min_length=64, max_length=64)]
    is_primary: bool = False


class AttachmentRead(BaseModel):
    """Slim read schema for an :class:`app.models.Attachment`."""

    id: int
    contract_id: int
    filename: str
    mime_type: str
    size_bytes: int
    storage: AttachmentStorage
    checksum_sha256: str
    sharepoint_item_id: str
    is_primary: bool
    version: int

    model_config = {"from_attributes": True}


class UploadOut(AttachmentRead):
    """Public ``Out`` alias used by ``GET /uploads/{id}``."""

    download_url: str | None = None
