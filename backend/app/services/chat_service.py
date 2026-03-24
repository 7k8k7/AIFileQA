"""Chat session / message CRUD service."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatSession, ChatMessage
from app.schemas.chat import SessionCreate


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
    session = ChatSession(
        scope_type=data.scope_type,
        document_id=data.document_id,
    )
    db.add(session)
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


async def save_user_message(db: AsyncSession, session_id: str, content: str) -> ChatMessage:
    """Persist user message and update session title on first message."""
    msg = ChatMessage(session_id=session_id, role="user", content=content)
    db.add(msg)

    # Update title from first user message
    session = await get_session(db, session_id)
    if session and session.title == "新对话":
        session.title = content[:50]

    await db.flush()
    await db.refresh(msg)
    return msg


async def save_assistant_message(db: AsyncSession, session_id: str, content: str) -> ChatMessage:
    """Persist the completed assistant response."""
    msg = ChatMessage(session_id=session_id, role="assistant", content=content)
    db.add(msg)
    await db.flush()
    await db.refresh(msg)
    return msg
