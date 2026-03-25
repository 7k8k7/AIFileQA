from __future__ import annotations

import asyncio
import importlib

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
        await db.commit()


def test_create_provider(app_ctx):
    with TestClient(app_ctx.main.app) as client:
        response = client.post("/api/providers", json=_provider_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["provider_type"] == "openai"
    assert body["model_name"] == "gpt-4o-mini"
    assert body["embedding_model"] == "text-embedding-3-small"
    assert body["enable_embedding"] is True
    assert body["is_default"] is False
    assert body["last_test_success"] is False


def test_list_masks_key_and_detail_returns_full_key(app_ctx):
    with TestClient(app_ctx.main.app) as client:
        created = client.post("/api/providers", json=_provider_payload(api_key="sk-secret-123456"))
        assert created.status_code == 201
        provider_id = created.json()["id"]

        listed = client.get("/api/providers")
        detail = client.get(f"/api/providers/{provider_id}")

    assert listed.status_code == 200
    assert listed.json()[0]["api_key"] != "sk-secret-123456"
    assert detail.status_code == 200
    assert detail.json()["api_key"] == "sk-secret-123456"

    async def _load_raw_provider():
        async with app_ctx.database.async_session() as db:
            provider = (
                await db.execute(
                    select(app_ctx.provider_models.ProviderConfig).where(
                        app_ctx.provider_models.ProviderConfig.id == provider_id
                    )
                )
            ).scalar_one()
            return provider._api_key_encrypted

    raw_value = asyncio.run(_load_raw_provider())
    assert raw_value != "sk-secret-123456"
    assert raw_value.startswith("enc:")


def test_update_preserves_key_when_empty(app_ctx):
    with TestClient(app_ctx.main.app) as client:
        created = client.post("/api/providers", json=_provider_payload(api_key="sk-original"))
        assert created.status_code == 201
        provider_id = created.json()["id"]

        updated = client.put(
            f"/api/providers/{provider_id}",
            json={
                "model_name": "gpt-4.1-mini",
                "api_key": "",
                "embedding_model": "text-embedding-3-small",
                "enable_embedding": True,
            },
        )
        detail = client.get(f"/api/providers/{provider_id}")

    assert updated.status_code == 200
    assert updated.json()["model_name"] == "gpt-4.1-mini"
    assert detail.status_code == 200
    assert detail.json()["api_key"] == "sk-original"


def test_set_default_provider(app_ctx):
    with TestClient(app_ctx.main.app) as client:
        first = client.post("/api/providers", json=_provider_payload(model_name="first"))
        second = client.post("/api/providers", json=_provider_payload(model_name="second", api_key="sk-two"))
        assert first.status_code == 201
        assert second.status_code == 201

    asyncio.run(_mark_provider_verified(app_ctx, second.json()["id"]))

    with TestClient(app_ctx.main.app) as client:
        set_default_resp = client.post(f"/api/providers/{second.json()['id']}/set-default")
        listed = client.get("/api/providers")

    assert set_default_resp.status_code == 204
    providers = {item["id"]: item for item in listed.json()}
    assert providers[first.json()["id"]]["is_default"] is False
    assert providers[second.json()["id"]]["is_default"] is True


def test_unverified_provider_cannot_be_default(app_ctx):
    with TestClient(app_ctx.main.app) as client:
        created = client.post("/api/providers", json=_provider_payload())
        assert created.status_code == 201

        set_default_resp = client.post(f"/api/providers/{created.json()['id']}/set-default")

    assert set_default_resp.status_code == 400
    assert "请先测试连接成功" in set_default_resp.json()["detail"]


def test_test_connection_returns_updated_provider_snapshot(app_ctx, monkeypatch):
    provider_service = importlib.import_module("app.services.provider_service")
    captured_request = {}

    class _FakeResponse:
        status_code = 200
        text = "ok"
        headers = {}

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, headers=None, json=None):
            captured_request["url"] = url
            captured_request["headers"] = headers
            captured_request["json"] = json
            return _FakeResponse()

    monkeypatch.setattr(provider_service.httpx, "AsyncClient", _FakeAsyncClient)

    with TestClient(app_ctx.main.app) as client:
        created = client.post("/api/providers", json=_provider_payload())
        assert created.status_code == 201

        tested = client.post(f"/api/providers/{created.json()['id']}/test")

    assert tested.status_code == 200
    body = tested.json()
    assert body["success"] is True
    assert body["provider"]["id"] == created.json()["id"]
    assert body["provider"]["last_test_success"] is True
    assert body["provider"]["last_test_message"] == "连接成功"
    assert captured_request["url"].endswith("/v1/chat/completions")
    assert captured_request["json"]["model"] == "gpt-4o-mini"
    assert captured_request["json"]["messages"] == [
        {"role": "user", "content": 'Reply with exactly "ok".'}
    ]
    assert captured_request["json"]["max_completion_tokens"] == 32
    assert "max_tokens" not in captured_request["json"]


def test_test_connection_openai_compatible_keeps_max_tokens(app_ctx, monkeypatch):
    provider_service = importlib.import_module("app.services.provider_service")
    captured_request = {}

    class _FakeResponse:
        status_code = 200
        text = "ok"
        headers = {}

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, headers=None, json=None):
            captured_request["url"] = url
            captured_request["headers"] = headers
            captured_request["json"] = json
            return _FakeResponse()

    monkeypatch.setattr(provider_service.httpx, "AsyncClient", _FakeAsyncClient)

    with TestClient(app_ctx.main.app) as client:
        created = client.post(
            "/api/providers",
            json=_provider_payload(
                provider_type="openai_compatible",
                base_url="http://localhost:11434",
                api_key="",
                model_name="llama3.1",
            ),
        )
        assert created.status_code == 201

        tested = client.post(f"/api/providers/{created.json()['id']}/test")

    assert tested.status_code == 200
    assert captured_request["json"]["messages"] == [
        {"role": "user", "content": 'Reply with exactly "ok".'}
    ]
    assert captured_request["json"]["max_tokens"] == 32
    assert "max_completion_tokens" not in captured_request["json"]


def test_test_connection_retries_without_temperature_for_openai_compatible(app_ctx, monkeypatch):
    provider_service = importlib.import_module("app.services.provider_service")
    captured_requests = []

    class _FakeResponse:
        def __init__(self, status_code, text, headers=None):
            self.status_code = status_code
            self.text = text
            self.headers = headers or {}

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            self.calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, headers=None, json=None):
            captured_requests.append({"url": url, "headers": headers, "json": json})
            self.calls += 1
            if self.calls == 1:
                return _FakeResponse(
                    400,
                    '{"error":{"message":"Unsupported parameter: temperature","param":"temperature","type":"invalid_request_error"}}',
                    {"x-request-id": "req_retry_temp"},
                )
            return _FakeResponse(200, "ok")

    monkeypatch.setattr(provider_service.httpx, "AsyncClient", _FakeAsyncClient)

    with TestClient(app_ctx.main.app) as client:
        created = client.post(
            "/api/providers",
            json=_provider_payload(
                provider_type="openai_compatible",
                base_url="http://localhost:11434",
                api_key="",
                model_name="llama3.1",
            ),
        )
        assert created.status_code == 201

        tested = client.post(f"/api/providers/{created.json()['id']}/test")

    assert tested.status_code == 200
    body = tested.json()
    assert body["success"] is True
    assert len(captured_requests) == 2
    assert captured_requests[0]["json"]["temperature"] == 0.7
    assert "temperature" not in captured_requests[1]["json"]


def test_test_connection_returns_raw_error_and_request_id(app_ctx, monkeypatch):
    provider_service = importlib.import_module("app.services.provider_service")

    class _FakeResponse:
        status_code = 400
        text = '{"error":{"message":"Unsupported parameter: temperature","type":"invalid_request_error"}}'
        headers = {"x-request-id": "req_test_123"}

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, *args, **kwargs):
            return _FakeResponse()

    monkeypatch.setattr(provider_service.httpx, "AsyncClient", _FakeAsyncClient)

    with TestClient(app_ctx.main.app) as client:
        created = client.post("/api/providers", json=_provider_payload(model_name="gpt-5.4"))
        assert created.status_code == 201

        tested = client.post(f"/api/providers/{created.json()['id']}/test")

    assert tested.status_code == 200
    body = tested.json()
    assert body["success"] is False
    assert "Unsupported parameter: temperature" in body["message"]
    assert "x-request-id: req_test_123" in body["message"]


def test_delete_provider(app_ctx):
    with TestClient(app_ctx.main.app) as client:
        first = client.post("/api/providers", json=_provider_payload(model_name="first"))
        second = client.post("/api/providers", json=_provider_payload(model_name="second", api_key="sk-two"))
        assert first.status_code == 201
        assert second.status_code == 201

        deleted = client.delete(f"/api/providers/{second.json()['id']}")
        listed = client.get("/api/providers")

    assert deleted.status_code == 204
    ids = {item["id"] for item in listed.json()}
    assert second.json()["id"] not in ids


def test_delete_provider_allows_provider_used_by_session(app_ctx):
    with TestClient(app_ctx.main.app) as client:
        provider = client.post("/api/providers", json=_provider_payload())
        assert provider.status_code == 201

    asyncio.run(_mark_provider_verified(app_ctx, provider.json()["id"]))

    with TestClient(app_ctx.main.app) as client:
        session = client.post(
            "/api/sessions",
            json={"scope_type": "all", "provider_id": provider.json()["id"]},
        )
        assert session.status_code == 201

        deleted = client.delete(f"/api/providers/{provider.json()['id']}")
        listed = client.get("/api/providers")

    assert deleted.status_code == 204
    ids = {item["id"] for item in listed.json()}
    assert provider.json()["id"] not in ids
