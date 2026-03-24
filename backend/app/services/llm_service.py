"""LLM streaming service — calls provider APIs and yields SSE tokens."""

import json
from collections.abc import AsyncGenerator

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import ProviderConfig
from app.models.chat import ChatMessage
from app.services.provider_url import build_provider_url, normalize_provider_base_url


async def get_default_provider(db: AsyncSession) -> ProviderConfig | None:
    return (
        await db.execute(
            select(ProviderConfig).where(ProviderConfig.is_default == True)  # noqa: E712
        )
    ).scalar_one_or_none()


async def stream_chat_completion(
    provider: ProviderConfig,
    messages: list[ChatMessage],
    user_content: str,
    system_prompt: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Call the LLM provider's streaming API and yield SSE-formatted lines.

    Args:
        system_prompt: Optional RAG system prompt with document context.

    Yields lines like:
        data: {"type":"token","content":"Hello"}
        data: {"type":"done","message_id":"..."}
    """
    # Build message history
    history: list[dict[str, str]] = []

    # For OpenAI-compatible: inject system prompt as first message
    if system_prompt and provider.provider_type != "claude":
        history.append({"role": "system", "content": system_prompt})

    for m in messages:
        history.append({"role": m.role, "content": m.content})
    history.append({"role": "user", "content": user_content})

    url = normalize_provider_base_url(provider.base_url)
    headers: dict[str, str] = {"Content-Type": "application/json"}

    if provider.provider_type == "claude":
        # ── Anthropic Messages API ──
        headers["x-api-key"] = provider.api_key
        headers["anthropic-version"] = "2023-06-01"
        url = build_provider_url(url, "/v1/messages")
        payload: dict = {
            "model": provider.model_name,
            "max_tokens": provider.max_tokens,
            "temperature": provider.temperature,
            "stream": True,
            "messages": history,
        }
        # Anthropic uses a separate 'system' field
        if system_prompt:
            payload["system"] = system_prompt
        async for chunk in _stream_anthropic(url, headers, payload, provider.timeout_seconds):
            yield chunk
    else:
        # ── OpenAI-compatible Chat Completions ──
        if provider.api_key:
            headers["Authorization"] = f"Bearer {provider.api_key}"
        url = build_provider_url(url, "/v1/chat/completions")
        payload = {
            "model": provider.model_name,
            "max_tokens": provider.max_tokens,
            "temperature": provider.temperature,
            "stream": True,
            "messages": history,
        }
        async for chunk in _stream_openai(url, headers, payload, provider.timeout_seconds):
            yield chunk


async def _stream_openai(
    url: str, headers: dict, payload: dict, timeout: int
) -> AsyncGenerator[str, None]:
    """Stream OpenAI-compatible SSE and yield token events."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, headers=headers, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                    delta = obj.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield f"data: {json.dumps({'type': 'token', 'content': content}, ensure_ascii=False)}\n\n"
                except (json.JSONDecodeError, IndexError, KeyError):
                    continue


async def _stream_anthropic(
    url: str, headers: dict, payload: dict, timeout: int
) -> AsyncGenerator[str, None]:
    """Stream Anthropic SSE and yield token events."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, headers=headers, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                try:
                    obj = json.loads(data)
                    event_type = obj.get("type")
                    if event_type == "content_block_delta":
                        text = obj.get("delta", {}).get("text", "")
                        if text:
                            yield f"data: {json.dumps({'type': 'token', 'content': text}, ensure_ascii=False)}\n\n"
                except (json.JSONDecodeError, KeyError):
                    continue
