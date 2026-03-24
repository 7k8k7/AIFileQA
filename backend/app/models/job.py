import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=lambda: f"j-{uuid.uuid4().hex[:12]}"
    )
    job_type: Mapped[str] = mapped_column(String(64), nullable=False, default="parse_document")
    document_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_ext: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending"
    )  # pending | running | succeeded | failed
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
