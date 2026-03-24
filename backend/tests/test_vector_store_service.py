"""Unit tests for vector_store_service — ChromaDB operations."""

from __future__ import annotations

import pytest

from app.services.vector_store_service import (
    VectorChunkRecord,
    VectorSearchHit,
    _build_where,
    _distance_to_score,
    _vector_id,
)


# ── _vector_id ──

def test_vector_id_format():
    result = _vector_id("p-123", "model-abc", "c-456")
    assert result == "p-123::model-abc::c-456"


# ── _distance_to_score ──

def test_distance_to_score_zero():
    assert _distance_to_score(0.0) == 1.0


def test_distance_to_score_one():
    assert _distance_to_score(1.0) == 0.0


def test_distance_to_score_half():
    assert _distance_to_score(0.5) == 0.5


def test_distance_to_score_none():
    assert _distance_to_score(None) is None


def test_distance_to_score_clamps_negative():
    """Distance > 1.0 should clamp score to 0.0."""
    assert _distance_to_score(1.5) == 0.0


# ── _build_where ──

def test_build_where_no_doc_ids():
    result = _build_where("p-1", "model-a", None)
    assert result == {"$and": [{"provider_id": "p-1"}, {"embedding_model": "model-a"}]}


def test_build_where_single_doc_id():
    result = _build_where("p-1", "model-a", ["d-1"])
    assert result == {
        "$and": [
            {"provider_id": "p-1"},
            {"embedding_model": "model-a"},
            {"document_id": "d-1"},
        ]
    }


def test_build_where_multiple_doc_ids():
    result = _build_where("p-1", "model-a", ["d-1", "d-2"])
    assert result == {
        "$and": [
            {"provider_id": "p-1"},
            {"embedding_model": "model-a"},
            {"document_id": {"$in": ["d-1", "d-2"]}},
        ]
    }


# ── VectorChunkRecord dataclass ──

def test_vector_chunk_record_defaults():
    record = VectorChunkRecord(
        chunk_id="c-1",
        document_id="d-1",
        provider_id="p-1",
        embedding_model="model-a",
        chunk_index=0,
        content="test",
        embedding=[0.1, 0.2],
    )
    assert record.page_no is None
    assert record.section_label is None


# ── VectorSearchHit dataclass ──

def test_vector_search_hit_defaults():
    hit = VectorSearchHit(chunk_id="c-1", document_id="d-1")
    assert hit.score is None


def test_vector_search_hit_with_score():
    hit = VectorSearchHit(chunk_id="c-1", document_id="d-1", score=0.85)
    assert hit.score == 0.85


# ── Integration-style test with real ChromaDB ──

@pytest.fixture
def clean_vector_store(app_ctx):
    """Provide a clean ChromaDB collection for testing."""
    from app.services.vector_store_service import (
        reset_vector_store_cache,
        _get_collection,
        upsert_document_chunks,
        query_document_chunks,
        delete_document_chunks,
        find_missing_chunk_ids,
    )
    reset_vector_store_cache()
    return {
        "upsert": upsert_document_chunks,
        "query": query_document_chunks,
        "delete": delete_document_chunks,
        "find_missing": find_missing_chunk_ids,
        "collection": _get_collection,
    }


def test_upsert_and_query(clean_vector_store):
    vs = clean_vector_store
    records = [
        VectorChunkRecord(
            chunk_id="c-1",
            document_id="d-1",
            provider_id="p-1",
            embedding_model="model-a",
            chunk_index=0,
            content="machine learning basics",
            embedding=[1.0, 0.0, 0.0],
        ),
        VectorChunkRecord(
            chunk_id="c-2",
            document_id="d-1",
            provider_id="p-1",
            embedding_model="model-a",
            chunk_index=1,
            content="deep learning advanced",
            embedding=[0.0, 1.0, 0.0],
        ),
    ]
    vs["upsert"](records)

    hits = vs["query"](
        query_embedding=[1.0, 0.0, 0.0],
        top_k=2,
        provider_id="p-1",
        embedding_model="model-a",
    )
    assert len(hits) == 2
    # First hit should be the closest (exact match)
    assert hits[0].chunk_id == "c-1"
    assert hits[0].score is not None
    assert hits[0].score > 0.5


def test_delete_document_chunks(clean_vector_store):
    vs = clean_vector_store
    records = [
        VectorChunkRecord(
            chunk_id="c-del",
            document_id="d-del",
            provider_id="p-1",
            embedding_model="model-a",
            chunk_index=0,
            content="to be deleted",
            embedding=[0.5, 0.5, 0.0],
        ),
    ]
    vs["upsert"](records)

    vs["delete"]("d-del")

    hits = vs["query"](
        query_embedding=[0.5, 0.5, 0.0],
        top_k=5,
        provider_id="p-1",
        embedding_model="model-a",
        document_ids=["d-del"],
    )
    assert len(hits) == 0


def test_find_missing_chunk_ids(clean_vector_store):
    vs = clean_vector_store
    records = [
        VectorChunkRecord(
            chunk_id="c-exist",
            document_id="d-1",
            provider_id="p-1",
            embedding_model="model-a",
            chunk_index=0,
            content="exists",
            embedding=[0.1, 0.2, 0.3],
        ),
    ]
    vs["upsert"](records)

    missing = vs["find_missing"]("p-1", "model-a", ["c-exist", "c-missing"])
    assert "c-missing" in missing
    assert "c-exist" not in missing


def test_query_filters_by_document_ids(clean_vector_store):
    vs = clean_vector_store
    records = [
        VectorChunkRecord(
            chunk_id="c-a",
            document_id="d-a",
            provider_id="p-1",
            embedding_model="model-a",
            chunk_index=0,
            content="doc a content",
            embedding=[1.0, 0.0, 0.0],
        ),
        VectorChunkRecord(
            chunk_id="c-b",
            document_id="d-b",
            provider_id="p-1",
            embedding_model="model-a",
            chunk_index=0,
            content="doc b content",
            embedding=[0.9, 0.1, 0.0],
        ),
    ]
    vs["upsert"](records)

    hits = vs["query"](
        query_embedding=[1.0, 0.0, 0.0],
        top_k=10,
        provider_id="p-1",
        embedding_model="model-a",
        document_ids=["d-a"],
    )
    assert len(hits) == 1
    assert hits[0].document_id == "d-a"


def test_upsert_empty_records(clean_vector_store):
    """Upserting empty list should not raise."""
    vs = clean_vector_store
    vs["upsert"]([])  # Should be a no-op


def test_find_missing_empty_input(clean_vector_store):
    vs = clean_vector_store
    missing = vs["find_missing"]("p-1", "model-a", [])
    assert missing == []
