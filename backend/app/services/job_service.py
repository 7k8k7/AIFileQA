from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.job import Job


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ClaimedJob:
    id: str
    document_id: str
    file_path: str
    file_ext: str
    retry_count: int
    max_retries: int


@dataclass
class ResetJobResult:
    document_id: str
    status: str
    message: str


async def create_parse_job(
    db: AsyncSession,
    *,
    document_id: str,
    file_path: str,
    file_ext: str,
) -> Job:
    existing = (
        await db.execute(
            select(Job).where(
                Job.document_id == document_id,
                Job.job_type == "parse_document",
                Job.status.in_(("pending", "running")),
            )
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    job = Job(
        job_type="parse_document",
        document_id=document_id,
        file_path=file_path,
        file_ext=file_ext,
        status="pending",
        retry_count=0,
        max_retries=settings.job_max_retries,
    )
    db.add(job)
    await db.flush()
    return job


async def claim_next_parse_job(db: AsyncSession) -> ClaimedJob | None:
    job = (
        await db.execute(
            select(Job)
            .where(Job.job_type == "parse_document", Job.status == "pending")
            .order_by(Job.created_at)
            .limit(1)
        )
    ).scalar_one_or_none()
    if not job:
        return None

    job.status = "running"
    job.started_at = _utcnow()
    job.finished_at = None
    job.error_message = None
    await db.flush()

    return ClaimedJob(
        id=job.id,
        document_id=job.document_id,
        file_path=job.file_path,
        file_ext=job.file_ext,
        retry_count=job.retry_count,
        max_retries=job.max_retries,
    )


async def reset_stalled_jobs(db: AsyncSession) -> list[ResetJobResult]:
    cutoff = _utcnow() - timedelta(seconds=settings.job_stale_seconds)
    jobs = (
        await db.execute(
            select(Job).where(
                Job.job_type == "parse_document",
                Job.status == "running",
                Job.started_at.is_not(None),
                Job.started_at < cutoff,
            )
        )
    ).scalars().all()

    results: list[ResetJobResult] = []
    for job in jobs:
        message = f"运行超过 {settings.job_stale_seconds // 60} 分钟，已自动重置并重试"
        if job.retry_count + 1 >= job.max_retries:
            job.retry_count += 1
            job.status = "failed"
            job.finished_at = _utcnow()
            job.error_message = message
            results.append(ResetJobResult(document_id=job.document_id, status="failed", message=message))
            continue

        job.retry_count += 1
        job.status = "pending"
        job.started_at = None
        job.finished_at = None
        job.error_message = message
        results.append(ResetJobResult(document_id=job.document_id, status="pending", message=message))

    await db.flush()
    return results


async def complete_job(db: AsyncSession, job_id: str) -> None:
    job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one_or_none()
    if not job:
        return
    job.status = "succeeded"
    job.finished_at = _utcnow()
    job.error_message = None
    await db.flush()


async def retry_or_fail_job(db: AsyncSession, job_id: str, message: str) -> str | None:
    job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one_or_none()
    if not job:
        return None

    if job.retry_count + 1 >= job.max_retries:
        job.retry_count += 1
        job.status = "failed"
        job.finished_at = _utcnow()
        job.error_message = message
        await db.flush()
        return "failed"

    job.retry_count += 1
    job.status = "pending"
    job.started_at = None
    job.finished_at = None
    job.error_message = message
    await db.flush()
    return "pending"
