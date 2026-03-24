from __future__ import annotations

import importlib
import re
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select


def _load_app_modules() -> SimpleNamespace:
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            sys.modules.pop(name)

    return SimpleNamespace(
        main=importlib.import_module("app.main"),
        documents_api=importlib.import_module("app.api.documents"),
        chat_api=importlib.import_module("app.api.chat"),
        database=importlib.import_module("app.core.database"),
        document_models=importlib.import_module("app.models.document"),
    )


@pytest.fixture
def app_ctx(monkeypatch: pytest.MonkeyPatch, tmp_path):
    db_path = (tmp_path / "test.db").as_posix()
    upload_dir = (tmp_path / "uploads").as_posix()
    vector_dir = (tmp_path / "chroma").as_posix()

    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("UPLOAD_DIR", upload_dir)
    monkeypatch.setenv("VECTOR_STORE_DIR", vector_dir)
    monkeypatch.setenv("DEBUG", "true")

    return _load_app_modules()


def test_full_flow_upload_parse_chat_sse(
    app_ctx: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_trigger_parse(doc_id: str, _file_path: str, _file_ext: str) -> None:
        async with app_ctx.database.async_session() as db:
            doc = (await db.execute(
                select(app_ctx.document_models.Document).where(
                    app_ctx.document_models.Document.id == doc_id
                )
            )).scalar_one()

            doc.status = "解析中"
            db.add(app_ctx.document_models.DocumentChunk(
                document_id=doc_id,
                chunk_index=0,
                content="alpha policy and onboarding notes",
                page_no=1,
                embedding=None,
            ))
            doc.status = "可用"
            doc.error_message = None
            await db.commit()

    async def fake_stream_chat_completion(_provider, _messages, _user_content, system_prompt=None):
        assert system_prompt is not None
        assert "alpha policy and onboarding notes" in system_prompt
        yield 'data: {"type":"token","content":"基于文档，"}\n\n'
        yield 'data: {"type":"token","content":"答案是 alpha。"}\n\n'

    async def fake_generate_embeddings(_provider, _texts):
        return [None]

    monkeypatch.setattr(app_ctx.documents_api, "trigger_parse", fake_trigger_parse)
    monkeypatch.setattr(app_ctx.chat_api, "stream_chat_completion", fake_stream_chat_completion)
    monkeypatch.setattr(
        sys.modules["app.services.retrieval_service"],
        "generate_embeddings",
        fake_generate_embeddings,
    )

    with TestClient(app_ctx.main.app) as client:
        provider_resp = client.post(
            "/api/providers",
            json={
                "provider_type": "openai",
                "base_url": "https://api.openai.com",
                "model_name": "gpt-4o-mini",
                "api_key": "test-key",
                "temperature": 0.7,
                "max_tokens": 512,
                "timeout_seconds": 30,
                "is_default": False,
            },
        )
        assert provider_resp.status_code == 201

        upload_resp = client.post(
            "/api/documents",
            files={"file": ("sample.txt", b"alpha policy", "text/plain")},
        )
        assert upload_resp.status_code == 201
        doc_id = upload_resp.json()["id"]

        doc_resp = client.get(f"/api/documents/{doc_id}")
        assert doc_resp.status_code == 200
        assert doc_resp.json()["status"] == "可用"

        invalid_session = client.post("/api/sessions", json={"scope_type": "single"})
        assert invalid_session.status_code == 422

        session_resp = client.post(
            "/api/sessions",
            json={
                "scope_type": "single",
                "document_id": doc_id,
                "provider_id": provider_resp.json()["id"],
            },
        )
        assert session_resp.status_code == 201
        session = session_resp.json()
        session_id = session["id"]
        created_at = session["created_at"]
        assert session["provider_id"] == provider_resp.json()["id"]

        legacy_sessions = client.get("/api/chat/sessions")
        assert legacy_sessions.status_code == 200
        assert any(item["id"] == session_id for item in legacy_sessions.json())

        with client.stream(
            "POST",
            f"/api/sessions/{session_id}/messages",
            json={"content": "alpha 是什么？"},
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            body = "".join(response.iter_text())

        assert '"type":"token"' in body
        assert '"type":"sources"' in body or '"type": "sources"' in body
        assert '"type": "done"' in body or '"type":"done"' in body
        assert '"type":"error"' not in body

        match = re.search(r'"message_id"\s*:\s*"([^"]+)"', body)
        assert match is not None
        assert match.group(1)

        messages_resp = client.get(f"/api/sessions/{session_id}/messages")
        assert messages_resp.status_code == 200
        messages = messages_resp.json()
        assert [item["role"] for item in messages] == ["user", "assistant"]
        assert messages[1]["content"] == "基于文档，答案是 alpha。"
        assert messages[1]["sources"]["retrieval_method"] in {"keyword", "vector"}
        assert len(messages[1]["sources"]["chunks"]) == 1
        assert messages[1]["sources"]["chunks"][0]["document_name"] == "sample.txt"
        assert messages[1]["sources"]["chunks"][0]["content"] == "alpha policy and onboarding notes"

        sessions_resp = client.get("/api/sessions")
        assert sessions_resp.status_code == 200
        updated_session = next(item for item in sessions_resp.json() if item["id"] == session_id)
        assert updated_session["updated_at"] != created_at


def test_chat_uses_selected_session_provider(
    app_ctx: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
):
    selected_provider_id: str | None = None

    async def fake_stream_chat_completion(provider, _messages, _user_content, system_prompt=None):
        assert provider.id == selected_provider_id
        yield 'data: {"type":"token","content":"ok"}\n\n'

    monkeypatch.setattr(app_ctx.chat_api, "stream_chat_completion", fake_stream_chat_completion)

    with TestClient(app_ctx.main.app) as client:
        default_provider = client.post(
            "/api/providers",
            json={
                "provider_type": "openai",
                "base_url": "https://api.openai.com",
                "model_name": "gpt-default",
                "api_key": "test-key-1",
                "temperature": 0.7,
                "max_tokens": 512,
                "timeout_seconds": 30,
                "is_default": False,
            },
        )
        assert default_provider.status_code == 201

        secondary_provider = client.post(
            "/api/providers",
            json={
                "provider_type": "openai",
                "base_url": "https://api.openai.com",
                "model_name": "gpt-selected",
                "api_key": "test-key-2",
                "temperature": 0.5,
                "max_tokens": 256,
                "timeout_seconds": 20,
                "is_default": False,
            },
        )
        assert secondary_provider.status_code == 201
        selected_provider_id = secondary_provider.json()["id"]

        session_resp = client.post(
            "/api/sessions",
            json={"scope_type": "all", "provider_id": selected_provider_id},
        )
        assert session_resp.status_code == 201
        assert session_resp.json()["provider_id"] == selected_provider_id

        with client.stream(
            "POST",
            f"/api/sessions/{session_resp.json()['id']}/messages",
            json={"content": "hello"},
        ) as response:
            assert response.status_code == 200
            body = "".join(response.iter_text())

        assert '"type":"error"' not in body
        assert '"type":"done"' in body or '"type": "done"' in body


def test_chat_retrieval_prefers_selected_session_provider_embeddings(
    app_ctx: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
):
    embedding_provider_ids: list[str] = []

    async def fake_trigger_parse(doc_id: str, _file_path: str, _file_ext: str) -> None:
        async with app_ctx.database.async_session() as db:
            doc = (await db.execute(
                select(app_ctx.document_models.Document).where(
                    app_ctx.document_models.Document.id == doc_id
                )
            )).scalar_one()

            db.add(app_ctx.document_models.DocumentChunk(
                document_id=doc_id,
                chunk_index=0,
                content="provider specific embedded content",
                page_no=1,
                embedding=None,
            ))
            doc.status = "可用"
            doc.error_message = None
            await db.commit()

    async def fake_generate_embeddings(provider, texts):
        embedding_provider_ids.extend([provider.id] * len(texts))
        return [None] * len(texts)

    async def fake_stream_chat_completion(_provider, _messages, _user_content, system_prompt=None):
        yield 'data: {"type":"token","content":"ok"}\n\n'

    monkeypatch.setattr(app_ctx.documents_api, "trigger_parse", fake_trigger_parse)
    monkeypatch.setattr(app_ctx.chat_api, "stream_chat_completion", fake_stream_chat_completion)
    monkeypatch.setattr(
        sys.modules["app.services.retrieval_service"],
        "generate_embeddings",
        fake_generate_embeddings,
    )

    with TestClient(app_ctx.main.app) as client:
        default_provider = client.post(
            "/api/providers",
            json={
                "provider_type": "openai",
                "base_url": "https://api.openai.com",
                "model_name": "gpt-default",
                "api_key": "test-key-1",
                "embedding_model": "text-embedding-3-small",
                "enable_embedding": True,
                "temperature": 0.7,
                "max_tokens": 512,
                "timeout_seconds": 30,
                "is_default": False,
            },
        )
        assert default_provider.status_code == 201

        selected_provider = client.post(
            "/api/providers",
            json={
                "provider_type": "openai_compatible",
                "base_url": "http://localhost:11434",
                "model_name": "llama3.1",
                "api_key": "",
                "embedding_model": "nomic-embed-text",
                "enable_embedding": True,
                "temperature": 0.7,
                "max_tokens": 512,
                "timeout_seconds": 30,
                "is_default": False,
            },
        )
        assert selected_provider.status_code == 201
        selected_provider_id = selected_provider.json()["id"]

        upload_resp = client.post(
            "/api/documents",
            files={"file": ("sample.txt", b"provider content", "text/plain")},
        )
        assert upload_resp.status_code == 201
        doc_id = upload_resp.json()["id"]

        session_resp = client.post(
            "/api/sessions",
            json={
                "scope_type": "single",
                "provider_id": selected_provider_id,
                "document_id": doc_id,
            },
        )
        assert session_resp.status_code == 201

        with client.stream(
            "POST",
            f"/api/sessions/{session_resp.json()['id']}/messages",
            json={"content": "请回答"},
        ) as response:
            assert response.status_code == 200
            body = "".join(response.iter_text())

        assert '"type":"error"' not in body
        assert embedding_provider_ids
        assert set(embedding_provider_ids) == {selected_provider_id}


def test_provider_detail_returns_full_key_while_list_is_masked(
    app_ctx: SimpleNamespace,
):
    with TestClient(app_ctx.main.app) as client:
        created = client.post(
            "/api/providers",
            json={
                "provider_type": "openai",
                "base_url": "https://api.openai.com",
                "model_name": "gpt-4o",
                "api_key": "sk-secret-12345678",
                "embedding_model": "text-embedding-3-small",
                "enable_embedding": True,
                "temperature": 0.7,
                "max_tokens": 512,
                "timeout_seconds": 30,
                "is_default": False,
            },
        )
        assert created.status_code == 201
        provider_id = created.json()["id"]

        listed = client.get("/api/providers")
        assert listed.status_code == 200
        assert listed.json()[0]["api_key"] != "sk-secret-12345678"

        detail = client.get(f"/api/providers/{provider_id}")
        assert detail.status_code == 200
        assert detail.json()["api_key"] == "sk-secret-12345678"
        assert detail.json()["embedding_model"] == "text-embedding-3-small"
        assert detail.json()["enable_embedding"] is True


def test_provider_api_key_required_except_openai_compatible(
    app_ctx: SimpleNamespace,
):
    with TestClient(app_ctx.main.app) as client:
        openai_resp = client.post(
            "/api/providers",
            json={
                "provider_type": "openai",
                "base_url": "https://api.openai.com",
                "model_name": "gpt-4o",
                "api_key": "",
                "temperature": 0.7,
                "max_tokens": 512,
                "timeout_seconds": 30,
                "is_default": False,
            },
        )
        assert openai_resp.status_code == 422

        compatible_resp = client.post(
            "/api/providers",
            json={
                "provider_type": "openai_compatible",
                "base_url": "http://localhost:11434",
                "model_name": "llama3.1",
                "api_key": "",
                "embedding_model": "",
                "enable_embedding": False,
                "temperature": 0.7,
                "max_tokens": 512,
                "timeout_seconds": 30,
                "is_default": False,
            },
        )
        assert compatible_resp.status_code == 201

        invalid_embedding_resp = client.post(
            "/api/providers",
            json={
                "provider_type": "openai",
                "base_url": "https://api.openai.com",
                "model_name": "gpt-4o",
                "api_key": "sk-test",
                "embedding_model": "",
                "enable_embedding": True,
                "temperature": 0.7,
                "max_tokens": 512,
                "timeout_seconds": 30,
                "is_default": False,
            },
        )
        assert invalid_embedding_resp.status_code == 422


def test_regenerate_last_assistant_message_updates_existing_reply(
    app_ctx: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
):
    mode = "initial"

    async def fake_stream_chat_completion(_provider, _messages, _user_content, system_prompt=None):
        nonlocal mode
        if mode == "initial":
            yield 'data: {"type":"token","content":"旧答案"}\n\n'
            return

        assert system_prompt is not None
        assert "不满意" in system_prompt
        assert "旧答案" in system_prompt
        yield 'data: {"type":"token","content":"新答案"}\n\n'

    monkeypatch.setattr(app_ctx.chat_api, "stream_chat_completion", fake_stream_chat_completion)

    with TestClient(app_ctx.main.app) as client:
        provider_resp = client.post(
            "/api/providers",
            json={
                "provider_type": "openai",
                "base_url": "https://api.openai.com",
                "model_name": "gpt-4o-mini",
                "api_key": "test-key",
                "temperature": 0.7,
                "max_tokens": 512,
                "timeout_seconds": 30,
                "is_default": False,
            },
        )
        assert provider_resp.status_code == 201

        session_resp = client.post(
            "/api/sessions",
            json={"scope_type": "all", "provider_id": provider_resp.json()["id"]},
        )
        assert session_resp.status_code == 201
        session_id = session_resp.json()["id"]

        with client.stream(
            "POST",
            f"/api/sessions/{session_id}/messages",
            json={"content": "请回答"},
        ) as response:
            assert response.status_code == 200
            _ = "".join(response.iter_text())

        messages_resp = client.get(f"/api/sessions/{session_id}/messages")
        assert messages_resp.status_code == 200
        original_messages = messages_resp.json()
        assistant_id = original_messages[-1]["id"]
        assert original_messages[-1]["content"] == "旧答案"

        mode = "regen"
        with client.stream(
            "POST",
            f"/api/sessions/{session_id}/messages/{assistant_id}/regenerate",
            json={},
        ) as response:
            assert response.status_code == 200
            body = "".join(response.iter_text())

        assert '"type":"error"' not in body
        assert '"type":"done"' in body or '"type": "done"' in body

        updated_messages_resp = client.get(f"/api/sessions/{session_id}/messages")
        assert updated_messages_resp.status_code == 200
        updated_messages = updated_messages_resp.json()
        assert len(updated_messages) == 2
        assert updated_messages[-1]["id"] == assistant_id
        assert updated_messages[-1]["content"] == "新答案"


def test_single_scope_supports_multiple_documents(
    app_ctx: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
):
    created_docs: list[str] = []

    async def fake_trigger_parse(doc_id: str, _file_path: str, _file_ext: str) -> None:
        async with app_ctx.database.async_session() as db:
            doc = (await db.execute(
                select(app_ctx.document_models.Document).where(
                    app_ctx.document_models.Document.id == doc_id
                )
            )).scalar_one()

            db.add(app_ctx.document_models.DocumentChunk(
                document_id=doc_id,
                chunk_index=0,
                content=f"{doc.file_name.replace('.txt', '')} unique content",
                page_no=1,
                embedding=None,
            ))
            doc.status = "可用"
            doc.error_message = None
            await db.commit()

    async def fake_generate_embeddings(_provider, _texts):
        return [None]

    monkeypatch.setattr(app_ctx.documents_api, "trigger_parse", fake_trigger_parse)
    monkeypatch.setattr(
        sys.modules["app.services.retrieval_service"],
        "generate_embeddings",
        fake_generate_embeddings,
    )

    with TestClient(app_ctx.main.app) as client:
        provider_resp = client.post(
            "/api/providers",
            json={
                "provider_type": "openai",
                "base_url": "https://api.openai.com",
                "model_name": "gpt-4o-mini",
                "api_key": "test-key",
                "temperature": 0.7,
                "max_tokens": 512,
                "timeout_seconds": 30,
                "is_default": False,
            },
        )
        assert provider_resp.status_code == 201

        for name in ("a.txt", "b.txt", "c.txt"):
            upload_resp = client.post(
                "/api/documents",
                files={"file": (name, f"{name} body".encode(), "text/plain")},
            )
            assert upload_resp.status_code == 201
            doc_id = upload_resp.json()["id"]
            created_docs.append(doc_id)

        session_resp = client.post(
            "/api/sessions",
            json={
                "scope_type": "single",
                "document_ids": created_docs[:2],
                "provider_id": provider_resp.json()["id"],
            },
        )
        assert session_resp.status_code == 201
        session = session_resp.json()
        assert session["document_ids"] == created_docs[:2]
        assert session["document_id"] == created_docs[0]

        retrieval_resp = client.post(
            "/api/retrieval/chunks",
            json={
                "query": "unique",
                "scope_type": "single",
                "document_ids": created_docs[:2],
                "top_k": 10,
            },
        )
        assert retrieval_resp.status_code == 200
        returned_doc_ids = {item["document_id"] for item in retrieval_resp.json()}
        assert returned_doc_ids == set(created_docs[:2])
