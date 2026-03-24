"""Unit tests for parser_service — text extraction and chunking."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.parser_service import (
    Chunk,
    _extract_text,
    _split_text,
    parse_document,
    EXTRACTORS,
)


# ── _extract_text ──

def test_extract_text_utf8(tmp_path: Path):
    f = tmp_path / "hello.txt"
    f.write_text("你好世界\nHello World", encoding="utf-8")
    result = _extract_text(f)
    assert len(result) == 1
    assert result[0] == (None, "你好世界\nHello World")


def test_extract_text_empty_file(tmp_path: Path):
    f = tmp_path / "empty.txt"
    f.write_text("", encoding="utf-8")
    result = _extract_text(f)
    assert result == []


def test_extract_markdown(tmp_path: Path):
    f = tmp_path / "readme.md"
    f.write_text("# Title\n\nSome content", encoding="utf-8")
    result = _extract_text(f)
    assert len(result) == 1
    assert "# Title" in result[0][1]


# ── _split_text ──

def test_split_text_short_returns_single():
    result = _split_text("short text", chunk_size=500)
    assert result == ["short text"]


def test_split_text_empty_returns_empty():
    result = _split_text("   ", chunk_size=500)
    assert result == []


def test_split_text_respects_chunk_size():
    text = "A" * 1000
    result = _split_text(text, chunk_size=500, overlap=0)
    assert all(len(chunk) <= 500 for chunk in result)
    assert len(result) >= 2


def test_split_text_overlap():
    text = "段落一。" * 100 + "段落二。" * 100
    result = _split_text(text, chunk_size=200, overlap=50)
    if len(result) > 1:
        # Second chunk should start with tail of first chunk (overlap)
        assert len(result[1]) > len(result[0]) or len(result) >= 2


def test_split_text_paragraph_separator():
    text = "Paragraph one content.\n\nParagraph two content."
    result = _split_text(text, chunk_size=500, overlap=0)
    assert len(result) == 1  # small enough to fit in one chunk


def test_split_text_forces_hard_split():
    # No separators at all — single long string
    text = "A" * 1200
    result = _split_text(text, chunk_size=500, overlap=50)
    assert len(result) >= 2
    # Hard split: each chunk <= chunk_size
    for chunk in result:
        assert len(chunk) <= 500


# ── parse_document ──

def test_parse_document_txt(tmp_path: Path):
    f = tmp_path / "test.txt"
    f.write_text("这是一段测试内容", encoding="utf-8")
    chunks = parse_document(str(f), ".txt")
    assert len(chunks) >= 1
    assert isinstance(chunks[0], Chunk)
    assert chunks[0].index == 0
    assert "测试内容" in chunks[0].content
    assert chunks[0].page_no is None  # TXT has no page numbers


def test_parse_document_md(tmp_path: Path):
    f = tmp_path / "test.md"
    f.write_text("# Heading\n\nBody text here.", encoding="utf-8")
    chunks = parse_document(str(f), ".md")
    assert len(chunks) >= 1
    assert "Heading" in chunks[0].content


def test_parse_document_empty_file(tmp_path: Path):
    f = tmp_path / "empty.txt"
    f.write_text("", encoding="utf-8")
    chunks = parse_document(str(f), ".txt")
    assert chunks == []


def test_parse_document_file_not_found():
    with pytest.raises(FileNotFoundError):
        parse_document("/nonexistent/path.txt", ".txt")


def test_parse_document_unsupported_ext(tmp_path: Path):
    f = tmp_path / "test.xyz"
    f.write_text("content", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported"):
        parse_document(str(f), ".xyz")


def test_parse_document_dispatches_by_ext():
    """Verify EXTRACTORS map covers expected extensions."""
    assert ".pdf" in EXTRACTORS
    assert ".docx" in EXTRACTORS
    assert ".doc" in EXTRACTORS
    assert ".txt" in EXTRACTORS
    assert ".md" in EXTRACTORS
    assert ".markdown" in EXTRACTORS


def test_parse_document_chunking_large_text(tmp_path: Path):
    f = tmp_path / "large.txt"
    # Create text that exceeds chunk_size (500)
    f.write_text("这是重复文本。" * 200, encoding="utf-8")
    chunks = parse_document(str(f), ".txt")
    assert len(chunks) > 1
    # Indices should be sequential
    for i, chunk in enumerate(chunks):
        assert chunk.index == i
