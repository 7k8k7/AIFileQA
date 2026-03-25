"""Chat session / message CRUD service."""

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatSession, ChatMessage
from app.models.document import Document
from app.models.provider import ProviderConfig
from app.schemas.chat import SessionCreate


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def list_sessions(db: AsyncSession) -> list[ChatSession]:
    rows = (
        await db.execute(
            select(ChatSession).order_by(ChatSession.updated_at.desc())
        )
    ).scalars().all()
    return list(rows)


async def get_session(db: AsyncSession, session_id: str) -> ChatSession | None:
    return (
        await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    ).scalar_one_or_none()


async def create_session(db: AsyncSession, data: SessionCreate) -> ChatSession:
    provider_id = data.provider_id
    if provider_id:
        provider = (
            await db.execute(select(ProviderConfig).where(ProviderConfig.id == provider_id))
        ).scalar_one_or_none()
        if not provider:
            raise ValueError("供应商不存在")
    else:
        default_provider = (
            await db.execute(
                select(ProviderConfig).where(ProviderConfig.is_default == True)  # noqa: E712
            )
        ).scalar_one_or_none()
        if not default_provider:
            raise ValueError("请先在设置中配置模型供应商")
        provider_id = default_provider.id

    document_ids = data.document_ids or ([data.document_id] if data.document_id else [])
    if data.scope_type == "single":
        if not document_ids:
            raise ValueError("请选择至少一个文档")
        rows = (
            await db.execute(
                select(Document.id).where(
                    Document.id.in_(document_ids),
                    Document.status == "可用",
                )
            )
        ).scalars().all()
        valid_id_set = set(rows)
        if len(valid_id_set) != len(set(document_ids)):
            raise ValueError("存在不可用或不存在的文档")
        document_ids = [doc_id for doc_id in document_ids if doc_id in valid_id_set]
    else:
        document_ids = []

    session = ChatSession(
        scope_type=data.scope_type,
        provider_id=provider_id,
        document_id=document_ids[0] if document_ids else None,
        document_ids_json=json.dumps(document_ids, ensure_ascii=False) if document_ids else None,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


async def rename_session(db: AsyncSession, session_id: str, title: str) -> ChatSession | None:
    session = await get_session(db, session_id)
    if not session:
        return None
    session.title = title.strip()[:255]
    session.updated_at = _utcnow()
    await db.flush()
    await db.refresh(session)
    return session


async def delete_session(db: AsyncSession, session_id: str) -> bool:
    session = await get_session(db, session_id)
    if not session:
        return False
    await db.delete(session)
    await db.flush()
    return True


async def list_messages(db: AsyncSession, session_id: str) -> list[ChatMessage]:
    rows = (
        await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        )
    ).scalars().all()
    return list(rows)


async def get_message(db: AsyncSession, message_id: str) -> ChatMessage | None:
    return (
        await db.execute(select(ChatMessage).where(ChatMessage.id == message_id))
    ).scalar_one_or_none()


async def save_user_message(db: AsyncSession, session_id: str, content: str) -> ChatMessage:
    """Persist user message and update session title on first message."""
    msg = ChatMessage(session_id=session_id, role="user", content=content)
    db.add(msg)

    # Update title from first user message
    session = await get_session(db, session_id)
    if session:
        if session.title == "新对话":
            session.title = content[:50]
        session.updated_at = _utcnow()

    await db.flush()
    await db.refresh(msg)
    return msg


async def save_assistant_message(
    db: AsyncSession,
    session_id: str,
    content: str,
    sources: dict | None = None,
) -> ChatMessage:
    """Persist the completed assistant response."""
    msg = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=content,
        sources_json=json.dumps(sources, ensure_ascii=False) if sources else None,
    )
    db.add(msg)

    session = await get_session(db, session_id)
    if session:
        session.updated_at = _utcnow()

    await db.flush()
    await db.refresh(msg)
    return msg


async def update_assistant_message(
    db: AsyncSession,
    message_id: str,
    content: str,
    sources: dict | None = None,
) -> ChatMessage | None:
    msg = await get_message(db, message_id)
    if not msg or msg.role != "assistant":
        return None

    msg.content = content
    msg.sources_json = json.dumps(sources, ensure_ascii=False) if sources else None

    session = await get_session(db, msg.session_id)
    if session:
        session.updated_at = _utcnow()

    await db.flush()
    await db.refresh(msg)
    return msg
