"""Unit tests for embedding_service."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.services.embedding_service import (
    can_use_embeddings,
    get_embedding_model,
    generate_embeddings,
    serialize_embedding,
    deserialize_embedding,
)


def _make_provider(**overrides):
    """Create a mock ProviderConfig."""
    defaults = {
        "id": "p-test123",
        "provider_type": "openai",
        "base_url": "https://api.openai.com",
        "model_name": "gpt-4o",
        "api_key": "sk-test",
        "embedding_model": "text-embedding-3-small",
        "enable_embedding": True,
        "temperature": 0.7,
        "max_tokens": 4096,
        "timeout_seconds": 30,
        "is_default": True,
    }
    defaults.update(overrides)
    provider = MagicMock()
    for k, v in defaults.items():
        setattr(provider, k, v)
    return provider


# ── get_embedding_model ──

def test_get_embedding_model_openai_enabled():
    provider = _make_provider(provider_type="openai", enable_embedding=True,
                              embedding_model="text-embedding-3-small")
    assert get_embedding_model(provider) == "text-embedding-3-small"


def test_get_embedding_model_disabled():
    provider = _make_provider(enable_embedding=False)
    assert get_embedding_model(provider) is None


def test_get_embedding_model_empty_string():
    provider = _make_provider(enable_embedding=True, embedding_model="")
    assert get_embedding_model(provider) is None


def test_get_embedding_model_claude_always_none():
    provider = _make_provider(provider_type="claude", enable_embedding=True,
                              embedding_model="some-model")
    assert get_embedding_model(provider) is None


def test_get_embedding_model_openai_compatible():
    provider = _make_provider(provider_type="openai_compatible",
                              enable_embedding=True,
                              embedding_model="nomic-embed-text")
    assert get_embedding_model(provider) == "nomic-embed-text"


# ── can_use_embeddings ──

def test_can_use_embeddings_openai():
    provider = _make_provider(provider_type="openai", enable_embedding=True,
                              embedding_model="text-embedding-3-small")
    assert can_use_embeddings(provider) is True


def test_can_use_embeddings_claude():
    provider = _make_provider(provider_type="claude", enable_embedding=True,
                              embedding_model="model")
    assert can_use_embeddings(provider) is False


def test_can_use_embeddings_disabled():
    provider = _make_provider(enable_embedding=False)
    assert can_use_embeddings(provider) is False


# ── generate_embeddings ──

@pytest.mark.asyncio
async def test_generate_embeddings_no_embedding_support():
    provider = _make_provider(provider_type="claude", enable_embedding=False)
    result = await generate_embeddings(provider, ["hello", "world"])
    assert result == [None, None]


@pytest.mark.asyncio
async def test_generate_embeddings_mock_api():
    provider = _make_provider(
        provider_type="openai",
        enable_embedding=True,
        embedding_model="text-embedding-3-small",
        base_url="https://api.openai.com",
        api_key="sk-test",
    )

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {"index": 0, "embedding": [0.1, 0.2, 0.3]},
            {"index": 1, "embedding": [0.4, 0.5, 0.6]},
        ]
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.embedding_service.httpx.AsyncClient", return_value=mock_client):
        result = await generate_embeddings(provider, ["hello", "world"])

    assert len(result) == 2
    assert result[0] == [0.1, 0.2, 0.3]
    assert result[1] == [0.4, 0.5, 0.6]


@pytest.mark.asyncio
async def test_generate_embeddings_api_failure_returns_none():
    provider = _make_provider(
        provider_type="openai",
        enable_embedding=True,
        embedding_model="text-embedding-3-small",
    )

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.embedding_service.httpx.AsyncClient", return_value=mock_client):
        result = await generate_embeddings(provider, ["text1", "text2"])

    assert result == [None, None]


# ── serialize / deserialize ──

def test_serialize_embedding():
    emb = [0.1, 0.2, 0.3]
    serialized = serialize_embedding(emb)
    assert isinstance(serialized, str)
    assert "[0.1" in serialized


def test_serialize_embedding_none():
    assert serialize_embedding(None) is None


def test_deserialize_embedding():
    serialized = "[0.1, 0.2, 0.3]"
    result = deserialize_embedding(serialized)
    assert result == [0.1, 0.2, 0.3]


def test_deserialize_embedding_none():
    assert deserialize_embedding(None) is None
    assert deserialize_embedding("") is None


def test_serialize_deserialize_roundtrip():
    original = [0.123456789, -0.987654321, 0.0]
    serialized = serialize_embedding(original)
    deserialized = deserialize_embedding(serialized)
    assert deserialized == original
