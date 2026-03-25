"""LLM Adapter Proxy — translates non-OpenAI-compatible APIs into OpenAI format.

Usage:
    uvicorn main:app --host 0.0.0.0 --port 11435

Then point DocQA's openai_compatible provider at http://localhost:11435.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from config import load_adapters
from adapters.base import BaseAdapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Global adapter registry — populated on startup
_adapters: dict[str, BaseAdapter] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _adapters
    _adapters = load_adapters()
    if not _adapters:
        logger.warning("No adapters configured. Create config.yaml and restart.")
    yield


app = FastAPI(title="LLM Adapter Proxy", lifespan=lifespan)


# ── Request / Response models ──

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    temperature: float = 0.7
    max_tokens: int = 4096
    stream: bool = False


# ── Endpoints ──

@app.get("/health")
async def health():
    return {"status": "ok", "adapters": list(_adapters.keys())}


@app.get("/v1/models")
async def list_models():
    """Return all configured models in OpenAI /v1/models format."""
    models = []
    for adapter in _adapters.values():
        models.extend(await adapter.list_models())
    return {"object": "list", "data": models}


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """Translate OpenAI chat completion request to the target adapter."""
    adapter = _adapters.get(request.model)
    if adapter is None:
        available = list(_adapters.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Model '{request.model}' not found. Available: {available}",
        )

    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    try:
        if request.stream:
            return StreamingResponse(
                adapter.chat_completion_stream(
                    messages=messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )
        else:
            result = await adapter.chat_completion(
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
            return JSONResponse(content=result)

    except Exception as e:
        logger.error("Adapter error for model '%s': %s", request.model, str(e)[:500])
        raise HTTPException(
            status_code=502,
            detail=f"Backend service error: {str(e)[:200]}",
        )
