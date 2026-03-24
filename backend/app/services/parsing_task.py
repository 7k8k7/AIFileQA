"""Async document parsing task — runs parsing in a background thread/process,
generates embeddings, and updates document status + inserts chunks into DB."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ProcessPoolExecutor

from sqlalchemy import select, delete

from app.core.database import async_session
from app.models.document import Document, DocumentChunk
from app.models.provider import ProviderConfig
from app.services.parser_service import parse_document
from app.services.embedding_service import generate_embeddings, serialize_embedding, get_embedding_model
from app.services.vector_store_service import (
    delete_document_chunks as delete_vector_chunks,
    upsert_document_chunks,
    VectorChunkRecord,
)

logger = logging.getLogger(__name__)

_executor: ProcessPoolExecutor | None = None
_background_tasks: set[asyncio.Task] = set()


def _get_executor() -> ProcessPoolExecutor:
    global _executor
    if _executor is None:
        # Shared executor — 2 workers max to avoid memory pressure
        _executor = ProcessPoolExecutor(max_workers=2)
    return _executor


async def trigger_parse(doc_id: str, file_path: str, file_ext: str) -> None:
    """Schedule document parsing as a background task."""
    task = asyncio.create_task(_run_parse(doc_id, file_path, file_ext))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _run_parse(doc_id: str, file_path: str, file_ext: str) -> None:
    """Execute the full pipeline:
    1. Set status → 解析中
    2. Parse document in executor (CPU-bound)
    3. Generate embeddings (if provider available)
    4. Save chunks to DB
    5. Set status → 可用 (or 失败)
    """
    # 1. Mark as parsing
    async with async_session() as db:
        doc = (await db.execute(
            select(Document).where(Document.id == doc_id)
        )).scalar_one_or_none()
        if not doc:
            logger.error("Document %s not found for parsing", doc_id)
            return
        doc.status = "解析中"
        await db.commit()

    # 2. Run CPU-bound parsing in process pool
    loop = asyncio.get_running_loop()
    try:
        chunks = await loop.run_in_executor(
            _get_executor(), parse_document, file_path, file_ext
        )
    except Exception as e:
        logger.exception("Parsing failed for document %s", doc_id)
        await _mark_failed(doc_id, str(e)[:500])
        return

    if not chunks:
        await _mark_failed(doc_id, "文档内容为空，无法提取文本")
        return

    # 3. Try to generate embeddings (best-effort)
    raw: list[list[float] | None] = [None] * len(chunks)
    embeddings: list[str | None] = [None] * len(chunks)
    embedding_model: str | None = None
    provider: ProviderConfig | None = None
    try:
        async with async_session() as db:
            provider = (await db.execute(
                select(ProviderConfig).where(ProviderConfig.is_default == True)  # noqa: E712
            )).scalar_one_or_none()

        if provider:
            embedding_model = get_embedding_model(provider)
            texts = [c.content for c in chunks]
            raw = await generate_embeddings(provider, texts)
            embeddings = [serialize_embedding(e) for e in raw]
            logger.info("Generated %d embeddings for document %s",
                        sum(1 for e in embeddings if e), doc_id)
    except Exception as e:
        logger.warning("Embedding generation failed for %s (will use keyword search): %s",
                       doc_id, str(e)[:200])

    # 4. Save chunks to DB
    async with async_session() as db:
        try:
            try:
                delete_vector_chunks(doc_id)
            except Exception as e:
                logger.warning("Failed to clear vector store for %s: %s", doc_id, str(e)[:200])

            # Clear existing chunks (in case of re-parse)
            await db.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == doc_id)
            )

            chunk_rows: list[DocumentChunk] = []
            for chunk, emb in zip(chunks, embeddings):
                row = DocumentChunk(
                    document_id=doc_id,
                    chunk_index=chunk.index,
                    content=chunk.content,
                    page_no=chunk.page_no,
                    section_label=chunk.section_label,
                    embedding=emb,
                )
                chunk_rows.append(row)
                db.add(row)

            await db.flush()

            vector_records = [
                VectorChunkRecord(
                    chunk_id=row.id,
                    document_id=doc_id,
                    provider_id=provider.id,
                    embedding_model=embedding_model,
                    chunk_index=row.chunk_index,
                    content=row.content,
                    embedding=raw_embedding,
                    page_no=row.page_no,
                    section_label=row.section_label,
                )
                for row, raw_embedding in zip(chunk_rows, raw)
                if provider and embedding_model and raw_embedding is not None
            ]
            if vector_records:
                upsert_document_chunks(vector_records)

            # 5. Mark as available
            doc = (await db.execute(
                select(Document).where(Document.id == doc_id)
            )).scalar_one_or_none()
            if doc:
                doc.status = "可用"
                doc.error_message = None

            await db.commit()
            logger.info("Document %s parsed: %d chunks", doc_id, len(chunks))

        except Exception as e:
            logger.exception("Failed to save chunks for document %s", doc_id)
            await db.rollback()
            await _mark_failed(doc_id, f"保存切片失败: {str(e)[:300]}")


async def _mark_failed(doc_id: str, message: str) -> None:
    async with async_session() as db:
        doc = (await db.execute(
            select(Document).where(Document.id == doc_id)
        )).scalar_one_or_none()
        if doc:
            doc.status = "失败"
            doc.error_message = message
            await db.commit()
