from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select


def test_upload_valid_file(app_ctx, monkeypatch):
    async def fake_trigger_parse(_doc_id: str, _file_path: str, _file_ext: str) -> None:
        return None

    monkeypatch.setattr(app_ctx.documents_api, "trigger_parse", fake_trigger_parse)

    with TestClient(app_ctx.main.app) as client:
        response = client.post(
            "/api/documents",
            files={"file": ("sample.txt", b"hello docqa", "text/plain")},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["file_name"] == "sample.txt"
    assert body["file_ext"] == ".txt"
    assert body["status"] == "上传中"


def test_upload_oversized_file(app_ctx, monkeypatch):
    monkeypatch.setattr(app_ctx.documents_api.settings, "max_upload_size_mb", 0)

    with TestClient(app_ctx.main.app) as client:
        response = client.post(
            "/api/documents",
            files={"file": ("big.txt", b"1", "text/plain")},
        )

    assert response.status_code == 413


def test_upload_unsupported_extension(app_ctx):
    with TestClient(app_ctx.main.app) as client:
        response = client.post(
            "/api/documents",
            files={"file": ("sample.exe", b"nope", "application/octet-stream")},
        )

    assert response.status_code == 400
    assert "不支持的文件类型" in response.json()["detail"]


def test_list_documents_pagination(app_ctx, monkeypatch):
    async def fake_trigger_parse(_doc_id: str, _file_path: str, _file_ext: str) -> None:
        return None

    monkeypatch.setattr(app_ctx.documents_api, "trigger_parse", fake_trigger_parse)

    with TestClient(app_ctx.main.app) as client:
        for idx in range(2):
            response = client.post(
                "/api/documents",
                files={"file": (f"sample-{idx}.txt", f"body-{idx}".encode(), "text/plain")},
            )
            assert response.status_code == 201

        page1 = client.get("/api/documents?page=1&page_size=1")
        page2 = client.get("/api/documents?page=2&page_size=1")

    assert page1.status_code == 200
    assert page2.status_code == 200
    assert page1.json()["total"] == 2
    assert len(page1.json()["items"]) == 1
    assert len(page2.json()["items"]) == 1


def test_delete_document_removes_record_and_file(app_ctx, monkeypatch):
    async def fake_trigger_parse(_doc_id: str, _file_path: str, _file_ext: str) -> None:
        return None

    monkeypatch.setattr(app_ctx.documents_api, "trigger_parse", fake_trigger_parse)

    with TestClient(app_ctx.main.app) as client:
        create_resp = client.post(
            "/api/documents",
            files={"file": ("sample.txt", b"delete me", "text/plain")},
        )
        assert create_resp.status_code == 201
        doc_id = create_resp.json()["id"]

        async def _fetch_storage_path() -> str:
            async with app_ctx.database.async_session() as db:
                doc = (
                    await db.execute(
                        select(app_ctx.document_models.Document).where(
                            app_ctx.document_models.Document.id == doc_id
                        )
                    )
                ).scalar_one()
                return doc.storage_path

        import asyncio

        storage_path = asyncio.run(_fetch_storage_path())
        assert Path(storage_path).exists()

        delete_resp = client.delete(f"/api/documents/{doc_id}")
        assert delete_resp.status_code == 204

        detail_resp = client.get(f"/api/documents/{doc_id}")

    assert detail_resp.status_code == 404
    assert not Path(storage_path).exists()


def test_legacy_document_status_is_normalized_on_read(app_ctx, monkeypatch):
    async def fake_trigger_parse(_doc_id: str, _file_path: str, _file_ext: str) -> None:
        return None

    monkeypatch.setattr(app_ctx.documents_api, "trigger_parse", fake_trigger_parse)

    with TestClient(app_ctx.main.app) as client:
        create_resp = client.post(
            "/api/documents",
            files={"file": ("legacy.txt", b"legacy", "text/plain")},
        )
        assert create_resp.status_code == 201
        doc_id = create_resp.json()["id"]

    async def _set_legacy_status() -> None:
        async with app_ctx.database.async_session() as db:
            doc = (
                await db.execute(
                    select(app_ctx.document_models.Document).where(
                        app_ctx.document_models.Document.id == doc_id
                    )
                )
            ).scalar_one()
            doc.status = "解析失败"
            doc.error_message = "旧错误"
            await db.commit()

    import asyncio

    asyncio.run(_set_legacy_status())

    with TestClient(app_ctx.main.app) as client:
        detail_resp = client.get(f"/api/documents/{doc_id}")
        list_resp = client.get("/api/documents")

    assert detail_resp.status_code == 200
    assert detail_resp.json()["status"] == "失败"
    assert detail_resp.json()["error_message"] == "旧错误"
    assert list_resp.status_code == 200
    assert list_resp.json()["items"][0]["status"] == "失败"
