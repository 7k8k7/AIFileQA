import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, Integer, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.security import decrypt_provider_secret, encrypt_provider_secret


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProviderConfig(Base):
    __tablename__ = "provider_configs"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=lambda: f"p-{uuid.uuid4().hex[:12]}"
    )
    provider_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # openai | claude | openai_compatible
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    _api_key_encrypted: Mapped[str] = mapped_column("api_key", String(512), nullable=False, default="")
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    enable_embedding: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=4096)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_test_success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_test_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    @property
    def api_key(self) -> str:
        return decrypt_provider_secret(self._api_key_encrypted)

    @api_key.setter
    def api_key(self, value: str) -> None:
        self._api_key_encrypted = encrypt_provider_secret(value or "")
