"""RAG retrieval service — vector search with keyword fallback."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk
from app.models.provider import ProviderConfig
from app.services.embedding_service import (
    can_use_embeddings,
    generate_embeddings,
    get_embedding_model,
)
from app.services.vector_store_service import (
    find_missing_chunk_ids,
    query_document_chunks,
    upsert_document_chunks,
    VectorChunkRecord,
)

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 6


@dataclass(slots=True)
class RetrievedChunk:
    chunk_id: str
    document_id: str
    document_name: str
    chunk_index: int
    content: str
    page_no: int | None = None
    section_label: str | None = None
    score: float | None = None


@dataclass(slots=True)
class RAGResult:
    """Structured result from RAG retrieval — carries both the prompt and metadata."""
    system_prompt: str
    chunks: list[RetrievedChunk]
    retrieval_method: str  # "vector" | "keyword" | "none"


async def retrieve_chunks(
    db: AsyncSession,
    query: str,
    *,
    provider: ProviderConfig | None = None,
    scope_type: str = "all",
    document_id: str | None = None,
    document_ids: list[str] | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> tuple[list[RetrievedChunk], str]:
    """Retrieve the most relevant chunks for a query.

    Returns (chunks, retrieval_method) where retrieval_method is
    "vector", "keyword", or "none".
    """
    doc_ids = await _get_candidate_doc_ids(db, scope_type, document_id, document_ids)
    if not doc_ids:
        logger.info("RAG: no candidate docs (scope=%s, doc_id=%s)", scope_type, document_id)
        return [], "none"

    logger.info("RAG: %d candidate doc(s) for scope=%s", len(doc_ids), scope_type)

    if provider is None:
        provider = (await db.execute(
            select(ProviderConfig).where(ProviderConfig.is_default == True)  # noqa: E712
        )).scalar_one_or_none()

    if provider and can_use_embeddings(provider):
        try:
            await _ensure_provider_embeddings(db, provider, doc_ids)
            vector_rows = await _vector_retrieve(
                db,
                provider,
                query,
                doc_ids=doc_ids,
                top_k=top_k,
            )
            if vector_rows:
                logger.info("RAG: vector retrieval returned %d chunk(s)", len(vector_rows))
                return vector_rows, "vector"
        except Exception as e:
            logger.warning("Vector retrieval failed, falling back to keyword: %s", str(e)[:200])

    keyword_chunks = await _load_candidate_chunks(db, doc_ids)
    results = await _keyword_retrieve(db, query, keyword_chunks, top_k)
    method = "keyword" if results else "none"
    logger.info("RAG: keyword retrieval returned %d chunk(s)", len(results))
    return results, method


async def retrieve_chunk_hits(
    db: AsyncSession,
    query: str,
    *,
    provider: ProviderConfig | None = None,
    scope_type: str = "all",
    document_id: str | None = None,
    document_ids: list[str] | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> list[RetrievedChunk]:
    chunks, _ = await retrieve_chunks(
        db,
        query,
        provider=provider,
        scope_type=scope_type,
        document_id=document_id,
        document_ids=document_ids,
        top_k=top_k,
    )
    return chunks


async def build_rag_prompt(
    db: AsyncSession,
    query: str,
    *,
    provider: ProviderConfig | None = None,
    scope_type: str = "all",
    document_id: str | None = None,
    document_ids: list[str] | None = None,
) -> RAGResult:
    """Build a RAG-augmented system prompt with retrieved context."""
    chunks, method = await retrieve_chunks(
        db,
        query,
        provider=provider,
        scope_type=scope_type,
        document_id=document_id,
        document_ids=document_ids,
    )

    if not chunks:
        logger.info("RAG: no chunks retrieved — using NO_CONTEXT_PROMPT")
        return RAGResult(
            system_prompt=_NO_CONTEXT_PROMPT,
            chunks=[],
            retrieval_method="none",
        )

    context_parts: list[str] = []
    for i, chunk in enumerate(chunks):
        page_info = f" (第{chunk.page_no}页)" if chunk.page_no else ""
        context_parts.append(
            f"[{i + 1}] 来源: {chunk.document_name}{page_info}\n{chunk.content}"
        )

    context_block = "\n\n---\n\n".join(context_parts)
    prompt = _RAG_SYSTEM_PROMPT.format(context=context_block)
    logger.info("RAG: built prompt with %d chunk(s), method=%s, context_len=%d",
                len(chunks), method, len(context_block))

    return RAGResult(
        system_prompt=prompt,
        chunks=chunks,
        retrieval_method=method,
    )


async def _vector_retrieve(
    db: AsyncSession,
    provider: ProviderConfig,
    query: str,
    *,
    doc_ids: list[str],
    top_k: int,
) -> list[RetrievedChunk]:
    embedding_model = get_embedding_model(provider)
    if not embedding_model:
        return []

    query_embs = await generate_embeddings(provider, [query])
    query_emb = query_embs[0] if query_embs else None
    if not query_emb:
        return []

    hits = query_document_chunks(
        query_emb,
        top_k=top_k,
        provider_id=provider.id,
        embedding_model=embedding_model,
        document_ids=doc_ids,
    )
    if not hits:
        return []

    chunk_ids = [hit.chunk_id for hit in hits]
    chunk_rows = (await db.execute(
        select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids))
    )).scalars().all()
    chunk_map = {row.id: row for row in chunk_rows}

    doc_name_map = await _load_document_names(db, {hit.document_id for hit in hits})
    results: list[RetrievedChunk] = []
    for hit in hits:
        chunk = chunk_map.get(hit.chunk_id)
        if not chunk:
            continue
        results.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document_name=doc_name_map.get(chunk.document_id, "未知文档"),
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                page_no=chunk.page_no,
                section_label=chunk.section_label,
                score=hit.score,
            )
        )
    return results


async def _ensure_provider_embeddings(
    db: AsyncSession,
    provider: ProviderConfig,
    doc_ids: list[str],
) -> None:
    embedding_model = get_embedding_model(provider)
    if not embedding_model or not doc_ids:
        return

    chunks = await _load_candidate_chunks(db, doc_ids)
    if not chunks:
        return

    chunk_ids = [chunk.id for chunk in chunks]
    missing_ids = set(find_missing_chunk_ids(provider.id, embedding_model, chunk_ids))
    if not missing_ids:
        return

    missing_chunks = [chunk for chunk in chunks if chunk.id in missing_ids]
    raw_embeddings = await generate_embeddings(provider, [chunk.content for chunk in missing_chunks])

    records = [
        VectorChunkRecord(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            provider_id=provider.id,
            embedding_model=embedding_model,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            embedding=raw_embedding,
            page_no=chunk.page_no,
            section_label=chunk.section_label,
        )
        for chunk, raw_embedding in zip(missing_chunks, raw_embeddings)
        if raw_embedding is not None
    ]
    if records:
        upsert_document_chunks(records)


async def _keyword_retrieve(
    db: AsyncSession,
    query: str,
    chunks: list[DocumentChunk],
    top_k: int,
) -> list[RetrievedChunk]:
    keywords = set(re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z]+", query.lower()))
    if not keywords:
        keywords = {query.strip().lower()} if query.strip() else set()

    doc_name_map = await _load_document_names(db, {c.document_id for c in chunks})

    scored: list[tuple[float, DocumentChunk]] = []
    for chunk in chunks:
        content_lower = chunk.content.lower()
        score = sum(content_lower.count(kw) for kw in keywords if kw)
        if score > 0:
            scored.append((float(score), chunk))

    if not scored:
        fallback = chunks[:top_k]
        return [
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document_name=doc_name_map.get(chunk.document_id, "未知文档"),
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                page_no=chunk.page_no,
                section_label=chunk.section_label,
                score=None,
            )
            for chunk in fallback
        ]

    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        RetrievedChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            document_name=doc_name_map.get(chunk.document_id, "未知文档"),
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            page_no=chunk.page_no,
            section_label=chunk.section_label,
            score=score,
        )
        for score, chunk in scored[:top_k]
    ]


async def _get_candidate_doc_ids(
    db: AsyncSession,
    scope_type: str,
    document_id: str | None,
    document_ids: list[str] | None = None,
) -> list[str]:
    selected_ids = document_ids or ([document_id] if document_id else [])

    if scope_type == "single" and not selected_ids:
        return []

    if scope_type == "single" and selected_ids:
        docs = (await db.execute(
            select(Document.id).where(
                Document.id.in_(selected_ids),
                Document.status == "可用",
            )
        )).scalars().all()
        return list(docs)

    docs = (await db.execute(
        select(Document).where(Document.status == "可用")
    )).scalars().all()
    return [d.id for d in docs]


async def _load_candidate_chunks(
    db: AsyncSession,
    doc_ids: list[str],
) -> list[DocumentChunk]:
    if not doc_ids:
        return []
    return (await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id.in_(doc_ids))
        .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
    )).scalars().all()


async def _load_document_names(
    db: AsyncSession,
    doc_ids: set[str],
) -> dict[str, str]:
    if not doc_ids:
        return {}
    rows = (await db.execute(
        select(Document.id, Document.file_name).where(Document.id.in_(doc_ids))
    )).all()
    return {doc_id: file_name for doc_id, file_name in rows}


_RAG_SYSTEM_PROMPT = """你是一个智能文档问答助手。请根据以下文档内容回答用户的问题。

要求：
1. 优先基于提供的文档内容回答，不要编造文档中没有的信息。
2. 如果文档内容不足以回答问题，请明确说明。
3. 在回答中引用相关来源编号，例如 [1]、[2]。
4. 使用 Markdown 格式组织回答。

以下是相关文档内容：

{context}"""

_NO_CONTEXT_PROMPT = """你是一个智能文档问答助手。

当前没有找到与问题相关的文档内容。请告知用户：
1. 系统中可能没有上传相关文档
2. 建议用户上传相关文档后再提问
3. 你可以尝试基于通用知识回答，但需要明确说明这不是基于已上传文档的回答"""
