"""Integration tests for upload session and attachment metadata flow."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.attachment import Attachment

CONTRACTS = "/api/v1/contracts"
UPLOADS = "/api/v1/uploads"


def _headers(role: str, subject: str) -> dict[str, str]:
    from app.core.security import create_access_token

    token = create_access_token(subject=subject, extra_claims={"role": role})
    return {"Authorization": f"Bearer {token}"}


def _session_for(engine: Any) -> Any:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    return async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)()


async def _attachment_by_id(engine: Any, attachment_id: int) -> Attachment:
    session = _session_for(engine)
    try:
        return (
            await session.execute(select(Attachment).where(Attachment.id == attachment_id))
        ).scalar_one()
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_upload_init_complete_get_and_delete(client: Any, test_engine: Any) -> None:
    """Upload metadata flow is DB-backed and soft-deletable."""
    headers = _headers("drafter", "upload-flow@example.com")

    created_contract = await client.post(
        CONTRACTS,
        headers=headers,
        json={
            "title": "Upload flow contract",
            "contract_type": "工事請負契約",
            "counterparty": "Upload建設",
            "department_id": 1,
        },
    )
    assert created_contract.status_code == 201, created_contract.text
    contract_id = created_contract.json()["id"]

    init = await client.post(
        f"{UPLOADS}/init",
        headers=headers,
        json={
            "contract_id": contract_id,
            "filename": "contract.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 12,
            "is_primary": True,
        },
    )
    assert init.status_code == 200, init.text
    token = init.json()["upload_token"]
    assert init.json()["upload_id"]
    assert init.json()["upload_url"] is None

    complete = await client.post(
        f"{UPLOADS}/complete",
        headers=headers,
        json={
            "upload_token": token,
            "contract_id": contract_id,
            "sharepoint_item_id": "sp-item-001",
            "checksum_sha256": "a" * 64,
            "is_primary": True,
        },
    )
    assert complete.status_code == 201, complete.text
    attachment_id = complete.json()["id"]
    assert complete.json()["contract_id"] == contract_id
    assert complete.json()["sharepoint_item_id"] == "sp-item-001"

    fetched = await client.get(f"{UPLOADS}/{attachment_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == attachment_id

    with patch(
        "app.services.upload_service.SharePointService.get_url",
        new=AsyncMock(return_value="https://contoso.sharepoint.com/sites/legalops/doc.aspx"),
    ):
        successful_download = await client.get(
            f"{UPLOADS}/{attachment_id}/download",
            headers=headers,
            follow_redirects=False,
        )
    assert successful_download.status_code == 302
    assert successful_download.headers["location"].startswith(
        "https://contoso.sharepoint.com/"
    )

    audit = await client.get(
        "/api/v1/audit-logs?action=upload.download",
        headers=_headers("admin", "upload-audit-admin@example.com"),
    )
    assert audit.status_code == 200
    download_rows = [
        row for row in audit.json()["items"] if row["target_id"] == attachment_id
    ]
    assert download_rows
    payload_after = download_rows[-1]["payload"]["after"]
    assert payload_after["external_url_resolved"] is True
    assert payload_after["external_write"] is False

    download = await client.get(f"{UPLOADS}/{attachment_id}/download", headers=headers)
    assert download.status_code == 502
    assert download.json()["detail"] == "sharepoint url unavailable"

    deleted = await client.delete(f"{UPLOADS}/{attachment_id}", headers=headers)
    assert deleted.status_code == 204
    persisted = await _attachment_by_id(test_engine, attachment_id)
    assert persisted.deleted_at is not None


@pytest.mark.asyncio
async def test_upload_init_rejects_unsupported_mime(client: Any) -> None:
    """Unsupported MIME types fail before token issuance."""
    headers = _headers("drafter", "upload-mime@example.com")

    response = await client.post(
        f"{UPLOADS}/init",
        headers=headers,
        json={
            "filename": "payload.exe",
            "mime_type": "application/x-msdownload",
            "size_bytes": 1,
        },
    )

    assert response.status_code == 415
