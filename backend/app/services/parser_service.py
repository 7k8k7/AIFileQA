"""Document parsing — extract text from files and split into chunks.

Runs in a separate process via ProcessPoolExecutor to avoid blocking
the async event loop (PDF/DOCX parsing is CPU-bound).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings


@dataclass
class Chunk:
    """A text chunk extracted from a document."""
    index: int
    content: str
    page_no: int | None = None
    section_label: str | None = None


# ── Text Extractors ──

def _extract_pdf(path: Path) -> list[tuple[int, str]]:
    """Return [(page_no, text), ...] from a PDF."""
    import fitz
    pages: list[tuple[int, str]] = []
    with fitz.open(str(path)) as doc:
        for i, page in enumerate(doc):
            text = page.get_text("text").strip()
            if text:
                pages.append((i + 1, text))
    return pages


def _extract_docx(path: Path) -> list[tuple[None, str]]:
    """Return [(None, paragraph_text), ...] from a DOCX."""
    from docx import Document as DocxDocument
    doc = DocxDocument(str(path))
    result: list[tuple[None, str]] = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            result.append((None, text))
    return result


def _extract_text(path: Path) -> list[tuple[None, str]]:
    """Return the full text from a plain text or markdown file."""
    content = path.read_text(encoding="utf-8", errors="replace").strip()
    if not content:
        return []
    return [(None, content)]


EXTRACTORS = {
    ".pdf": _extract_pdf,
    ".docx": _extract_docx,
    ".doc": _extract_docx,
    ".txt": _extract_text,
    ".md": _extract_text,
    ".markdown": _extract_text,
}


# ── Text Splitter ──

def _split_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """
    Recursive character splitter.
    Tries to split on paragraph breaks, then sentences, then by size.
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    # Try splitting on double newlines first
    for sep in ["\n\n", "\n", "。", ".", " "]:
        parts = text.split(sep)
        if len(parts) > 1:
            chunks: list[str] = []
            current = ""
            for part in parts:
                candidate = (current + sep + part) if current else part
                if len(candidate) <= chunk_size:
                    current = candidate
                else:
                    if current.strip():
                        chunks.append(current.strip())
                    current = part
            if current.strip():
                chunks.append(current.strip())

            # Apply overlap
            if overlap > 0 and len(chunks) > 1:
                overlapped: list[str] = [chunks[0]]
                for i in range(1, len(chunks)):
                    prev_tail = chunks[i - 1][-overlap:]
                    overlapped.append(prev_tail + chunks[i])
                return overlapped
            return chunks

    # Fallback: hard split by chunk_size
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size - overlap)]


# ── Public API ──

def parse_document(file_path: str, file_ext: str) -> list[Chunk]:
    """
    Extract text from a document and split into chunks.
    This is designed to run in a ProcessPoolExecutor.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    extractor = EXTRACTORS.get(file_ext.lower())
    if not extractor:
        raise ValueError(f"Unsupported file type: {file_ext}")

    raw_pages = extractor(path)
    if not raw_pages:
        return []

    chunks: list[Chunk] = []
    idx = 0

    for page_no, text in raw_pages:
        splits = _split_text(
            text,
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap,
        )
        for split in splits:
            chunks.append(Chunk(
                index=idx,
                content=split,
                page_no=page_no,
                section_label=None,
            ))
            idx += 1

    return chunks
