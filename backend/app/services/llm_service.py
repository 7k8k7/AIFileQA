"""LLM streaming service — calls provider APIs and yields SSE tokens."""

import json
from collections.abc import AsyncGenerator
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.provider import ProviderConfig
from app.models.chat import ChatMessage
from app.services.provider_url import build_provider_url, normalize_provider_base_url

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM_PROMPT = (
    "以下是更早对话的压缩摘要，仅用于保留上下文。"
    "如果它与最近几轮原始消息冲突，请以最近几轮原始消息为准。\n\n{summary}"
)


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
    summary_text, recent_messages = _prepare_conversation_context(messages)

    # Build message history
    history: list[dict[str, str]] = []

    # For OpenAI-compatible: inject system prompt as first message
    if system_prompt and provider.provider_type != "claude":
        history.append({"role": "system", "content": system_prompt})
    if summary_text and provider.provider_type != "claude":
        history.append({
            "role": "system",
            "content": SUMMARY_SYSTEM_PROMPT.format(summary=summary_text),
        })

    for m in recent_messages:
        history.append({"role": m.role, "content": m.content})
    history.append({"role": "user", "content": user_content})

    url = normalize_provider_base_url(provider.base_url)
    headers: dict[str, str] = {"Content-Type": "application/json"}

    if provider.provider_type == "claude":
        # ── Anthropic Messages API ──
        headers["x-api-key"] = provider.api_key
        headers["anthropic-version"] = "2023-06-01"
        url = build_provider_url(url, "/v1/messages")
        claude_system_prompt = _merge_system_and_summary(system_prompt, summary_text)
        payload: dict = {
            "model": provider.model_name,
            "max_tokens": provider.max_tokens,
            "temperature": provider.temperature,
            "stream": True,
            "messages": history,
        }
        # Anthropic uses a separate 'system' field
        if claude_system_prompt:
            payload["system"] = claude_system_prompt
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


def _prepare_conversation_context(messages: list[ChatMessage]) -> tuple[str | None, list[ChatMessage]]:
    if not messages:
        return None, []

    recent_limit = max(settings.conversation_recent_messages, 0)
    summary_char_limit = max(settings.conversation_summary_chars, 0)
    history_char_budget = max(settings.conversation_history_char_budget, 0)

    recent_messages = list(messages[-recent_limit:]) if recent_limit else []
    older_messages = list(messages[:-recent_limit]) if recent_limit else list(messages)

    if history_char_budget > 0 and recent_messages:
        trimmed_recent: list[ChatMessage] = []
        used_chars = 0
        for message in reversed(recent_messages):
            content_len = len((message.content or "").strip())
            if trimmed_recent and used_chars + content_len > history_char_budget:
                break
            trimmed_recent.append(message)
            used_chars += content_len
        recent_messages = list(reversed(trimmed_recent))
        if not recent_messages and messages:
            recent_messages = [messages[-1]]

    summary_text = _summarize_messages(older_messages, max_chars=summary_char_limit)
    logger.info(
        "LLM context prepared: total=%d, summarized=%d, recent=%d, summary_chars=%d",
        len(messages),
        len(older_messages),
        len(recent_messages),
        len(summary_text or ""),
    )
    return summary_text, recent_messages


def _summarize_messages(messages: list[ChatMessage], *, max_chars: int) -> str | None:
    if not messages or max_chars <= 0:
        return None

    lines: list[str] = []
    current_len = 0
    truncated = False

    for message in messages:
        role_label = "用户" if message.role == "user" else "助手"
        content = _clip_text((message.content or "").strip(), 180)
        if not content:
            continue
        line = f"- {role_label}：{content}"
        addition = len(line) + (1 if lines else 0)
        if current_len + addition > max_chars:
            truncated = True
            break
        lines.append(line)
        current_len += addition

    if not lines:
        return None
    if truncated:
        suffix = "\n- 以上仅保留更早对话的关键信息摘要。"
        if current_len + len(suffix) <= max_chars:
            lines.append(suffix.lstrip("\n"))

    return "\n".join(lines)


def _clip_text(content: str, limit: int) -> str:
    normalized = " ".join(content.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(limit - 1, 1)].rstrip() + "…"


def _merge_system_and_summary(system_prompt: str | None, summary_text: str | None) -> str | None:
    if system_prompt and summary_text:
        return f"{system_prompt}\n\n{SUMMARY_SYSTEM_PROMPT.format(summary=summary_text)}"
    return system_prompt or (
        SUMMARY_SYSTEM_PROMPT.format(summary=summary_text) if summary_text else None
    )


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
