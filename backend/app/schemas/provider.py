from datetime import datetime
from typing import Literal
from pydantic import BaseModel, model_validator

ProviderType = Literal["openai", "claude", "openai_compatible"]


class ProviderCreate(BaseModel):
    provider_type: ProviderType
    base_url: str
    model_name: str
    api_key: str = ""
    embedding_model: str = ""
    enable_embedding: bool = False
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout_seconds: int = 30
    is_default: bool = False

    @model_validator(mode="after")
    def validate_api_key(self) -> "ProviderCreate":
        validate_provider_values(
            provider_type=self.provider_type,
            api_key=self.api_key,
            enable_embedding=self.enable_embedding,
            embedding_model=self.embedding_model,
        )
        return self


class ProviderUpdate(BaseModel):
    provider_type: ProviderType | None = None
    base_url: str | None = None
    model_name: str | None = None
    api_key: str | None = None
    embedding_model: str | None = None
    enable_embedding: bool | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    timeout_seconds: int | None = None


class ProviderOut(BaseModel):
    id: str
    provider_type: ProviderType
    base_url: str
    model_name: str
    api_key: str  # masked before returning
    embedding_model: str
    enable_embedding: bool
    temperature: float
    max_tokens: int
    timeout_seconds: int
    is_default: bool
    last_test_success: bool
    last_test_message: str | None = None
    last_test_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProviderDetailOut(BaseModel):
    id: str
    provider_type: ProviderType
    base_url: str
    model_name: str
    api_key: str
    embedding_model: str
    enable_embedding: bool
    temperature: float
    max_tokens: int
    timeout_seconds: int
    is_default: bool
    last_test_success: bool
    last_test_message: str | None = None
    last_test_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProviderTestOut(BaseModel):
    success: bool
    message: str
    provider: ProviderOut


def mask_api_key(key: str) -> str:
    """Return masked API key: first 3 + **** + last 4, or full mask if too short."""
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:3]}****{key[-4:]}"


def validate_provider_values(
    *,
    provider_type: ProviderType,
    api_key: str,
    enable_embedding: bool,
    embedding_model: str,
) -> None:
    if provider_type != "openai_compatible" and not api_key.strip():
        raise ValueError("当前供应商必须提供 API Key")

    if enable_embedding and provider_type != "claude" and not embedding_model.strip():
        raise ValueError("启用 Embedding 时必须填写 Embedding Model")
