from datetime import datetime
from typing import Literal
from pydantic import BaseModel, model_validator

ProviderType = Literal["openai", "claude", "openai_compatible"]


class ProviderCreate(BaseModel):
    provider_type: ProviderType
    base_url: str
    model_name: str
    api_key: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout_seconds: int = 30
    is_default: bool = False

    @model_validator(mode="after")
    def validate_api_key(self) -> "ProviderCreate":
        if self.provider_type != "openai_compatible" and not self.api_key.strip():
            raise ValueError("当前供应商必须提供 API Key")
        return self


class ProviderUpdate(BaseModel):
    provider_type: ProviderType | None = None
    base_url: str | None = None
    model_name: str | None = None
    api_key: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    timeout_seconds: int | None = None

    @model_validator(mode="after")
    def validate_api_key(self) -> "ProviderUpdate":
        if self.provider_type != "openai_compatible" and self.api_key is not None and not self.api_key.strip():
            raise ValueError("当前供应商必须提供 API Key")
        return self


class ProviderOut(BaseModel):
    id: str
    provider_type: ProviderType
    base_url: str
    model_name: str
    api_key: str  # masked before returning
    temperature: float
    max_tokens: int
    timeout_seconds: int
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProviderDetailOut(BaseModel):
    id: str
    provider_type: ProviderType
    base_url: str
    model_name: str
    api_key: str
    temperature: float
    max_tokens: int
    timeout_seconds: int
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


def mask_api_key(key: str) -> str:
    """Return masked API key: first 3 + **** + last 4, or full mask if too short."""
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:3]}****{key[-4:]}"
