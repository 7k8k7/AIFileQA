"""Chat API endpoints — sessions, messages, SSE streaming."""

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, async_session
from app.schemas.chat import SessionCreate, SessionOut, MessageOut, MessageSend, message_to_out
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
from app.services.retrieval_service import build_rag_prompt

router = APIRouter(tags=["chat"])


# ── Sessions ──

@router.get("/api/chat/sessions", response_model=list[SessionOut])
@router.get("/api/sessions", response_model=list[SessionOut], include_in_schema=False)
async def get_sessions(db: AsyncSession = Depends(get_db)):
    return [SessionOut.model_validate(s) for s in await list_sessions(db)]


@router.post("/api/chat/sessions", response_model=SessionOut, status_code=201)
@router.post("/api/sessions", response_model=SessionOut, status_code=201, include_in_schema=False)
async def add_session(
    data: SessionCreate,
    db: AsyncSession = Depends(get_db),
):
    session = await create_session(db, data)
    return SessionOut.model_validate(session)


@router.delete("/api/chat/sessions/{session_id}", status_code=204)
@router.delete("/api/sessions/{session_id}", status_code=204, include_in_schema=False)
async def remove_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    deleted = await delete_session(db, session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="会话不存在")


# ── Messages ──

@router.get("/api/chat/sessions/{session_id}/messages", response_model=list[MessageOut])
@router.get("/api/sessions/{session_id}/messages", response_model=list[MessageOut], include_in_schema=False)
async def get_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    session = await get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    msgs = await list_messages(db, session_id)
    return [message_to_out(m) for m in msgs]


@router.post("/api/chat/sessions/{session_id}/messages")
@router.post("/api/sessions/{session_id}/messages", include_in_schema=False)
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

    # Persist user message immediately so the frontend can refresh and render it.
    user_message = await save_user_message(db, session_id, body.content)
    await db.commit()

    # Build RAG system prompt with document context
    rag_result = await build_rag_prompt(
        db,
        body.content,
        scope_type=session.scope_type,
        document_id=session.document_id,
    )

    # Fetch conversation history after the user message is committed.
    history = await list_messages(db, session_id)
    # Exclude the user message we just added (it's already in history now)
    prior = history[:-1]

    async def event_generator():
        # Emit sources event before token stream
        sources_event = {
            "type": "sources",
            "retrieval_method": rag_result.retrieval_method,
            "chunks": [
                {
                    "document_name": c.document_name,
                    "chunk_index": c.chunk_index,
                    "content": c.content[:200],
                    "page_no": c.page_no,
                    "score": c.score,
                }
                for c in rag_result.chunks
            ],
        }
        yield f"data: {json.dumps(sources_event, ensure_ascii=False)}\n\n"

        full_content = ""
        try:
            async for sse_line in stream_chat_completion(
                provider, prior, body.content, system_prompt=rag_result.system_prompt
            ):
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
                assistant_msg = await save_assistant_message(
                    persist_db,
                    session_id,
                    full_content,
                    sources={
                        "retrieval_method": rag_result.retrieval_method,
                        "chunks": sources_event["chunks"],
                    },
                )
                await persist_db.commit()
                done_event = f"data: {json.dumps({'type': 'done', 'message_id': assistant_msg.id}, ensure_ascii=False)}\n\n"
                yield done_event
            except Exception as e:
                error_event = f"data: {json.dumps({'type': 'error', 'content': f'保存助手消息失败：{str(e)[:200]}'}, ensure_ascii=False)}\n\n"
                yield error_event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-User-Message-Id": user_message.id,
        },
    )
