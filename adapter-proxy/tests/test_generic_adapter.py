from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from adapters.generic import GenericHTTPAdapter, _extract_by_path
from tests.conftest import DummyResponse, DummyStreamContext, DummyStreamResponse


def _collect_chunks(generator) -> list[str]:
    async def consume():
        items = []
        async for chunk in generator:
            items.append(chunk)
        return items

    return asyncio.run(consume())


def test_extract_by_path_handles_nested_values():
    data = {"result": {"text": "hello", "token": {"done": False}}}

    assert _extract_by_path(data, "result.text") == "hello"
    assert _extract_by_path(data, "result.token.done") is False
    assert _extract_by_path(data, "result.missing") is None


def test_default_request_template_escapes_prompt_text():
    adapter = GenericHTTPAdapter(model_name="demo", base_url="http://localhost:9090")
    prompt = 'He said "hi"\\nnext line \\\\ end'

    body = adapter._render_request_body(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=32,
    )

    assert body["prompt"] == f"[User] {prompt}"
    assert body["max_tokens"] == 32


def test_chat_completion_parses_nested_response_content():
    adapter = GenericHTTPAdapter(
        model_name="demo",
        base_url="http://localhost:9090",
        response_content_path="result.text",
    )

    with patch(
        "httpx.AsyncClient.post",
        new=AsyncMock(return_value=DummyResponse({"result": {"text": "ok"}})),
    ):
        result = asyncio.run(
            adapter.chat_completion(
                messages=[{"role": "user", "content": "hello"}],
                temperature=0.3,
                max_tokens=16,
            )
        )

    assert result["choices"][0]["message"]["content"] == "ok"


def test_chat_completion_handles_array_response():
    adapter = GenericHTTPAdapter(
        model_name="demo",
        base_url="http://localhost:9090",
        response_content_path="generated_text",
    )

    with patch(
        "httpx.AsyncClient.post",
        new=AsyncMock(return_value=DummyResponse([{"generated_text": "hello"}])),
    ):
        result = asyncio.run(
            adapter.chat_completion(
                messages=[{"role": "user", "content": "hello"}],
                temperature=0.3,
                max_tokens=16,
            )
        )

    assert result["choices"][0]["message"]["content"] == "hello"


def test_chat_completion_stream_parses_sse_lines_and_done():
    adapter = GenericHTTPAdapter(
        model_name="demo",
        base_url="http://localhost:9090",
        stream=True,
        stream_content_path="token.text",
        stream_done_field="done",
    )
    stream_response = DummyStreamResponse(
        [
            'data: {"token": {"text": "Hel"}, "done": false}',
            "",
            'data: {"token": {"text": "lo"}, "done": false}',
            "not-json",
            'data: {"token": {"text": ""}, "done": true}',
        ]
    )

    with patch(
        "httpx.AsyncClient.stream",
        new=lambda *args, **kwargs: DummyStreamContext(stream_response),
    ):
        chunks = _collect_chunks(
            adapter.chat_completion_stream(
                messages=[{"role": "user", "content": "hello"}],
                temperature=0.3,
                max_tokens=16,
            )
        )

    assert any('"Hel"' in chunk for chunk in chunks)
    assert any('"lo"' in chunk for chunk in chunks)
    assert chunks[-1].strip().endswith("data: [DONE]")


def test_chat_completion_stream_falls_back_when_stream_disabled():
    adapter = GenericHTTPAdapter(
        model_name="demo",
        base_url="http://localhost:9090",
        stream=False,
        response_content_path="text",
    )

    with patch(
        "httpx.AsyncClient.post",
        new=AsyncMock(return_value=DummyResponse({"text": "full answer"})),
    ):
        chunks = _collect_chunks(
            adapter.chat_completion_stream(
                messages=[{"role": "user", "content": "hello"}],
                temperature=0.3,
                max_tokens=16,
            )
        )

    assert any("full answer" in chunk for chunk in chunks)
    assert chunks[-1].strip().endswith("data: [DONE]")
