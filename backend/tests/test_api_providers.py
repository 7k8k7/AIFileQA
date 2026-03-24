from __future__ import annotations

import asyncio

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


def test_create_provider(app_ctx):
    with TestClient(app_ctx.main.app) as client:
        response = client.post("/api/providers", json=_provider_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["provider_type"] == "openai"
    assert body["model_name"] == "gpt-4o-mini"
    assert body["embedding_model"] == "text-embedding-3-small"
    assert body["enable_embedding"] is True


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

        set_default_resp = client.post(f"/api/providers/{second.json()['id']}/set-default")
        listed = client.get("/api/providers")

    assert set_default_resp.status_code == 204
    providers = {item["id"]: item for item in listed.json()}
    assert providers[first.json()["id"]]["is_default"] is False
    assert providers[second.json()["id"]]["is_default"] is True


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
