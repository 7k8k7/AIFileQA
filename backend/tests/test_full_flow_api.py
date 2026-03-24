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
        assert provider_resp.json()["is_default"] is True

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
            json={"scope_type": "single", "document_id": doc_id},
        )
        assert session_resp.status_code == 201
        session = session_resp.json()
        session_id = session["id"]
        created_at = session["created_at"]

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
