"""Unit tests for llm_service — LLM streaming and message formatting."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.services.llm_service as llm_service


def _make_provider(**overrides):
    defaults = {
        "id": "p-test123",
        "provider_type": "openai",
        "base_url": "https://api.openai.com",
        "model_name": "gpt-4o",
        "api_key": "sk-test",
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


def _make_message(role: str, content: str):
    msg = MagicMock()
    msg.role = role
    msg.content = content
    return msg


# ── OpenAI payload ──

@pytest.mark.asyncio
async def test_openai_includes_system_message():
    """OpenAI-compatible: system prompt is injected as first message."""
    provider = _make_provider(provider_type="openai")
    history = [_make_message("user", "先前的问题"), _make_message("assistant", "先前的回答")]

    captured_payload = {}

    async def mock_stream_lines():
        yield 'data: {"choices":[{"delta":{"content":"hi"}}]}'
        yield "data: [DONE]"

    mock_resp = AsyncMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.aiter_lines = mock_stream_lines

    mock_client = AsyncMock()

    async def mock_stream(method, url, headers=None, json=None):
        captured_payload.update(json or {})
        return mock_resp

    mock_client.stream = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=mock_resp),
        __aexit__=AsyncMock(return_value=False),
    ))

    # Use a simpler approach: patch _stream_openai directly
    collected_tokens = []

    async def fake_stream_openai(url, headers, payload, timeout):
        captured_payload.update(payload)
        yield 'data: {"type": "token", "content": "hello"}\n\n'

    with patch.object(llm_service, "_stream_openai", fake_stream_openai):
        async for chunk in llm_service.stream_chat_completion(
            provider, history, "新问题", system_prompt="你是助手"
        ):
            collected_tokens.append(chunk)

    # Verify system prompt was placed in messages
    messages = captured_payload["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "你是助手"
    # History comes after system
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "先前的问题"
    assert messages[2]["role"] == "assistant"
    assert messages[2]["content"] == "先前的回答"
    # Current user message is last
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "新问题"


@pytest.mark.asyncio
async def test_claude_uses_system_field():
    """Claude: system prompt goes in 'system' field, not in messages."""
    provider = _make_provider(provider_type="claude", api_key="sk-ant-test")

    captured_payload = {}

    async def fake_stream_anthropic(url, headers, payload, timeout):
        captured_payload.update(payload)
        yield 'data: {"type": "token", "content": "hi"}\n\n'

    with patch.object(llm_service, "_stream_anthropic", fake_stream_anthropic):
        tokens = []
        async for chunk in llm_service.stream_chat_completion(
            provider, [], "问题", system_prompt="你是文档助手"
        ):
            tokens.append(chunk)

    assert captured_payload["system"] == "你是文档助手"
    # System should NOT be in messages list
    for msg in captured_payload["messages"]:
        assert msg["role"] != "system"


@pytest.mark.asyncio
async def test_openai_no_system_prompt():
    """When no system_prompt, no system message is added."""
    provider = _make_provider(provider_type="openai")

    captured_payload = {}

    async def fake_stream_openai(url, headers, payload, timeout):
        captured_payload.update(payload)
        yield 'data: {"type": "token", "content": "ok"}\n\n'

    with patch.object(llm_service, "_stream_openai", fake_stream_openai):
        async for _ in llm_service.stream_chat_completion(provider, [], "hello", system_prompt=None):
            pass

    messages = captured_payload["messages"]
    assert not any(m["role"] == "system" for m in messages)
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "hello"


@pytest.mark.asyncio
async def test_history_formatting():
    """Message history preserves role and content order."""
    provider = _make_provider(provider_type="openai")
    history = [
        _make_message("user", "Q1"),
        _make_message("assistant", "A1"),
        _make_message("user", "Q2"),
        _make_message("assistant", "A2"),
    ]

    captured_payload = {}

    async def fake_stream_openai(url, headers, payload, timeout):
        captured_payload.update(payload)
        yield 'data: {"type": "token", "content": "ok"}\n\n'

    with patch.object(llm_service, "_stream_openai", fake_stream_openai):
        async for _ in llm_service.stream_chat_completion(provider, history, "Q3"):
            pass

    messages = captured_payload["messages"]
    roles = [m["role"] for m in messages]
    assert roles == ["user", "assistant", "user", "assistant", "user"]
    assert messages[-1]["content"] == "Q3"


@pytest.mark.asyncio
async def test_openai_long_history_is_summarized_and_trimmed(monkeypatch):
    provider = _make_provider(provider_type="openai")
    history = [
        _make_message("user", "第一轮问题非常长 " * 20),
        _make_message("assistant", "第一轮回答非常长 " * 20),
        _make_message("user", "第二轮问题非常长 " * 20),
        _make_message("assistant", "第二轮回答非常长 " * 20),
        _make_message("user", "第三轮问题"),
        _make_message("assistant", "第三轮回答"),
    ]

    monkeypatch.setattr(llm_service.settings, "conversation_recent_messages", 2)
    monkeypatch.setattr(llm_service.settings, "conversation_summary_chars", 220)
    monkeypatch.setattr(llm_service.settings, "conversation_history_char_budget", 40)

    captured_payload = {}

    async def fake_stream_openai(url, headers, payload, timeout):
        captured_payload.update(payload)
        yield 'data: {"type": "token", "content": "ok"}\n\n'

    with patch.object(llm_service, "_stream_openai", fake_stream_openai):
        async for _ in llm_service.stream_chat_completion(
            provider, history, "当前问题", system_prompt="你是助手"
        ):
            pass

    messages = captured_payload["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "你是助手"
    assert messages[1]["role"] == "system"
    assert "更早对话的压缩摘要" in messages[1]["content"]
    assert "第一轮问题非常长" in messages[1]["content"]
    assert messages[-2]["role"] == "assistant"
    assert messages[-2]["content"] == "第三轮回答"
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "当前问题"


@pytest.mark.asyncio
async def test_claude_merges_summary_into_system_field(monkeypatch):
    provider = _make_provider(provider_type="claude", api_key="sk-ant-test")
    history = [
        _make_message("user", "旧问题一"),
        _make_message("assistant", "旧回答一"),
        _make_message("user", "旧问题二"),
        _make_message("assistant", "旧回答二"),
    ]

    monkeypatch.setattr(llm_service.settings, "conversation_recent_messages", 1)
    monkeypatch.setattr(llm_service.settings, "conversation_summary_chars", 120)
    monkeypatch.setattr(llm_service.settings, "conversation_history_char_budget", 20)

    captured_payload = {}

    async def fake_stream_anthropic(url, headers, payload, timeout):
        captured_payload.update(payload)
        yield 'data: {"type": "token", "content": "ok"}\n\n'

    with patch.object(llm_service, "_stream_anthropic", fake_stream_anthropic):
        async for _ in llm_service.stream_chat_completion(
            provider, history, "新问题", system_prompt="文档助手"
        ):
            pass

    assert "文档助手" in captured_payload["system"]
    assert "更早对话的压缩摘要" in captured_payload["system"]
    assert "旧问题一" in captured_payload["system"]
    roles = [m["role"] for m in captured_payload["messages"]]
    assert roles == ["assistant", "user"]


@pytest.mark.asyncio
async def test_openai_stream_yields_tokens():
    """Verify _stream_openai correctly parses SSE and yields token events."""
    async def mock_lines():
        yield 'data: {"choices":[{"delta":{"content":"Hello"}}]}'
        yield 'data: {"choices":[{"delta":{"content":" World"}}]}'
        yield "data: [DONE]"

    mock_resp = AsyncMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.aiter_lines = mock_lines

    mock_context = AsyncMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_context.__aexit__ = AsyncMock(return_value=False)

    mock_client = AsyncMock()
    mock_client.stream = MagicMock(return_value=mock_context)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    tokens = []
    with patch("app.services.llm_service.httpx.AsyncClient", return_value=mock_client):
        async for line in llm_service._stream_openai("http://test", {}, {}, 30):
            obj = json.loads(line.split("data: ")[1].strip())
            tokens.append(obj["content"])

    assert tokens == ["Hello", " World"]


@pytest.mark.asyncio
async def test_anthropic_stream_yields_tokens():
    """Verify _stream_anthropic correctly parses content_block_delta."""
    async def mock_lines():
        yield 'data: {"type":"content_block_delta","delta":{"text":"你好"}}'
        yield 'data: {"type":"content_block_delta","delta":{"text":"世界"}}'
        yield 'data: {"type":"message_stop"}'

    mock_resp = AsyncMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.aiter_lines = mock_lines

    mock_context = AsyncMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_context.__aexit__ = AsyncMock(return_value=False)

    mock_client = AsyncMock()
    mock_client.stream = MagicMock(return_value=mock_context)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    tokens = []
    with patch("app.services.llm_service.httpx.AsyncClient", return_value=mock_client):
        async for line in llm_service._stream_anthropic("http://test", {}, {}, 30):
            obj = json.loads(line.split("data: ")[1].strip())
            tokens.append(obj["content"])

    assert tokens == ["你好", "世界"]
