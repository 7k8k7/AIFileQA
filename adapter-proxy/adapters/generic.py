"""Generic HTTP adapter — supports arbitrary REST APIs via Jinja2 templates.

Users configure the request format, response parsing path, and optional
streaming behavior through YAML configuration.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator

import httpx
import jinja2

from .base import BaseAdapter

logger = logging.getLogger(__name__)


def _extract_by_path(data: dict, path: str):
    """Extract a nested value from a dict using dot-separated path.

    Example: _extract_by_path({"a": {"b": "hello"}}, "a.b") → "hello"
    """
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


class GenericHTTPAdapter(BaseAdapter):
    """Translate OpenAI chat format ↔ any HTTP API via configurable templates."""

    def __init__(
        self,
        model_name: str,
        base_url: str,
        *,
        chat_endpoint: str = "/generate",
        request_template: str = '{"prompt": {{ prompt | tojson }}, "max_tokens": {{ max_tokens }}}',
        response_content_path: str = "text",
        stream: bool = False,
        stream_content_path: str = "token.text",
        stream_done_field: str = "",
    ):
        super().__init__(model_name, base_url)
        self.chat_endpoint = chat_endpoint
        self.request_template = request_template
        self.response_content_path = response_content_path
        self.stream_enabled = stream
        self.stream_content_path = stream_content_path
        self.stream_done_field = stream_done_field
        self._jinja_env = jinja2.Environment(undefined=jinja2.StrictUndefined)

    def _render_request_body(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> dict:
        """Render the Jinja2 request template with provided variables."""
        prompt = self.messages_to_prompt(messages)
        template = self._jinja_env.from_string(self.request_template)
        rendered = template.render(
            prompt=prompt,
            messages=messages,
            messages_json=json.dumps(messages, ensure_ascii=False),
            temperature=temperature,
            max_tokens=max_tokens,
            model=self.model_name,
        )
        return json.loads(rendered)

    async def chat_completion_stream(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> AsyncGenerator[str, None]:
        if not self.stream_enabled:
            # Fall back to non-streaming and emit all at once
            result = await self.chat_completion(messages, temperature, max_tokens)
            content = result["choices"][0]["message"]["content"]
            yield self.wrap_sse_chunk(content, self.model_name)
            yield self.wrap_sse_done(self.model_name)
            return

        body = self._render_request_body(messages, temperature, max_tokens)
        url = f"{self.base_url}{self.chat_endpoint}"

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", url, json=body) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    # Handle SSE format (data: {...})
                    if line.startswith("data:"):
                        line = line[5:].strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        # Check for done signal
                        if self.stream_done_field:
                            if obj.get(self.stream_done_field):
                                break
                        token = _extract_by_path(obj, self.stream_content_path)
                        if token:
                            yield self.wrap_sse_chunk(str(token), self.model_name)
                    except json.JSONDecodeError:
                        continue

        yield self.wrap_sse_done(self.model_name)

    async def chat_completion(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> dict:
        body = self._render_request_body(messages, temperature, max_tokens)
        url = f"{self.base_url}{self.chat_endpoint}"

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()

        # Handle both object and array responses
        if isinstance(data, list):
            data = data[0] if data else {}

        content = _extract_by_path(data, self.response_content_path)
        return self.wrap_full_response(str(content or ""), self.model_name)
