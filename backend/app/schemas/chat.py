from datetime import datetime
from typing import Literal
from pydantic import BaseModel, model_validator

ScopeType = Literal["all", "single"]
MessageRole = Literal["user", "assistant"]


class SessionCreate(BaseModel):
    scope_type: ScopeType = "all"
    document_id: str | None = None

    @model_validator(mode="after")
    def validate_single_scope(self) -> "SessionCreate":
        if self.scope_type == "single" and not self.document_id:
            raise ValueError("single 范围必须提供 document_id")
        return self


class SessionOut(BaseModel):
    id: str
    title: str
    scope_type: ScopeType
    document_id: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: str
    session_id: str
    role: MessageRole
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageSend(BaseModel):
    content: str
