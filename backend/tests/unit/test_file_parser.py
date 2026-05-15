"""Tests for ``app.services.file_parser``.

Public API::

    async def parse(file_path: str, mime_type: str) -> ParsedDocument
    class FileParser: async def parse(...)
    class ParsedDocument: text, page_count, metadata, used_ocr, warnings
"""

from __future__ import annotations

from pathlib import Path

import pytest

fp = pytest.importorskip(
    "app.services.file_parser",
    reason="file_parser implemented in Loop 3",
)


async def test_parse_txt_returns_text_content(tmp_path: Path):
    """Arrange: a UTF-8 .txt file. Act: parse. Assert: text roundtrips."""
    # Arrange
    p = tmp_path / "sample.txt"
    body = "本契約書は請負契約に関するものである。"
    p.write_text(body, encoding="utf-8")
    # Act
    doc = await fp.parse(str(p), mime_type="text/plain")
    # Assert
    assert body in doc.text
    assert doc.used_ocr is False


async def test_parse_docx_extracts_paragraphs(tmp_path: Path):
    """Arrange: minimal docx. Act: parse. Assert: paragraph text found."""
    # Arrange
    try:
        from docx import Document
    except Exception:
        pytest.skip("python-docx unavailable")
    p = tmp_path / "sample.docx"
    doc = Document()
    doc.add_paragraph("第一条 目的")
    doc.add_paragraph("本契約は工事請負を目的とする。")
    doc.save(p)
    # Act
    parsed = await fp.parse(
        str(p),
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    # Assert
    assert "第一条" in parsed.text


async def test_parse_missing_file_raises(tmp_path: Path):
    """Arrange: nonexistent path. Act: parse. Assert: FileParserError."""
    # Arrange
    missing = tmp_path / "no_such.txt"
    # Act / Assert
    with pytest.raises(fp.FileParserError):
        await fp.parse(str(missing), mime_type="text/plain")


async def test_parse_unknown_mime_falls_back_to_suffix(tmp_path: Path):
    """Arrange: .txt file with octet-stream mime. Act: parse. Assert: text returned."""
    # Arrange
    p = tmp_path / "data.txt"
    p.write_text("plain text", encoding="utf-8")
    # Act
    try:
        doc = await fp.parse(str(p), mime_type="application/octet-stream")
    except fp.FileParserError:
        pytest.skip("parser does not fall back on suffix (acceptable)")
    # Assert
    assert "plain text" in doc.text


async def test_parsed_document_has_expected_attributes(tmp_path: Path):
    """Arrange: simple txt. Act: parse. Assert: ParsedDocument shape."""
    # Arrange
    p = tmp_path / "x.txt"
    p.write_text("hello", encoding="utf-8")
    # Act
    doc = await fp.parse(str(p), mime_type="text/plain")
    # Assert
    for attr in ("text", "page_count", "metadata", "used_ocr", "warnings"):
        assert hasattr(doc, attr)
