import json
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, model_validator

from app.models.chat import ChatMessage

ScopeType = Literal["all", "single"]
MessageRole = Literal["user", "assistant"]


class SessionCreate(BaseModel):
    scope_type: ScopeType = "all"
    provider_id: str | None = None
    document_id: str | None = None
    document_ids: list[str] | None = None

    @model_validator(mode="after")
    def validate_single_scope(self) -> "SessionCreate":
        if self.scope_type == "single" and not (self.document_ids or self.document_id):
            raise ValueError("single 范围必须提供至少一个 document_id")
        return self


class SessionUpdate(BaseModel):
    title: str


class SessionOut(BaseModel):
    id: str
    title: str
    scope_type: ScopeType
    provider_id: str | None = None
    document_id: str | None = None
    document_ids: list[str] = []
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


class MessageRegenerate(BaseModel):
    feedback: str | None = None


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


def session_to_out(session) -> SessionOut:
    document_ids: list[str] = []
    if getattr(session, "document_ids_json", None):
        document_ids = json.loads(session.document_ids_json)
    elif getattr(session, "document_id", None):
        document_ids = [session.document_id]

    return SessionOut(
        id=session.id,
        title=session.title,
        scope_type=session.scope_type,
        provider_id=session.provider_id,
        document_id=session.document_id,
        document_ids=document_ids,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )
