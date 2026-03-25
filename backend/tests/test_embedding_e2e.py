from __future__ import annotations

import asyncio
import importlib
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import select


async def _prepare_schema(app_ctx) -> None:
    async with app_ctx.database.engine.begin() as conn:
        await conn.run_sync(app_ctx.database.Base.metadata.create_all)


async def _mark_provider_as_default(app_ctx, provider_id: str) -> None:
    async with app_ctx.database.async_session() as db:
        provider = (
            await db.execute(
                select(app_ctx.provider_models.ProviderConfig).where(
                    app_ctx.provider_models.ProviderConfig.id == provider_id
                )
            )
        ).scalar_one()
        provider.is_default = True
        provider.last_test_success = True
        provider.last_test_message = "测试环境默认启用"
        db.add(provider)
        await db.commit()


async def _load_document_and_chunks(app_ctx, document_id: str):
    async with app_ctx.database.async_session() as db:
        document = (
            await db.execute(
                select(app_ctx.document_models.Document).where(
                    app_ctx.document_models.Document.id == document_id
                )
            )
        ).scalar_one()
        chunks = (
            await db.execute(
                select(app_ctx.document_models.DocumentChunk).where(
                    app_ctx.document_models.DocumentChunk.document_id == document_id
                )
            )
        ).scalars().all()
        return document, chunks


def test_embedding_pipeline_indexes_chunks_and_chat_uses_vector_retrieval(
    app_ctx,
    monkeypatch,
):
    asyncio.run(_prepare_schema(app_ctx))
    vector_store = importlib.import_module("app.services.vector_store_service")
    retrieval_service = importlib.import_module("app.services.retrieval_service")
    vector_store.reset_vector_store_cache()

    embedding_calls: list[tuple[str, list[str]]] = []

    def fake_parse_document(_file_path: str, file_ext: str):
        assert file_ext == ".txt"
        return [
            SimpleNamespace(
                index=0,
                content="vector only evidence lives here",
                page_no=1,
                section_label=None,
            )
        ]

    async def fake_generate_embeddings(provider, texts: list[str]):
        embedding_calls.append((provider.id, list(texts)))
        result: list[list[float] | None] = []
        for text in texts:
            if text == "semantic query":
                result.append([1.0, 0.0, 0.0])
            elif "vector only evidence" in text:
                result.append([1.0, 0.0, 0.0])
            else:
                result.append([0.0, 1.0, 0.0])
        return result

    async def fake_trigger_parse(doc_id: str, file_path: str, file_ext: str) -> None:
        await app_ctx.parsing_task._run_parse_pipeline(doc_id, file_path, file_ext)

    async def fake_stream_chat_completion(_provider, _messages, _user_content, system_prompt=None):
        assert system_prompt is not None
        assert "vector only evidence lives here" in system_prompt
        yield 'data: {"type":"token","content":"命中向量检索"}\n\n'

    monkeypatch.setattr(app_ctx.parsing_task, "_get_executor", lambda: None)
    monkeypatch.setattr(app_ctx.parsing_task, "parse_document", fake_parse_document)
    monkeypatch.setattr(app_ctx.parsing_task, "generate_embeddings", fake_generate_embeddings)
    monkeypatch.setattr(retrieval_service, "generate_embeddings", fake_generate_embeddings)
    monkeypatch.setattr(app_ctx.documents_api, "trigger_parse", fake_trigger_parse)
    monkeypatch.setattr(app_ctx.chat_api, "stream_chat_completion", fake_stream_chat_completion)

    with TestClient(app_ctx.main.app) as client:
        provider_resp = client.post(
            "/api/providers",
            json={
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
            },
        )
        assert provider_resp.status_code == 201
        provider_id = provider_resp.json()["id"]
        asyncio.run(_mark_provider_as_default(app_ctx, provider_id))

        upload_resp = client.post(
            "/api/documents",
            files={"file": ("vector.txt", b"ignored original body", "text/plain")},
        )
        assert upload_resp.status_code == 201
        document_id = upload_resp.json()["id"]

        session_resp = client.post(
            "/api/sessions",
            json={
                "scope_type": "single",
                "provider_id": provider_id,
                "document_id": document_id,
            },
        )
        assert session_resp.status_code == 201
        session_id = session_resp.json()["id"]

        with client.stream(
            "POST",
            f"/api/sessions/{session_id}/messages",
            json={"content": "semantic query"},
        ) as response:
            assert response.status_code == 200
            body = "".join(response.iter_text())

        messages_resp = client.get(f"/api/sessions/{session_id}/messages")
        assert messages_resp.status_code == 200
        messages = messages_resp.json()

    document, chunks = asyncio.run(_load_document_and_chunks(app_ctx, document_id))
    assert document.status == "可用"
    assert len(chunks) == 1
    assert chunks[0].embedding is not None

    missing_chunk_ids = vector_store.find_missing_chunk_ids(
        provider_id,
        "text-embedding-3-small",
        [chunks[0].id],
    )
    assert missing_chunk_ids == []

    vector_hits = vector_store.query_document_chunks(
        [1.0, 0.0, 0.0],
        top_k=3,
        provider_id=provider_id,
        embedding_model="text-embedding-3-small",
        document_ids=[document_id],
    )
    assert len(vector_hits) == 1
    assert vector_hits[0].chunk_id == chunks[0].id

    assert any(texts == ["vector only evidence lives here"] for _, texts in embedding_calls)
    assert any(texts == ["semantic query"] for _, texts in embedding_calls)

    assert '"retrieval_method":"vector"' in body or '"retrieval_method": "vector"' in body
    assert '"type":"done"' in body or '"type": "done"' in body
    assert '"type":"error"' not in body

    assert [item["role"] for item in messages] == ["user", "assistant"]
    assert messages[1]["content"] == "命中向量检索"
    assert messages[1]["sources"]["retrieval_method"] == "vector"
    assert len(messages[1]["sources"]["chunks"]) == 1
    assert messages[1]["sources"]["chunks"][0]["document_name"] == "vector.txt"
    assert messages[1]["sources"]["chunks"][0]["content"] == "vector only evidence lives here"
