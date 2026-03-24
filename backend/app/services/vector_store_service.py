"""Local vector store backed by ChromaDB."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.core.config import settings

COLLECTION_NAME = "document_chunks"


@dataclass
class VectorChunkRecord:
    chunk_id: str
    document_id: str
    provider_id: str
    embedding_model: str
    chunk_index: int
    content: str
    embedding: list[float]
    page_no: int | None = None
    section_label: str | None = None


@dataclass
class VectorSearchHit:
    chunk_id: str
    document_id: str
    score: float | None = None


def _import_chromadb():
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError(
            "ChromaDB 未安装，请先安装 backend 依赖后再使用向量检索"
        ) from exc
    return chromadb


@lru_cache(maxsize=1)
def _get_collection():
    chromadb = _import_chromadb()
    client = chromadb.PersistentClient(path=str(settings.vector_store_path))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def reset_vector_store_cache() -> None:
    _get_collection.cache_clear()


def upsert_document_chunks(records: list[VectorChunkRecord]) -> None:
    if not records:
        return

    collection = _get_collection()
    ids: list[str] = []
    documents: list[str] = []
    embeddings: list[list[float]] = []
    metadatas: list[dict[str, str | int | float | bool]] = []

    for record in records:
        ids.append(_vector_id(record.provider_id, record.embedding_model, record.chunk_id))
        documents.append(record.content)
        embeddings.append(record.embedding)

        metadata: dict[str, str | int | float | bool] = {
            "chunk_id": record.chunk_id,
            "document_id": record.document_id,
            "provider_id": record.provider_id,
            "embedding_model": record.embedding_model,
            "chunk_index": record.chunk_index,
        }
        if record.page_no is not None:
            metadata["page_no"] = record.page_no
        if record.section_label:
            metadata["section_label"] = record.section_label
        metadatas.append(metadata)

    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )


def delete_document_chunks(document_id: str) -> None:
    collection = _get_collection()
    collection.delete(where={"document_id": document_id})


def query_document_chunks(
    query_embedding: list[float],
    *,
    top_k: int,
    provider_id: str,
    embedding_model: str,
    document_ids: list[str] | None = None,
) -> list[VectorSearchHit]:
    collection = _get_collection()
    if collection.count() == 0:
        return []
    where = _build_where(provider_id, embedding_model, document_ids)

    include: list[str] = ["metadatas", "distances"]
    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where,
        include=include,
    )

    ids = result.get("ids", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    hits: list[VectorSearchHit] = []
    for chunk_id, metadata, distance in zip(ids, metadatas, distances):
        metadata = metadata or {}
        raw_chunk_id = metadata.get("chunk_id")
        document_id = metadata.get("document_id")
        if not isinstance(raw_chunk_id, str):
            continue
        if not isinstance(document_id, str):
            continue
        hits.append(
            VectorSearchHit(
                chunk_id=raw_chunk_id,
                document_id=document_id,
                score=_distance_to_score(distance),
            )
        )
    return hits


def find_missing_chunk_ids(
    provider_id: str,
    embedding_model: str,
    chunk_ids: list[str],
) -> list[str]:
    if not chunk_ids:
        return []

    collection = _get_collection()
    expected_ids = [_vector_id(provider_id, embedding_model, chunk_id) for chunk_id in chunk_ids]
    result = collection.get(ids=expected_ids, include=[])
    existing_vector_ids = set(result.get("ids", []))
    missing: list[str] = []
    for chunk_id, vector_id in zip(chunk_ids, expected_ids):
        if vector_id not in existing_vector_ids:
            missing.append(chunk_id)
    return missing


def _build_where(
    provider_id: str,
    embedding_model: str,
    document_ids: list[str] | None,
) -> dict[str, Any]:
    conditions: list[dict[str, Any]] = [
        {"provider_id": provider_id},
        {"embedding_model": embedding_model},
    ]
    if document_ids:
        if len(document_ids) == 1:
            conditions.append({"document_id": document_ids[0]})
        else:
            conditions.append({"document_id": {"$in": document_ids}})
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def _distance_to_score(distance: float | None) -> float | None:
    if distance is None:
        return None
    return max(0.0, 1.0 - float(distance))


def _vector_id(provider_id: str, embedding_model: str, chunk_id: str) -> str:
    return f"{provider_id}::{embedding_model}::{chunk_id}"
