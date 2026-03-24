"""Unit tests for retrieval_service — keyword retrieval and RAG prompt building."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.services.retrieval_service as retrieval_service


def _make_chunk(chunk_id, doc_id, content, chunk_index=0, page_no=None):
    """Create a mock DocumentChunk."""
    chunk = MagicMock()
    chunk.id = chunk_id
    chunk.document_id = doc_id
    chunk.content = content
    chunk.chunk_index = chunk_index
    chunk.page_no = page_no
    chunk.section_label = None
    return chunk


def _make_provider(**overrides):
    defaults = {
        "id": "p-test",
        "provider_type": "openai",
        "base_url": "https://api.openai.com",
        "model_name": "gpt-4o",
        "api_key": "sk-test",
        "embedding_model": "text-embedding-3-small",
        "enable_embedding": True,
        "is_default": True,
    }
    defaults.update(overrides)
    provider = MagicMock()
    for k, v in defaults.items():
        setattr(provider, k, v)
    return provider


# ── _keyword_retrieve ──

@pytest.mark.asyncio
async def test_keyword_retrieve_scores_by_frequency():
    """Chunks with more keyword hits should rank higher."""
    db = AsyncMock()
    # Mock _load_document_names
    db.execute = AsyncMock(return_value=MagicMock(
        all=MagicMock(return_value=[("doc1", "test.txt")])
    ))

    chunks = [
        _make_chunk("c1", "doc1", "python is great for python development", chunk_index=0),
        _make_chunk("c2", "doc1", "java is a language", chunk_index=1),
        _make_chunk("c3", "doc1", "python python python everywhere", chunk_index=2),
    ]

    with patch.object(retrieval_service, "_load_document_names",
                      new=AsyncMock(return_value={"doc1": "test.txt"})):
        results = await retrieval_service._keyword_retrieve(db, "python", chunks, top_k=3)

    assert len(results) >= 2
    # Chunk with 3x "python" should be first
    assert results[0].chunk_id == "c3"
    assert results[1].chunk_id == "c1"


@pytest.mark.asyncio
async def test_keyword_retrieve_fallback_on_no_match():
    """When no keywords match, return first top_k chunks as fallback."""
    db = AsyncMock()
    chunks = [
        _make_chunk("c1", "doc1", "apple banana cherry", chunk_index=0),
        _make_chunk("c2", "doc1", "date elderberry fig", chunk_index=1),
    ]

    with patch.object(retrieval_service, "_load_document_names",
                      new=AsyncMock(return_value={"doc1": "test.txt"})):
        results = await retrieval_service._keyword_retrieve(db, "xyz_nonexistent", chunks, top_k=1)

    assert len(results) == 1
    assert results[0].chunk_id == "c1"
    assert results[0].score is None


@pytest.mark.asyncio
async def test_keyword_chinese_segmentation():
    """Chinese keywords are extracted via regex and matched."""
    db = AsyncMock()
    chunks = [
        _make_chunk("c1", "doc1", "智能文档管理系统支持多种格式", chunk_index=0),
        _make_chunk("c2", "doc1", "英文内容 english content", chunk_index=1),
    ]

    with patch.object(retrieval_service, "_load_document_names",
                      new=AsyncMock(return_value={"doc1": "test.txt"})):
        results = await retrieval_service._keyword_retrieve(db, "智能文档", chunks, top_k=2)

    # c1 should match Chinese keywords
    assert len(results) >= 1
    assert results[0].chunk_id == "c1"


# ── _get_candidate_doc_ids ──

@pytest.mark.asyncio
async def test_get_candidate_doc_ids_scope_all():
    """scope=all returns all available documents."""
    db = AsyncMock()
    mock_docs = [MagicMock(id="d1"), MagicMock(id="d2")]
    db.execute = AsyncMock(return_value=MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=mock_docs)))
    ))

    result = await retrieval_service._get_candidate_doc_ids(db, "all", None)
    assert set(result) == {"d1", "d2"}


@pytest.mark.asyncio
async def test_get_candidate_doc_ids_scope_single_with_id():
    """scope=single with document_id filters to that document."""
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=["d1"])))
    ))

    result = await retrieval_service._get_candidate_doc_ids(db, "single", "d1")
    assert result == ["d1"]


@pytest.mark.asyncio
async def test_get_candidate_doc_ids_scope_single_no_id():
    """scope=single without document_id returns empty list."""
    db = AsyncMock()
    result = await retrieval_service._get_candidate_doc_ids(db, "single", None)
    assert result == []


# ── build_rag_prompt ──

@pytest.mark.asyncio
async def test_build_rag_prompt_with_chunks():
    """When chunks are retrieved, prompt contains document context."""
    db = AsyncMock()
    provider = _make_provider()

    mock_chunks = [
        retrieval_service.RetrievedChunk(
            chunk_id="c1", document_id="d1", document_name="test.pdf",
            chunk_index=0, content="重要内容片段", page_no=1, score=0.95,
        )
    ]

    with patch.object(retrieval_service, "retrieve_chunks",
                      new=AsyncMock(return_value=(mock_chunks, "keyword"))):
        result = await retrieval_service.build_rag_prompt(db, "问题")

    assert isinstance(result, retrieval_service.RAGResult)
    assert result.retrieval_method == "keyword"
    assert len(result.chunks) == 1
    assert "重要内容片段" in result.system_prompt
    assert "test.pdf" in result.system_prompt


@pytest.mark.asyncio
async def test_build_rag_prompt_no_chunks():
    """When no chunks are retrieved, use NO_CONTEXT_PROMPT."""
    db = AsyncMock()

    with patch.object(retrieval_service, "retrieve_chunks",
                      new=AsyncMock(return_value=([], "none"))):
        result = await retrieval_service.build_rag_prompt(db, "问题")

    assert result.retrieval_method == "none"
    assert result.chunks == []
    assert result.system_prompt == retrieval_service._NO_CONTEXT_PROMPT


# ── retrieve_chunks ──

@pytest.mark.asyncio
async def test_retrieve_chunks_no_docs_returns_none():
    """When no candidate documents exist, return empty."""
    db = AsyncMock()

    with patch.object(retrieval_service, "_get_candidate_doc_ids",
                      new=AsyncMock(return_value=[])):
        chunks, method = await retrieval_service.retrieve_chunks(db, "query")

    assert chunks == []
    assert method == "none"


@pytest.mark.asyncio
async def test_retrieve_chunks_keyword_fallback():
    """When vector retrieval fails, fall back to keyword search."""
    db = AsyncMock()
    provider = _make_provider()

    mock_chunk = _make_chunk("c1", "d1", "keyword content", chunk_index=0)

    with patch.object(retrieval_service, "_get_candidate_doc_ids",
                      new=AsyncMock(return_value=["d1"])), \
         patch.object(retrieval_service, "can_use_embeddings", return_value=True), \
         patch.object(retrieval_service, "_ensure_provider_embeddings",
                      new=AsyncMock(side_effect=Exception("embedding failed"))), \
         patch.object(retrieval_service, "_load_candidate_chunks",
                      new=AsyncMock(return_value=[mock_chunk])), \
         patch.object(retrieval_service, "_keyword_retrieve",
                      new=AsyncMock(return_value=[
                   retrieval_service.RetrievedChunk(
                       chunk_id="c1", document_id="d1", document_name="test.txt",
                       chunk_index=0, content="keyword content", score=1.0,
                   )
               ])):

        provider_result = MagicMock()
        provider_result.scalar_one_or_none = MagicMock(return_value=provider)
        db.execute = AsyncMock(return_value=provider_result)

        chunks, method = await retrieval_service.retrieve_chunks(db, "keyword")

    assert method == "keyword"
    assert len(chunks) == 1
