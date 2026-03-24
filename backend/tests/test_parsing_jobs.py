from __future__ import annotations

import asyncio

from sqlalchemy import select


async def _create_document_record(app_ctx, tmp_path, *, file_name: str = "sample.txt", content: str = "hello world"):
    file_path = tmp_path / file_name
    file_path.write_text(content, encoding="utf-8")

    async with app_ctx.database.async_session() as db:
        document = app_ctx.document_models.Document(
            file_name=file_name,
            file_ext=".txt",
            file_size=len(content.encode("utf-8")),
            storage_path=str(file_path),
            status="上传中",
        )
        db.add(document)
        await db.flush()
        document_id = document.id
        await db.commit()

    return document_id, file_path


async def _prepare_schema(app_ctx) -> None:
    async with app_ctx.database.engine.begin() as conn:
        await conn.run_sync(app_ctx.database.Base.metadata.create_all)


def test_trigger_parse_creates_job_and_worker_completes(app_ctx, tmp_path, monkeypatch):
    async def fake_generate_embeddings(_provider, _texts):
        return [None]

    monkeypatch.setattr(app_ctx.parsing_task, "generate_embeddings", fake_generate_embeddings)

    asyncio.run(_prepare_schema(app_ctx))
    document_id, file_path = asyncio.run(_create_document_record(app_ctx, tmp_path))
    asyncio.run(app_ctx.parsing_task.trigger_parse(document_id, str(file_path), ".txt"))
    worked = asyncio.run(app_ctx.parsing_task.run_parse_worker_once())

    assert worked is True

    async def _load_state():
        async with app_ctx.database.async_session() as db:
            document = (
                await db.execute(
                    select(app_ctx.document_models.Document).where(
                        app_ctx.document_models.Document.id == document_id
                    )
                )
            ).scalar_one()
            job = (
                await db.execute(
                    select(app_ctx.job_models.Job).where(
                        app_ctx.job_models.Job.document_id == document_id
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
            return document, job, chunks

    document, job, chunks = asyncio.run(_load_state())
    assert document.status == "可用"
    assert document.error_message is None
    assert job.status == "succeeded"
    assert len(chunks) >= 1


def test_failed_job_retries_then_marks_document_failed(app_ctx, tmp_path, monkeypatch):
    async def always_fail(*_args, **_kwargs):
        raise ValueError("模拟解析失败")

    monkeypatch.setattr(app_ctx.parsing_task, "_run_parse_pipeline", always_fail)

    asyncio.run(_prepare_schema(app_ctx))
    document_id, file_path = asyncio.run(_create_document_record(app_ctx, tmp_path))
    asyncio.run(app_ctx.parsing_task.trigger_parse(document_id, str(file_path), ".txt"))

    for _ in range(app_ctx.parsing_task.settings.job_max_retries):
        asyncio.run(app_ctx.parsing_task.run_parse_worker_once())

    async def _load_state():
        async with app_ctx.database.async_session() as db:
            document = (
                await db.execute(
                    select(app_ctx.document_models.Document).where(
                        app_ctx.document_models.Document.id == document_id
                    )
                )
            ).scalar_one()
            job = (
                await db.execute(
                    select(app_ctx.job_models.Job).where(
                        app_ctx.job_models.Job.document_id == document_id
                    )
                )
            ).scalar_one()
            return document, job

    document, job = asyncio.run(_load_state())
    assert job.status == "failed"
    assert job.retry_count == app_ctx.parsing_task.settings.job_max_retries
    assert "模拟解析失败" in (job.error_message or "")
    assert document.status == "失败"
    assert "模拟解析失败" in (document.error_message or "")


def test_timeout_job_is_reset_to_pending_for_retry(app_ctx, tmp_path, monkeypatch):
    async def slow_pipeline(*_args, **_kwargs):
        await asyncio.sleep(0.05)

    monkeypatch.setattr(app_ctx.parsing_task.settings, "job_stale_seconds", 0.01)
    monkeypatch.setattr(app_ctx.parsing_task, "_run_parse_pipeline", slow_pipeline)

    asyncio.run(_prepare_schema(app_ctx))
    document_id, file_path = asyncio.run(_create_document_record(app_ctx, tmp_path))
    asyncio.run(app_ctx.parsing_task.trigger_parse(document_id, str(file_path), ".txt"))
    worked = asyncio.run(app_ctx.parsing_task.run_parse_worker_once())

    assert worked is True

    async def _load_state():
        async with app_ctx.database.async_session() as db:
            document = (
                await db.execute(
                    select(app_ctx.document_models.Document).where(
                        app_ctx.document_models.Document.id == document_id
                    )
                )
            ).scalar_one()
            job = (
                await db.execute(
                    select(app_ctx.job_models.Job).where(
                        app_ctx.job_models.Job.document_id == document_id
                    )
                )
            ).scalar_one()
            return document, job

    document, job = asyncio.run(_load_state())
    assert job.status == "pending"
    assert job.retry_count == 1
    assert "自动重置并重试" in (job.error_message or "")
    assert document.status == "解析中"
    assert "自动重置并重试" in (document.error_message or "")
