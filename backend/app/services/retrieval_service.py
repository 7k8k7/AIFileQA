"""RAG retrieval service — vector search with keyword fallback."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from math import ceil

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
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

DEFAULT_TOP_K = settings.retrieval_top_k


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
    retrieval_method: str  # "hybrid" | "vector" | "keyword" | "none"


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
    "hybrid", "vector", "keyword", or "none".
    """
    doc_ids = await _get_candidate_doc_ids(db, scope_type, document_id, document_ids)
    if not doc_ids:
        logger.info("RAG: no candidate docs (scope=%s, doc_id=%s)", scope_type, document_id)
        return [], "none"

    logger.info("RAG: %d candidate doc(s) for scope=%s", len(doc_ids), scope_type)
    candidate_top_k = max(top_k, ceil(top_k * max(settings.retrieval_candidate_multiplier, 1)))

    if provider is None:
        provider = (await db.execute(
            select(ProviderConfig).where(ProviderConfig.is_default == True)  # noqa: E712
        )).scalar_one_or_none()

    keyword_chunks = await _load_candidate_chunks(db, doc_ids)
    keyword_rows = await _keyword_retrieve(db, query, keyword_chunks, candidate_top_k)
    vector_rows: list[RetrievedChunk] = []

    if provider and can_use_embeddings(provider):
        try:
            await _ensure_provider_embeddings(db, provider, doc_ids)
            vector_rows = await _vector_retrieve(
                db,
                provider,
                query,
                doc_ids=doc_ids,
                top_k=candidate_top_k,
            )
            logger.info("RAG: vector retrieval returned %d chunk(s)", len(vector_rows))
        except Exception as e:
            logger.warning("Vector retrieval failed, falling back to keyword: %s", str(e)[:200])

    logger.info("RAG: keyword retrieval returned %d chunk(s)", len(keyword_rows))

    results, method = _merge_retrieval_results(vector_rows, keyword_rows, top_k=top_k)
    logger.info("RAG: merged retrieval returned %d chunk(s), method=%s", len(results), method)
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
        return []

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


def _merge_retrieval_results(
    vector_rows: list[RetrievedChunk],
    keyword_rows: list[RetrievedChunk],
    *,
    top_k: int,
) -> tuple[list[RetrievedChunk], str]:
    if vector_rows and keyword_rows:
        merged: dict[str, dict[str, object]] = {}

        for chunk, weighted_score in _weighted_scores(vector_rows, settings.retrieval_vector_weight):
            merged[chunk.chunk_id] = {
                "chunk": chunk,
                "score": weighted_score,
                "has_vector": True,
                "has_keyword": False,
            }

        for chunk, weighted_score in _weighted_scores(keyword_rows, settings.retrieval_keyword_weight):
            entry = merged.get(chunk.chunk_id)
            if entry:
                entry["score"] = float(entry["score"]) + weighted_score
                entry["has_keyword"] = True
            else:
                merged[chunk.chunk_id] = {
                    "chunk": chunk,
                    "score": weighted_score,
                    "has_vector": False,
                    "has_keyword": True,
                }

        ranked = sorted(
            merged.values(),
            key=lambda item: (
                float(item["score"]),
                bool(item["has_vector"]) and bool(item["has_keyword"]),
                _safe_score_value(item["chunk"]),  # type: ignore[arg-type]
                -int(getattr(item["chunk"], "chunk_index", 0)),  # type: ignore[arg-type]
            ),
            reverse=True,
        )
        return [item["chunk"] for item in ranked[:top_k]], "hybrid"

    if vector_rows:
        return vector_rows[:top_k], "vector"
    if keyword_rows:
        return keyword_rows[:top_k], "keyword"
    return [], "none"


def _weighted_scores(
    chunks: list[RetrievedChunk],
    weight: float,
) -> list[tuple[RetrievedChunk, float]]:
    if not chunks:
        return []

    base_scores = [float(chunk.score or 0.0) for chunk in chunks]
    max_score = max(base_scores) if base_scores else 0.0
    if max_score <= 0:
        max_score = float(len(chunks))

    weighted: list[tuple[RetrievedChunk, float]] = []
    for idx, chunk in enumerate(chunks):
        raw_score = float(chunk.score or 0.0)
        if raw_score > 0:
            normalized = raw_score / max_score
        else:
            normalized = (len(chunks) - idx) / len(chunks)
        weighted.append((chunk, normalized * weight))
    return weighted


def _safe_score_value(chunk: RetrievedChunk) -> float:
    return float(chunk.score or 0.0)


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


_RAG_SYSTEM_PROMPT = """你是一个智能文档问答助手。你必须严格基于下面提供的文档片段回答用户问题。

回答要求：
1. 只能使用提供的文档片段中的事实、术语和结论作答，不得补充文档中没有明确出现的信息。
2. 如果文档片段不足以支持完整回答，必须明确说明“根据当前检索到的文档内容，无法确定”或“文档中未提供足够信息”，不要猜测，不要编造。
3. 回答中的关键结论都要标注来源编号，例如 [1]、[2]。
4. 如果不同片段之间信息不一致，必须指出这一点，不要自行合并成确定结论。
5. 优先复用文档中的原始表述、关键词和专业术语。
6. 使用 Markdown 格式组织回答，先给结论，再补充依据。

以下是相关文档内容：

{context}"""

_NO_CONTEXT_PROMPT = """你是一个智能文档问答助手。

当前没有找到与用户问题相关的文档内容。你的回答必须遵守以下要求：
1. 明确告诉用户：当前无法基于已上传文档回答这个问题。
2. 不要使用通用知识直接回答，不要猜测，不要编造。
3. 建议用户检查是否上传了相关文档，或调整提问方式后重试。
4. 如果合适，可以提示用户缩小问题范围，或指定文档后再次提问。"""
