from datetime import datetime
from typing import Literal
from pydantic import BaseModel

ScopeType = Literal["all", "single"]
MessageRole = Literal["user", "assistant"]


class SessionCreate(BaseModel):
    scope_type: ScopeType = "all"
    document_id: str | None = None


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
