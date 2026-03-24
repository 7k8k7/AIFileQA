"""Chat API endpoints — sessions, messages, SSE streaming."""

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, async_session
from app.schemas.chat import SessionCreate, SessionOut, MessageOut, MessageSend
from app.services.chat_service import (
    list_sessions,
    get_session,
    create_session,
    delete_session,
    list_messages,
    save_user_message,
    save_assistant_message,
)
from app.services.llm_service import get_default_provider, stream_chat_completion

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ── Sessions ──

@router.get("/sessions", response_model=list[SessionOut])
async def get_sessions(db: AsyncSession = Depends(get_db)):
    return [SessionOut.model_validate(s) for s in await list_sessions(db)]


@router.post("/sessions", response_model=SessionOut, status_code=201)
async def add_session(
    data: SessionCreate,
    db: AsyncSession = Depends(get_db),
):
    session = await create_session(db, data)
    return SessionOut.model_validate(session)


@router.delete("/sessions/{session_id}", status_code=204)
async def remove_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    deleted = await delete_session(db, session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="会话不存在")


# ── Messages ──

@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
async def get_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    session = await get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    msgs = await list_messages(db, session_id)
    return [MessageOut.model_validate(m) for m in msgs]


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    body: MessageSend,
    db: AsyncSession = Depends(get_db),
):
    """
    Send a user message and stream the LLM response via SSE.

    Returns `text/event-stream` with events:
      data: {"type":"token","content":"..."}
      data: {"type":"done","message_id":"..."}
    """
    # Validate session exists
    session = await get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # Get default provider
    provider = await get_default_provider(db)
    if not provider:
        raise HTTPException(status_code=400, detail="请先在设置中配置模型供应商")

    # Persist user message
    await save_user_message(db, session_id, body.content)

    # Fetch conversation history
    history = await list_messages(db, session_id)
    # Exclude the user message we just added (it's already in history now)
    # We pass history (excluding last) + current content separately
    prior = history[:-1]  # all messages before the one we just saved

    async def event_generator():
        full_content = ""
        try:
            async for sse_line in stream_chat_completion(provider, prior, body.content):
                # Extract content for persistence
                if sse_line.startswith("data: "):
                    try:
                        obj = json.loads(sse_line[6:])
                        if obj.get("type") == "token":
                            full_content += obj.get("content", "")
                    except json.JSONDecodeError:
                        pass
                yield sse_line
        except Exception as e:
            error_event = f"data: {json.dumps({'type': 'error', 'content': str(e)[:300]}, ensure_ascii=False)}\n\n"
            yield error_event
            return

        # Persist assistant message after streaming is done
        async with async_session() as persist_db:
            try:
                assistant_msg = await save_assistant_message(persist_db, session_id, full_content)
                await persist_db.commit()
                done_event = f"data: {json.dumps({'type': 'done', 'message_id': assistant_msg.id}, ensure_ascii=False)}\n\n"
                yield done_event
            except Exception:
                yield f"data: {json.dumps({'type': 'done', 'message_id': ''})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
