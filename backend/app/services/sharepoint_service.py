"""SharePoint Online integration (stub).

Loop 2 keeps uploaded bytes on the local filesystem under a configurable
root directory so the rest of the platform can persist attachments
without an Entra app registration. Loop 4 replaces these methods with
Microsoft Graph API calls.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final
from uuid import uuid4

import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = structlog.get_logger(__name__)

_DEFAULT_STUB_ROOT: Final[Path] = Path(
    os.getenv("SHAREPOINT_STUB_ROOT", "/tmp/legalops-sharepoint-stub")
)


class SharePointError(RuntimeError):
    """Raised when the SharePoint backend rejects an operation."""


@dataclass(slots=True)
class SharePointDocument:
    """Result of an upload."""

    doc_id: str
    path: str
    size_bytes: int
    sha256: str
    uploaded_at: datetime
    url: str


class SharePointService:
    """SharePoint Online integration.

    Two modes:

    * ``stub`` (default for Loop 2): writes to ``SHAREPOINT_STUB_ROOT``.
    * ``real`` (Loop 4): authenticates with MSAL and calls Microsoft Graph.
    """

    def __init__(
        self,
        *,
        mode: str | None = None,
        stub_root: Path | None = None,
        site_url: str | None = None,
    ) -> None:
        self._mode = (mode or os.getenv("SHAREPOINT_MODE", "stub")).lower()
        self._stub_root = stub_root or _DEFAULT_STUB_ROOT
        self._site_url = site_url or os.getenv(
            "SHAREPOINT_SITE_URL", "https://contoso.sharepoint.com/sites/legalops"
        )
        if self._mode == "stub":
            self._stub_root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def upload(self, file_bytes: bytes, path: str) -> str:
        """Upload ``file_bytes`` to ``path`` and return the doc ID."""
        if not path:
            raise SharePointError("path is required")
        if self._mode != "stub":  # pragma: no cover - Loop 4 path
            return await self._real_upload(file_bytes, path)

        # Stub path with retry to exercise the same code in tests.
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(min=0.1, max=1.0),
            retry=retry_if_exception_type(OSError),
            reraise=True,
        ):
            with attempt:
                doc = self._stub_write(file_bytes, path)
        logger.info(
            "sharepoint.upload.stub",
            doc_id=doc.doc_id,
            path=path,
            size=doc.size_bytes,
        )
        return doc.doc_id

    async def get_url(self, doc_id: str) -> str:
        """Return a viewable URL for ``doc_id``."""
        if self._mode != "stub":  # pragma: no cover - Loop 4 path
            return await self._real_get_url(doc_id)
        marker = self._stub_root / "_index" / f"{doc_id}.path"
        if not marker.exists():
            raise SharePointError(f"unknown doc_id: {doc_id}")
        path = marker.read_text(encoding="utf-8")
        return f"{self._site_url}/Shared%20Documents/{path}?docid={doc_id}"

    async def download(self, doc_id: str) -> bytes:
        """Stub-only helper used by tests and the file_parser bridge."""
        if self._mode != "stub":  # pragma: no cover
            raise SharePointError("download() is stub-only in Loop 2")
        marker = self._stub_root / "_index" / f"{doc_id}.path"
        if not marker.exists():
            raise SharePointError(f"unknown doc_id: {doc_id}")
        rel = marker.read_text(encoding="utf-8")
        return (self._stub_root / rel).read_bytes()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _stub_write(self, file_bytes: bytes, path: str) -> SharePointDocument:
        rel = path.lstrip("/")
        target = self._stub_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(file_bytes)

        doc_id = uuid4().hex
        index = self._stub_root / "_index"
        index.mkdir(parents=True, exist_ok=True)
        (index / f"{doc_id}.path").write_text(rel, encoding="utf-8")

        return SharePointDocument(
            doc_id=doc_id,
            path=rel,
            size_bytes=len(file_bytes),
            sha256=hashlib.sha256(file_bytes).hexdigest(),
            uploaded_at=datetime.now(timezone.utc),
            url=f"{self._site_url}/Shared%20Documents/{rel}?docid={doc_id}",
        )

    async def _real_upload(self, file_bytes: bytes, path: str) -> str:  # pragma: no cover
        raise SharePointError(
            "real SharePoint upload is not implemented in Loop 2 — set SHAREPOINT_MODE=stub"
        )

    async def _real_get_url(self, doc_id: str) -> str:  # pragma: no cover
        raise SharePointError(
            "real SharePoint URL resolution is not implemented in Loop 2 — set SHAREPOINT_MODE=stub"
        )
