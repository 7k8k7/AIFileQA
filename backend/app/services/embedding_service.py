"""Embedding service — call provider API to generate text embeddings.

Uses the default provider's embedding endpoint.
For OpenAI / compatible: POST /v1/embeddings
For Claude: falls back to keyword-based retrieval (no native embedding API).

Embeddings are stored as JSON-serialized float lists in the `embedding` column.
"""

from __future__ import annotations

import json
import logging

import httpx

from app.models.provider import ProviderConfig
from app.services.provider_url import build_provider_url, normalize_provider_base_url

logger = logging.getLogger(__name__)


async def generate_embeddings(
    provider: ProviderConfig,
    texts: list[str],
) -> list[list[float] | None]:
    """Generate embeddings for a batch of texts.

    Returns a list of float vectors (or None for texts that failed).
    If the provider doesn't support embeddings (e.g. Claude), returns all None.
    """
    if provider.provider_type == "claude":
        # Anthropic has no embedding API — skip
        logger.info("Claude provider has no embedding API, skipping vectorization")
        return [None] * len(texts)

    url = normalize_provider_base_url(provider.base_url)
    url = build_provider_url(url, "/v1/embeddings")

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if provider.api_key:
        headers["Authorization"] = f"Bearer {provider.api_key}"

    # Batch in groups of 100 to avoid API limits
    batch_size = 100
    results: list[list[float] | None] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(url, headers=headers, json={
                    "model": _embedding_model(provider),
                    "input": batch,
                })
                resp.raise_for_status()
                data = resp.json()

                embeddings = [None] * len(batch)
                for item in data.get("data", []):
                    idx = item.get("index", 0)
                    if idx < len(embeddings):
                        embeddings[idx] = item.get("embedding")
                results.extend(embeddings)

        except Exception as e:
            logger.warning("Embedding batch %d failed: %s", i, str(e)[:200])
            results.extend([None] * len(batch))

    return results


def serialize_embedding(embedding: list[float] | None) -> str | None:
    """Serialize embedding to JSON string for SQLite storage."""
    if embedding is None:
        return None
    return json.dumps(embedding)


def deserialize_embedding(data: str | None) -> list[float] | None:
    """Deserialize JSON string back to float list."""
    if not data:
        return None
    return json.loads(data)


def _embedding_model(provider: ProviderConfig) -> str:
    """Determine which embedding model to use based on provider type."""
    if provider.provider_type == "openai":
        return "text-embedding-3-small"
    # For compatible providers, try a common default
    return "text-embedding-3-small"
