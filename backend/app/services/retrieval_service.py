"""RAG retrieval service — vector search with keyword fallback."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk
from app.models.provider import ProviderConfig
from app.services.embedding_service import generate_embeddings
from app.services.vector_store_service import query_document_chunks

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


async def retrieve_chunks(
    db: AsyncSession,
    query: str,
    *,
    scope_type: str = "all",
    document_id: str | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> list[RetrievedChunk]:
    """Retrieve the most relevant chunks for a query."""
    doc_ids = await _get_candidate_doc_ids(db, scope_type, document_id)
    if not doc_ids:
        return []

    provider = (await db.execute(
        select(ProviderConfig).where(ProviderConfig.is_default == True)  # noqa: E712
    )).scalar_one_or_none()

    if provider:
        try:
            vector_rows = await _vector_retrieve(
                db,
                provider,
                query,
                doc_ids=doc_ids,
                top_k=top_k,
            )
            if vector_rows:
                return vector_rows
        except Exception as e:
            logger.warning("Vector retrieval failed, falling back to keyword: %s", str(e)[:200])

    keyword_chunks = await _load_candidate_chunks(db, doc_ids)
    return await _keyword_retrieve(db, query, keyword_chunks, top_k)


async def retrieve_chunk_hits(
    db: AsyncSession,
    query: str,
    *,
    scope_type: str = "all",
    document_id: str | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> list[RetrievedChunk]:
    return await retrieve_chunks(
        db,
        query,
        scope_type=scope_type,
        document_id=document_id,
        top_k=top_k,
    )


async def build_rag_prompt(
    db: AsyncSession,
    query: str,
    *,
    scope_type: str = "all",
    document_id: str | None = None,
) -> str:
    """Build a RAG-augmented system prompt with retrieved context."""
    chunks = await retrieve_chunks(
        db,
        query,
        scope_type=scope_type,
        document_id=document_id,
    )

    if not chunks:
        return _NO_CONTEXT_PROMPT

    context_parts: list[str] = []
    for i, chunk in enumerate(chunks):
        page_info = f" (第{chunk.page_no}页)" if chunk.page_no else ""
        context_parts.append(
            f"[{i + 1}] 来源: {chunk.document_name}{page_info}\n{chunk.content}"
        )

    context_block = "\n\n---\n\n".join(context_parts)
    return _RAG_SYSTEM_PROMPT.format(context=context_block)


async def _vector_retrieve(
    db: AsyncSession,
    provider: ProviderConfig,
    query: str,
    *,
    doc_ids: list[str],
    top_k: int,
) -> list[RetrievedChunk]:
    query_embs = await generate_embeddings(provider, [query])
    query_emb = query_embs[0] if query_embs else None
    if not query_emb:
        return []

    hits = query_document_chunks(query_emb, top_k=top_k, document_ids=doc_ids)
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
) -> list[str]:
    if scope_type == "single" and document_id:
        doc = (await db.execute(
            select(Document).where(
                Document.id == document_id,
                Document.status == "可用",
            )
        )).scalar_one_or_none()
        return [doc.id] if doc else []

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
