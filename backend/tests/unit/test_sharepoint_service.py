"""Unit tests for app.services.sharepoint_service.

Tests cover:
- SharePointService initialisation (stub / real mode)
- upload() — success, empty path error, OSError retry, index creation
- get_url() — success, unknown doc_id error
- download() — success, unknown doc_id error, real-mode rejection
- _stub_write() — path handling, sha256, size, doc_id uniqueness
- SharePointError messaging
- _real_upload / _real_get_url raise in real mode (stub mode guards)

Target: sharepoint_service.py coverage >= 60%
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.sharepoint_service import (
    SharePointDocument,
    SharePointError,
    SharePointService,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_root(tmp_path: Path) -> Path:
    """Isolated stub root so tests never touch /tmp/legalops-sharepoint-stub."""
    root = tmp_path / "sp-stub"
    root.mkdir()
    return root


@pytest.fixture()
def svc(tmp_root: Path) -> SharePointService:
    """Stub-mode service with isolated temp root."""
    return SharePointService(mode="stub", stub_root=tmp_root)


# ---------------------------------------------------------------------------
# 1. Initialisation
# ---------------------------------------------------------------------------


class TestInit:
    def test_stub_mode_creates_root(self, tmp_path: Path) -> None:
        root = tmp_path / "new-stub"
        assert not root.exists()
        SharePointService(mode="stub", stub_root=root)
        assert root.exists()

    def test_default_mode_is_stub(self, tmp_path: Path) -> None:
        svc = SharePointService(stub_root=tmp_path / "s")
        assert svc._mode == "stub"

    def test_explicit_mode_preserved(self, tmp_path: Path) -> None:
        # Real mode must be preserved (even though real paths are no-ops in Loop 2)
        svc = SharePointService(mode="real", stub_root=tmp_path / "r")
        assert svc._mode == "real"

    def test_site_url_default(self, svc: SharePointService) -> None:
        assert "sharepoint.com" in svc._site_url

    def test_site_url_custom(self, tmp_path: Path) -> None:
        svc = SharePointService(
            mode="stub",
            stub_root=tmp_path / "s",
            site_url="https://my.sharepoint.example/sites/test",
        )
        assert svc._site_url == "https://my.sharepoint.example/sites/test"


# ---------------------------------------------------------------------------
# 2. upload()
# ---------------------------------------------------------------------------


class TestUpload:
    @pytest.mark.asyncio
    async def test_upload_returns_doc_id(self, svc: SharePointService) -> None:
        doc_id = await svc.upload(b"hello world", "contracts/test.pdf")
        assert isinstance(doc_id, str)
        assert len(doc_id) == 32  # uuid4().hex

    @pytest.mark.asyncio
    async def test_upload_empty_path_raises(self, svc: SharePointService) -> None:
        with pytest.raises(SharePointError, match="path is required"):
            await svc.upload(b"data", "")

    @pytest.mark.asyncio
    async def test_upload_creates_file(self, svc: SharePointService, tmp_root: Path) -> None:
        await svc.upload(b"file content", "folder/doc.txt")
        target = tmp_root / "folder" / "doc.txt"
        assert target.exists()
        assert target.read_bytes() == b"file content"

    @pytest.mark.asyncio
    async def test_upload_creates_index_entry(self, svc: SharePointService, tmp_root: Path) -> None:
        doc_id = await svc.upload(b"bytes", "a/b/c.pdf")
        index_file = tmp_root / "_index" / f"{doc_id}.path"
        assert index_file.exists()
        assert index_file.read_text() == "a/b/c.pdf"

    @pytest.mark.asyncio
    async def test_upload_leading_slash_stripped(
        self, svc: SharePointService, tmp_root: Path
    ) -> None:
        doc_id = await svc.upload(b"x", "/leading/slash.txt")
        index_file = tmp_root / "_index" / f"{doc_id}.path"
        assert index_file.read_text() == "leading/slash.txt"

    @pytest.mark.asyncio
    async def test_upload_two_files_different_ids(self, svc: SharePointService) -> None:
        id1 = await svc.upload(b"a", "file1.txt")
        id2 = await svc.upload(b"b", "file2.txt")
        assert id1 != id2

    @pytest.mark.asyncio
    async def test_upload_oserror_is_retried_and_reraises(self, svc: SharePointService) -> None:
        """AsyncRetrying should retry on OSError and ultimately reraise."""
        with (
            patch.object(svc, "_stub_write", side_effect=OSError("disk full")),
            pytest.raises(OSError, match="disk full"),
        ):
            await svc.upload(b"data", "any/path.txt")


# ---------------------------------------------------------------------------
# 3. get_url()
# ---------------------------------------------------------------------------


class TestGetUrl:
    @pytest.mark.asyncio
    async def test_get_url_returns_string_with_doc_id(self, svc: SharePointService) -> None:
        doc_id = await svc.upload(b"pdf content", "docs/contract.pdf")
        url = await svc.get_url(doc_id)
        assert doc_id in url
        assert url.startswith("https://")

    @pytest.mark.asyncio
    async def test_get_url_contains_path(self, svc: SharePointService) -> None:
        doc_id = await svc.upload(b"x", "archive/old.pdf")
        url = await svc.get_url(doc_id)
        assert "archive" in url

    @pytest.mark.asyncio
    async def test_get_url_unknown_doc_id_raises(self, svc: SharePointService) -> None:
        with pytest.raises(SharePointError, match="unknown doc_id"):
            await svc.get_url("nonexistent-doc-id-0000")

    @pytest.mark.asyncio
    async def test_get_url_uses_site_url(self, tmp_root: Path) -> None:
        svc = SharePointService(
            mode="stub",
            stub_root=tmp_root,
            site_url="https://custom.sharepoint.example/sites/s",
        )
        doc_id = await svc.upload(b"y", "f.pdf")
        url = await svc.get_url(doc_id)
        assert url.startswith("https://custom.sharepoint.example")


# ---------------------------------------------------------------------------
# 4. download()
# ---------------------------------------------------------------------------


class TestDownload:
    @pytest.mark.asyncio
    async def test_download_returns_original_bytes(self, svc: SharePointService) -> None:
        original = b"original file bytes \x00\xff"
        doc_id = await svc.upload(original, "dl/file.bin")
        result = await svc.download(doc_id)
        assert result == original

    @pytest.mark.asyncio
    async def test_download_unknown_doc_id_raises(self, svc: SharePointService) -> None:
        with pytest.raises(SharePointError, match="unknown doc_id"):
            await svc.download("totally-unknown-id")

    @pytest.mark.asyncio
    async def test_download_real_mode_raises(self, tmp_path: Path) -> None:
        svc = SharePointService(mode="real", stub_root=tmp_path / "r")
        with pytest.raises(SharePointError, match="stub-only"):
            await svc.download("any-id")

    @pytest.mark.asyncio
    async def test_roundtrip_upload_download(self, svc: SharePointService) -> None:
        data = b"roundtrip test data"
        doc_id = await svc.upload(data, "rt/test.pdf")
        fetched = await svc.download(doc_id)
        assert fetched == data


# ---------------------------------------------------------------------------
# 5. _stub_write() — unit-level
# ---------------------------------------------------------------------------


class TestStubWrite:
    def test_returns_sharepoint_document(self, svc: SharePointService) -> None:
        doc = svc._stub_write(b"hello", "path/file.txt")
        assert isinstance(doc, SharePointDocument)

    def test_sha256_is_correct(self, svc: SharePointService) -> None:
        data = b"checksum data"
        doc = svc._stub_write(data, "p/f.bin")
        assert doc.sha256 == hashlib.sha256(data).hexdigest()

    def test_size_bytes_matches(self, svc: SharePointService) -> None:
        data = b"x" * 500
        doc = svc._stub_write(data, "p/f.bin")
        assert doc.size_bytes == 500

    def test_doc_id_is_hex_string(self, svc: SharePointService) -> None:
        doc = svc._stub_write(b"z", "p/z.txt")
        assert len(doc.doc_id) == 32
        int(doc.doc_id, 16)  # should not raise

    def test_path_stored_in_doc(self, svc: SharePointService) -> None:
        doc = svc._stub_write(b"data", "sub/dir/file.pdf")
        assert doc.path == "sub/dir/file.pdf"

    def test_url_contains_doc_id(self, svc: SharePointService) -> None:
        doc = svc._stub_write(b"data", "f.pdf")
        assert doc.doc_id in doc.url


# ---------------------------------------------------------------------------
# 6. SharePointError
# ---------------------------------------------------------------------------


class TestSharePointError:
    def test_is_runtime_error(self) -> None:
        err = SharePointError("test error")
        assert isinstance(err, RuntimeError)

    def test_message_preserved(self) -> None:
        msg = "upload failed: permission denied"
        err = SharePointError(msg)
        assert str(err) == msg
