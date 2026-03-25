from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from adapters.huggingface import HuggingFaceTGIAdapter
from tests.conftest import DummyResponse, DummyStreamContext, DummyStreamResponse


def _collect_chunks(generator) -> list[str]:
    async def consume():
        items = []
        async for chunk in generator:
            items.append(chunk)
        return items

    return asyncio.run(consume())


def test_chat_completion_maps_generated_text():
    adapter = HuggingFaceTGIAdapter(model_name="demo", base_url="http://localhost:8082")

    with patch(
        "httpx.AsyncClient.post",
        new=AsyncMock(return_value=DummyResponse({"generated_text": "hello"})),
    ):
        result = asyncio.run(
            adapter.chat_completion(
                messages=[{"role": "user", "content": "hello"}],
                temperature=0.5,
                max_tokens=20,
            )
        )

    assert result["choices"][0]["message"]["content"] == "hello"


def test_chat_completion_stream_parses_tokens_and_skips_special():
    adapter = HuggingFaceTGIAdapter(model_name="demo", base_url="http://localhost:8082")
    stream_response = DummyStreamResponse(
        [
            'data: {"token": {"text": "He", "special": false}}',
            'data: {"token": {"text": "<eos>", "special": true}}',
            'data: {"token": {"text": "llo", "special": false}}',
        ]
    )

    with patch(
        "httpx.AsyncClient.stream",
        new=lambda *args, **kwargs: DummyStreamContext(stream_response),
    ):
        chunks = _collect_chunks(
            adapter.chat_completion_stream(
                messages=[{"role": "user", "content": "hello"}],
                temperature=0.5,
                max_tokens=20,
            )
        )

    assert any('"He"' in chunk for chunk in chunks)
    assert any('"llo"' in chunk for chunk in chunks)
    assert not any("<eos>" in chunk for chunk in chunks)
    assert chunks[-1].strip().endswith("data: [DONE]")


def test_list_models_uses_info_endpoint_when_available():
    adapter = HuggingFaceTGIAdapter(model_name="demo", base_url="http://localhost:8082")

    with patch(
        "httpx.AsyncClient.get",
        new=AsyncMock(return_value=DummyResponse({"model_id": "Qwen/Qwen2-7B-Instruct"})),
    ):
        models = asyncio.run(adapter.list_models())

    assert models == [
        {
            "id": "demo",
            "object": "model",
            "created": 0,
            "owned_by": "tgi:Qwen/Qwen2-7B-Instruct",
        }
    ]


def test_list_models_falls_back_when_info_fails():
    adapter = HuggingFaceTGIAdapter(model_name="demo", base_url="http://localhost:8082")

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=RuntimeError("boom"))):
        models = asyncio.run(adapter.list_models())

    assert models == [
        {
            "id": "demo",
            "object": "model",
            "created": 0,
            "owned_by": "adapter-proxy",
        }
    ]
