import json
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, model_validator

from app.models.chat import ChatMessage

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


class SourceChunkOut(BaseModel):
    document_name: str
    chunk_index: int
    content: str
    page_no: int | None = None
    score: float | None = None


class MessageSourcesOut(BaseModel):
    retrieval_method: str
    chunks: list[SourceChunkOut]


class MessageOut(BaseModel):
    id: str
    session_id: str
    role: MessageRole
    content: str
    sources: MessageSourcesOut | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageSend(BaseModel):
    content: str


def message_to_out(message: ChatMessage) -> MessageOut:
    sources = None
    if message.sources_json:
        sources = MessageSourcesOut.model_validate(json.loads(message.sources_json))

    return MessageOut(
        id=message.id,
        session_id=message.session_id,
        role=message.role,
        content=message.content,
        sources=sources,
        created_at=message.created_at,
    )
