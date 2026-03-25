"""HuggingFace Text Generation Inference (TGI) adapter.

TGI native API reference:
  - Streaming:  POST /generate_stream  → SSE with {"token": {"text": "..."}}
  - Blocking:   POST /generate         → [{"generated_text": "..."}]
  - Model info: GET  /info             → {"model_id": "...", ...}
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator

import httpx

from .base import BaseAdapter

logger = logging.getLogger(__name__)


class HuggingFaceTGIAdapter(BaseAdapter):
    """Translate OpenAI chat format ↔ HuggingFace TGI native API."""

    async def chat_completion_stream(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> AsyncGenerator[str, None]:
        prompt = self.messages_to_prompt(messages)
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": max(temperature, 0.01),  # TGI rejects 0
                "do_sample": temperature > 0,
            },
        }

        url = f"{self.base_url}/generate_stream"
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", url, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data:
                        continue
                    try:
                        obj = json.loads(data)
                        token_text = obj.get("token", {}).get("text", "")
                        special = obj.get("token", {}).get("special", False)
                        if token_text and not special:
                            yield self.wrap_sse_chunk(token_text, self.model_name)
                    except json.JSONDecodeError:
                        continue

        yield self.wrap_sse_done(self.model_name)

    async def chat_completion(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> dict:
        prompt = self.messages_to_prompt(messages)
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": max(temperature, 0.01),
                "do_sample": temperature > 0,
            },
        }

        url = f"{self.base_url}/generate"
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        # TGI returns [{"generated_text": "..."}] or {"generated_text": "..."}
        if isinstance(data, list):
            text = data[0].get("generated_text", "") if data else ""
        else:
            text = data.get("generated_text", "")

        return self.wrap_full_response(text, self.model_name)

    async def list_models(self) -> list[dict]:
        """Fetch model info from TGI /info endpoint."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self.base_url}/info")
                resp.raise_for_status()
                info = resp.json()
                model_id = info.get("model_id", self.model_name)
                return [
                    {
                        "id": self.model_name,
                        "object": "model",
                        "created": 0,
                        "owned_by": f"tgi:{model_id}",
                    }
                ]
        except Exception:
            return await super().list_models()
