"""Background parsing worker built on the jobs table."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ProcessPoolExecutor

from sqlalchemy import select, delete

from app.core.config import settings
from app.core.database import async_session
from app.models.document import Document, DocumentChunk
from app.models.job import Job
from app.models.provider import ProviderConfig
from app.services.job_service import (
    claim_next_parse_job,
    complete_job,
    create_parse_job,
    reset_stalled_jobs,
    retry_or_fail_job,
)
from app.services.parser_service import parse_document
from app.services.embedding_service import generate_embeddings, serialize_embedding, get_embedding_model
from app.services.vector_store_service import (
    delete_document_chunks as delete_vector_chunks,
    upsert_document_chunks,
    VectorChunkRecord,
)

logger = logging.getLogger(__name__)

_executor: ProcessPoolExecutor | None = None
_worker_task: asyncio.Task | None = None


def _get_executor() -> ProcessPoolExecutor:
    global _executor
    if _executor is None:
        # Shared executor — 2 workers max to avoid memory pressure
        _executor = ProcessPoolExecutor(max_workers=2)
    return _executor


async def trigger_parse(doc_id: str, file_path: str, file_ext: str) -> None:
    """Create a parse job for the document."""
    async with async_session() as db:
        await create_parse_job(
            db,
            document_id=doc_id,
            file_path=file_path,
            file_ext=file_ext,
        )
        await db.commit()


async def start_job_worker() -> None:
    global _worker_task
    if _worker_task and not _worker_task.done():
        return
    _worker_task = asyncio.create_task(_job_worker_loop())


async def stop_job_worker() -> None:
    global _worker_task, _executor
    if _worker_task:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        _worker_task = None
    if _executor is not None:
        _executor.shutdown(cancel_futures=True)
        _executor = None


async def _job_worker_loop() -> None:
    while True:
        worked = await run_parse_worker_once()
        if not worked:
            await asyncio.sleep(settings.job_poll_seconds)


async def run_parse_worker_once() -> bool:
    async with async_session() as db:
        reset_results = await reset_stalled_jobs(db)
        for result in reset_results:
            await _apply_job_result_to_document(db, result.document_id, result.status, result.message)
        claimed = await claim_next_parse_job(db)
        await db.commit()

    if not claimed:
        return bool(reset_results)

    try:
        await asyncio.wait_for(
            _run_parse_pipeline(claimed.document_id, claimed.file_path, claimed.file_ext),
            timeout=settings.job_stale_seconds,
        )
    except asyncio.TimeoutError:
        message = f"运行超过 {settings.job_stale_seconds // 60} 分钟，已自动重置并重试"
        await _handle_job_failure(claimed.id, claimed.document_id, message)
    except Exception as exc:
        message = str(exc)[:500] or "解析失败"
        await _handle_job_failure(claimed.id, claimed.document_id, message)
    else:
        async with async_session() as db:
            await complete_job(db, claimed.id)
            await db.commit()

    return True


async def _run_parse_pipeline(doc_id: str, file_path: str, file_ext: str) -> None:
    async with async_session() as db:
        doc = (await db.execute(select(Document).where(Document.id == doc_id))).scalar_one_or_none()
        if not doc:
            raise FileNotFoundError(f"文档不存在: {doc_id}")
        doc.status = "解析中"
        doc.error_message = None
        await db.commit()

    loop = asyncio.get_running_loop()
    chunks = await loop.run_in_executor(
        _get_executor(), parse_document, file_path, file_ext
    )

    if not chunks:
        raise ValueError("文档内容为空，无法提取文本")

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
            logger.info(
                "Generated %d embeddings for document %s",
                sum(1 for e in embeddings if e),
                doc_id,
            )
    except Exception as e:
        logger.warning(
            "Embedding generation failed for %s (will use keyword search): %s",
            doc_id,
            str(e)[:200],
        )

    async with async_session() as db:
        try:
            delete_vector_chunks(doc_id)
        except Exception as e:
            logger.warning("Failed to clear vector store for %s: %s", doc_id, str(e)[:200])

        await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc_id))

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

        doc = (await db.execute(select(Document).where(Document.id == doc_id))).scalar_one_or_none()
        if not doc:
            raise FileNotFoundError(f"文档不存在: {doc_id}")
        doc.status = "可用"
        doc.error_message = None
        await db.commit()
        logger.info("Document %s parsed: %d chunks", doc_id, len(chunks))


async def _handle_job_failure(job_id: str, doc_id: str, message: str) -> None:
    async with async_session() as db:
        status = await retry_or_fail_job(db, job_id, message)
        if status:
            await _apply_job_result_to_document(db, doc_id, status, message)
        await db.commit()


async def _apply_job_result_to_document(
    db,
    document_id: str,
    status: str,
    message: str,
) -> None:
    doc = (await db.execute(select(Document).where(Document.id == document_id))).scalar_one_or_none()
    if not doc:
        return

    if status == "failed":
        doc.status = "失败"
        doc.error_message = message
    else:
        doc.status = "解析中"
        doc.error_message = message
