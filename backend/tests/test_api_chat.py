from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass

from fastapi.testclient import TestClient
from sqlalchemy import select


def _provider_payload(**overrides):
    payload = {
        "provider_type": "openai",
        "base_url": "https://api.openai.com",
        "model_name": "gpt-4o-mini",
        "api_key": "sk-test-key",
        "embedding_model": "text-embedding-3-small",
        "enable_embedding": True,
        "temperature": 0.7,
        "max_tokens": 512,
        "timeout_seconds": 30,
        "is_default": False,
    }
    payload.update(overrides)
    return payload


async def _mark_provider_verified(app_ctx, provider_id: str) -> None:
    async with app_ctx.database.async_session() as db:
        provider = (
            await db.execute(
                select(app_ctx.provider_models.ProviderConfig).where(
                    app_ctx.provider_models.ProviderConfig.id == provider_id
                )
            )
        ).scalar_one()
        provider.last_test_success = True
        provider.last_test_message = "测试成功"
        db.add(provider)
        await db.commit()


@dataclass
class _FakeChunk:
    document_name: str
    chunk_index: int
    content: str
    page_no: int | None = None
    score: float | None = None


@dataclass
class _FakeRagResult:
    system_prompt: str
    chunks: list[_FakeChunk]
    retrieval_method: str


def test_create_session(app_ctx):
    with TestClient(app_ctx.main.app) as client:
        provider = client.post("/api/providers", json=_provider_payload())
        assert provider.status_code == 201
        asyncio.run(_mark_provider_verified(app_ctx, provider.json()["id"]))

        response = client.post(
            "/api/sessions",
            json={"scope_type": "all", "provider_id": provider.json()["id"]},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["provider_id"] == provider.json()["id"]


def test_create_session_rejects_unverified_provider(app_ctx):
    with TestClient(app_ctx.main.app) as client:
        provider = client.post("/api/providers", json=_provider_payload())
        assert provider.status_code == 201

        response = client.post(
            "/api/sessions",
            json={"scope_type": "all", "provider_id": provider.json()["id"]},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "请选择已经测试连接成功的供应商"


def test_send_message_sse_format(app_ctx, monkeypatch):
    async def fake_build_rag_prompt(*_args, **_kwargs):
        return _FakeRagResult(
            system_prompt="system prompt",
            retrieval_method="keyword",
            chunks=[_FakeChunk(document_name="sample.txt", chunk_index=0, content="alpha chunk", page_no=1, score=1.0)],
        )

    async def fake_stream_chat_completion(_provider, _messages, _user_content, system_prompt=None):
        assert system_prompt == "system prompt"
        yield 'data: {"type":"token","content":"hello"}\n\n'
        yield 'data: {"type":"token","content":" world"}\n\n'

    monkeypatch.setattr(app_ctx.chat_api, "build_rag_prompt", fake_build_rag_prompt)
    monkeypatch.setattr(app_ctx.chat_api, "stream_chat_completion", fake_stream_chat_completion)

    with TestClient(app_ctx.main.app) as client:
        provider = client.post("/api/providers", json=_provider_payload())
        assert provider.status_code == 201
        asyncio.run(_mark_provider_verified(app_ctx, provider.json()["id"]))
        session = client.post(
            "/api/sessions",
            json={"scope_type": "all", "provider_id": provider.json()["id"]},
        )
        assert session.status_code == 201

        with client.stream(
            "POST",
            f"/api/sessions/{session.json()['id']}/messages",
            json={"content": "hello?"},
        ) as response:
            assert response.status_code == 200
            body = "".join(response.iter_text())

    assert '"type":"sources"' in body or '"type": "sources"' in body
    assert '"type":"token"' in body
    assert '"type":"done"' in body or '"type": "done"' in body
    assert '"type":"error"' not in body


def test_regenerate_message(app_ctx, monkeypatch):
    mode = "initial"

    async def fake_build_rag_prompt(*_args, **_kwargs):
        return _FakeRagResult(
            system_prompt="system prompt",
            retrieval_method="keyword",
            chunks=[_FakeChunk(document_name="sample.txt", chunk_index=0, content="alpha chunk")],
        )

    async def fake_stream_chat_completion(_provider, _messages, _user_content, system_prompt=None):
        nonlocal mode
        if mode == "initial":
            yield 'data: {"type":"token","content":"old answer"}\n\n'
            return

        assert system_prompt is not None
        assert "不满意" in system_prompt
        yield 'data: {"type":"token","content":"new answer"}\n\n'

    monkeypatch.setattr(app_ctx.chat_api, "build_rag_prompt", fake_build_rag_prompt)
    monkeypatch.setattr(app_ctx.chat_api, "stream_chat_completion", fake_stream_chat_completion)

    with TestClient(app_ctx.main.app) as client:
        provider = client.post("/api/providers", json=_provider_payload())
        assert provider.status_code == 201
        asyncio.run(_mark_provider_verified(app_ctx, provider.json()["id"]))
        session = client.post(
            "/api/sessions",
            json={"scope_type": "all", "provider_id": provider.json()["id"]},
        )
        assert session.status_code == 201
        session_id = session.json()["id"]

        with client.stream(
            "POST",
            f"/api/sessions/{session_id}/messages",
            json={"content": "question"},
        ) as response:
            assert response.status_code == 200
            body = "".join(response.iter_text())

        assistant_id = re.search(r'"message_id"\s*:\s*"([^"]+)"', body).group(1)
        mode = "regen"

        with client.stream(
            "POST",
            f"/api/sessions/{session_id}/messages/{assistant_id}/regenerate",
            json={},
        ) as response:
            assert response.status_code == 200
            regen_body = "".join(response.iter_text())

        messages = client.get(f"/api/sessions/{session_id}/messages")

    assert '"type":"done"' in regen_body or '"type": "done"' in regen_body
    assert messages.status_code == 200
    assert messages.json()[-1]["id"] == assistant_id
    assert messages.json()[-1]["content"] == "new answer"


def test_delete_session(app_ctx, monkeypatch):
    async def fake_build_rag_prompt(*_args, **_kwargs):
        return _FakeRagResult(
            system_prompt="system prompt",
            retrieval_method="none",
            chunks=[],
        )

    async def fake_stream_chat_completion(_provider, _messages, _user_content, system_prompt=None):
        yield 'data: {"type":"token","content":"bye"}\n\n'

    monkeypatch.setattr(app_ctx.chat_api, "build_rag_prompt", fake_build_rag_prompt)
    monkeypatch.setattr(app_ctx.chat_api, "stream_chat_completion", fake_stream_chat_completion)

    with TestClient(app_ctx.main.app) as client:
        provider = client.post("/api/providers", json=_provider_payload())
        assert provider.status_code == 201
        asyncio.run(_mark_provider_verified(app_ctx, provider.json()["id"]))
        session = client.post(
            "/api/sessions",
            json={"scope_type": "all", "provider_id": provider.json()["id"]},
        )
        assert session.status_code == 201
        session_id = session.json()["id"]

        with client.stream(
            "POST",
            f"/api/sessions/{session_id}/messages",
            json={"content": "question"},
        ) as response:
            assert response.status_code == 200
            _ = "".join(response.iter_text())

        deleted = client.delete(f"/api/sessions/{session_id}")
        messages = client.get(f"/api/sessions/{session_id}/messages")

    assert deleted.status_code == 204
    assert messages.status_code == 404


def test_deleted_provider_session_can_still_browse_but_cannot_send(app_ctx, monkeypatch):
    async def fake_build_rag_prompt(*_args, **_kwargs):
        return _FakeRagResult(
            system_prompt="system prompt",
            retrieval_method="keyword",
            chunks=[_FakeChunk(document_name="sample.txt", chunk_index=0, content="alpha chunk")],
        )

    async def fake_stream_chat_completion(_provider, _messages, _user_content, system_prompt=None):
        assert system_prompt == "system prompt"
        yield 'data: {"type":"token","content":"first answer"}\n\n'

    monkeypatch.setattr(app_ctx.chat_api, "build_rag_prompt", fake_build_rag_prompt)
    monkeypatch.setattr(app_ctx.chat_api, "stream_chat_completion", fake_stream_chat_completion)

    with TestClient(app_ctx.main.app) as client:
        provider = client.post("/api/providers", json=_provider_payload())
        assert provider.status_code == 201
        asyncio.run(_mark_provider_verified(app_ctx, provider.json()["id"]))
        session = client.post(
            "/api/sessions",
            json={"scope_type": "all", "provider_id": provider.json()["id"]},
        )
        assert session.status_code == 201
        session_id = session.json()["id"]

        with client.stream(
            "POST",
            f"/api/sessions/{session_id}/messages",
            json={"content": "question"},
        ) as response:
            assert response.status_code == 200
            _ = "".join(response.iter_text())

        deleted = client.delete(f"/api/providers/{provider.json()['id']}")
        messages = client.get(f"/api/sessions/{session_id}/messages")
        send_again = client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "next question"},
        )

    assert deleted.status_code == 204
    assert messages.status_code == 200
    assert len(messages.json()) == 2
    assert send_again.status_code == 400
    assert "供应商已被删除" in send_again.json()["detail"]


def test_deleted_provider_session_cannot_regenerate(app_ctx, monkeypatch):
    async def fake_build_rag_prompt(*_args, **_kwargs):
        return _FakeRagResult(
            system_prompt="system prompt",
            retrieval_method="keyword",
            chunks=[_FakeChunk(document_name="sample.txt", chunk_index=0, content="alpha chunk")],
        )

    async def fake_stream_chat_completion(_provider, _messages, _user_content, system_prompt=None):
        yield 'data: {"type":"token","content":"old answer"}\n\n'

    monkeypatch.setattr(app_ctx.chat_api, "build_rag_prompt", fake_build_rag_prompt)
    monkeypatch.setattr(app_ctx.chat_api, "stream_chat_completion", fake_stream_chat_completion)

    with TestClient(app_ctx.main.app) as client:
        provider = client.post("/api/providers", json=_provider_payload())
        assert provider.status_code == 201
        asyncio.run(_mark_provider_verified(app_ctx, provider.json()["id"]))
        session = client.post(
            "/api/sessions",
            json={"scope_type": "all", "provider_id": provider.json()["id"]},
        )
        assert session.status_code == 201
        session_id = session.json()["id"]

        with client.stream(
            "POST",
            f"/api/sessions/{session_id}/messages",
            json={"content": "question"},
        ) as response:
            assert response.status_code == 200
            body = "".join(response.iter_text())

        assistant_id = re.search(r'"message_id"\s*:\s*"([^"]+)"', body).group(1)
        deleted = client.delete(f"/api/providers/{provider.json()['id']}")
        regenerate = client.post(
            f"/api/sessions/{session_id}/messages/{assistant_id}/regenerate",
            json={},
        )

    assert deleted.status_code == 204
    assert regenerate.status_code == 400
    assert "供应商已被删除" in regenerate.json()["detail"]
