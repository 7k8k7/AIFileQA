from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi.testclient import TestClient

import main
from adapters.base import BaseAdapter


class FakeAdapter(BaseAdapter):
    async def chat_completion_stream(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> AsyncGenerator[str, None]:
        yield self.wrap_sse_chunk("hello", self.model_name)
        yield self.wrap_sse_done(self.model_name)

    async def chat_completion(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> dict:
        return self.wrap_full_response("full answer", self.model_name)


class BrokenAdapter(BaseAdapter):
    async def chat_completion_stream(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> AsyncGenerator[str, None]:
        raise RuntimeError("stream boom")
        yield

    async def chat_completion(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> dict:
        raise RuntimeError("boom")


def _build_client(monkeypatch, adapters):
    monkeypatch.setattr(main, "load_adapters", lambda: adapters)
    return TestClient(main.app)


def test_health_and_models_list_configured_adapters(monkeypatch):
    adapters = {
        "demo": FakeAdapter("demo", "http://localhost:8082"),
        "demo-2": FakeAdapter("demo-2", "http://localhost:8083"),
    }

    with _build_client(monkeypatch, adapters) as client:
        health = client.get("/health")
        models = client.get("/v1/models")

    assert health.status_code == 200
    assert health.json() == {"status": "ok", "adapters": ["demo", "demo-2"]}
    assert models.status_code == 200
    assert [item["id"] for item in models.json()["data"]] == ["demo", "demo-2"]


def test_chat_completions_returns_openai_like_response(monkeypatch):
    adapters = {"demo": FakeAdapter("demo", "http://localhost:8082")}

    with _build_client(monkeypatch, adapters) as client:
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "demo",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": False,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["model"] == "demo"
    assert body["choices"][0]["message"]["content"] == "full answer"


def test_chat_completions_streams_sse_chunks(monkeypatch):
    adapters = {"demo": FakeAdapter("demo", "http://localhost:8082")}

    with _build_client(monkeypatch, adapters) as client:
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "demo",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": True,
            },
        )

    assert response.status_code == 200
    assert '"hello"' in response.text
    assert "data: [DONE]" in response.text


def test_chat_completions_returns_404_for_unknown_model(monkeypatch):
    with _build_client(monkeypatch, {"demo": FakeAdapter("demo", "http://localhost:8082")}) as client:
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "missing",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

    assert response.status_code == 404
    assert "Available" in response.json()["detail"]


def test_chat_completions_returns_502_when_adapter_fails(monkeypatch):
    with _build_client(monkeypatch, {"demo": BrokenAdapter("demo", "http://localhost:8082")}) as client:
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "demo",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

    assert response.status_code == 502
    assert "Backend service error" in response.json()["detail"]
