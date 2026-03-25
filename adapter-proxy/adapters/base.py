"""Base adapter class for LLM API translation."""

from __future__ import annotations

import time
import uuid
import json
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator


class BaseAdapter(ABC):
    """Translates requests from OpenAI format to a target LLM API."""

    def __init__(self, model_name: str, base_url: str):
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")

    @abstractmethod
    async def chat_completion_stream(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> AsyncGenerator[str, None]:
        """Yield OpenAI-compatible SSE chunks for streaming chat completion."""
        ...

    @abstractmethod
    async def chat_completion(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> dict:
        """Return a complete OpenAI-compatible chat completion response."""
        ...

    async def list_models(self) -> list[dict]:
        """Return model entries in OpenAI /v1/models format."""
        return [
            {
                "id": self.model_name,
                "object": "model",
                "created": 0,
                "owned_by": "adapter-proxy",
            }
        ]

    # ── Helpers ──

    @staticmethod
    def messages_to_prompt(messages: list[dict]) -> str:
        """Flatten OpenAI messages array into a single prompt string."""
        parts: list[str] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.append(f"[System] {content}")
            elif role == "assistant":
                parts.append(f"[Assistant] {content}")
            else:
                parts.append(f"[User] {content}")
        return "\n".join(parts)

    @staticmethod
    def wrap_sse_chunk(content: str, model: str) -> str:
        """Wrap a token into an OpenAI-compatible SSE delta chunk."""
        chunk = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": content},
                    "finish_reason": None,
                }
            ],
        }
        return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

    @staticmethod
    def wrap_sse_done(model: str) -> str:
        """Emit the final SSE chunk with finish_reason=stop, then [DONE]."""
        chunk = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }
            ],
        }
        return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\ndata: [DONE]\n\n"

    @staticmethod
    def wrap_full_response(content: str, model: str) -> dict:
        """Build a complete OpenAI-compatible chat completion response."""
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
