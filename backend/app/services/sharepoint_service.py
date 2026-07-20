"""SharePoint Online integration.

Loop 2 keeps uploaded bytes on the local filesystem under a configurable
root directory so the rest of the platform can persist attachments
without an Entra app registration. Real mode uses Microsoft Graph with the
client-credentials grant and fails closed when operator configuration is
missing or Graph rejects a request.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, cast
from uuid import uuid4

import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

_DEFAULT_STUB_ROOT: Final[Path] = Path(
    os.getenv("SHAREPOINT_STUB_ROOT", "/tmp/legalops-sharepoint-stub")  # nosec B108
)
_GRAPH_BASE_URL: Final[str] = "https://graph.microsoft.com/v1.0"
_GRAPH_SCOPE: Final[str] = "https://graph.microsoft.com/.default"
_HTTP_TIMEOUT: Final[float] = 10.0


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
    * ``real``: authenticates with Entra ID and calls Microsoft Graph.
    """

    def __init__(
        self,
        *,
        mode: str | None = None,
        stub_root: Path | None = None,
        site_url: str | None = None,
        drive_id: str | None = None,
    ) -> None:
        settings = get_settings()
        self._mode = (mode or os.getenv("SHAREPOINT_MODE", "stub") or "stub").lower()
        if settings.is_production and self._mode == "stub":
            raise RuntimeError("SHAREPOINT_MODE=stub is disabled when APP_ENV=production")
        self._stub_root = stub_root or _DEFAULT_STUB_ROOT
        self._site_url = site_url or os.getenv(
            "SHAREPOINT_SITE_URL", "https://contoso.sharepoint.com/sites/legalops"
        )
        self._drive_id = drive_id or os.getenv("SHAREPOINT_DRIVE_ID", "").strip()
        self._access_token: str | None = None
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
            uploaded_at=datetime.now(UTC),
            url=f"{self._site_url}/Shared%20Documents/{rel}?docid={doc_id}",
        )

    async def _real_upload(self, file_bytes: bytes, path: str) -> str:
        drive_id = self._require_drive_id()
        token = self._graph_access_token()
        encoded_path = urllib.parse.quote(path.lstrip("/"), safe="/")
        url = f"{_GRAPH_BASE_URL}/drives/{drive_id}/root:/{encoded_path}:/content"
        req = urllib.request.Request(  # noqa: S310  # nosec B310
            url,
            data=file_bytes,
            method="PUT",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/octet-stream",
                "Accept": "application/json",
            },
        )
        payload = self._read_json(req, action="sharepoint.upload")
        item_id = payload.get("id")
        if not isinstance(item_id, str) or not item_id:
            raise SharePointError("Graph upload response missing item id")
        logger.info("sharepoint.upload.real", item_id=item_id, path=path)
        return item_id

    async def _real_get_url(self, doc_id: str) -> str:
        drive_id = self._require_drive_id()
        token = self._graph_access_token()
        encoded_id = urllib.parse.quote(doc_id, safe="")
        url = f"{_GRAPH_BASE_URL}/drives/{drive_id}/items/{encoded_id}?$select=webUrl"
        req = urllib.request.Request(  # noqa: S310  # nosec B310
            url,
            method="GET",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
        )
        payload = self._read_json(req, action="sharepoint.get_url")
        web_url = payload.get("webUrl")
        if not isinstance(web_url, str) or not web_url:
            raise SharePointError("Graph item response missing webUrl")
        return web_url

    def _require_drive_id(self) -> str:
        if not self._drive_id:
            raise SharePointError("SHAREPOINT_DRIVE_ID is required for real SharePoint mode")
        return self._drive_id

    def _graph_access_token(self) -> str:
        if self._access_token:
            return self._access_token
        settings = get_settings()
        tenant = settings.entra_tenant_id
        token_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
        body = urllib.parse.urlencode(
            {
                "client_id": settings.entra_client_id,
                "client_secret": settings.entra_client_secret.get_secret_value(),
                "grant_type": "client_credentials",
                "scope": _GRAPH_SCOPE,
            }
        ).encode("utf-8")
        req = urllib.request.Request(  # noqa: S310  # nosec B310
            token_url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
        payload = self._read_json(req, action="sharepoint.token")
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise SharePointError("Entra token response missing access_token")
        self._access_token = token
        return token

    def _read_json(self, req: urllib.request.Request, *, action: str) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:  # noqa: S310  # nosec B310
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            logger.warning(action, status=exc.code, detail=detail[:512])
            raise SharePointError(f"{action} failed with HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise SharePointError(f"{action} endpoint unreachable: {exc.reason}") from exc

        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SharePointError(f"{action} returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise SharePointError(f"{action} returned a non-object JSON payload")
        if "error" in parsed:
            raise SharePointError(f"{action} rejected request")
        return cast(dict[str, Any], parsed)
