"""Chat API endpoints — sessions, messages, SSE streaming."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, async_session
from app.schemas.chat import (
    SessionCreate,
    SessionUpdate,
    SessionOut,
    MessageOut,
    MessageSend,
    MessageRegenerate,
    message_to_out,
    session_to_out,
)
from app.services.chat_service import (
    list_sessions,
    get_session,
    create_session,
    rename_session,
    delete_session,
    list_messages,
    get_message,
    save_user_message,
    save_assistant_message,
    update_assistant_message,
)
from app.services.llm_service import get_default_provider, stream_chat_completion
from app.services.provider_service import get_provider
from app.services.retrieval_service import build_rag_prompt
from app.core.observability import clip_text, summarize_chunks, summarize_provider

router = APIRouter(tags=["chat"])
REGENERATE_FEEDBACK = "用户对你刚刚的回答不满意。请重新回答同一个问题，明确修正问题，不要只是换个说法重复原答案。"
logger = logging.getLogger(__name__)


# ── Sessions ──

@router.get("/api/chat/sessions", response_model=list[SessionOut])
@router.get("/api/sessions", response_model=list[SessionOut], include_in_schema=False)
async def get_sessions(db: AsyncSession = Depends(get_db)):
    return [session_to_out(s) for s in await list_sessions(db)]


@router.post("/api/chat/sessions", response_model=SessionOut, status_code=201)
@router.post("/api/sessions", response_model=SessionOut, status_code=201, include_in_schema=False)
async def add_session(
    data: SessionCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        session = await create_session(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return session_to_out(session)


@router.patch("/api/chat/sessions/{session_id}", response_model=SessionOut)
@router.patch("/api/sessions/{session_id}", response_model=SessionOut, include_in_schema=False)
async def update_session(
    session_id: str,
    data: SessionUpdate,
    db: AsyncSession = Depends(get_db),
):
    session = await rename_session(db, session_id, data.title)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session_to_out(session)


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
    provider = None
    if session.provider_id:
        provider = await get_provider(db, session.provider_id)
    if not provider:
        provider = await get_default_provider(db)
    if not provider:
        raise HTTPException(status_code=400, detail="请先在设置中配置模型供应商")
    logger.info(
        "Chat send started: session_id=%s scope=%s provider=%s question=%s",
        session_id,
        session.scope_type,
        summarize_provider(provider),
        clip_text(body.content),
    )

    # Persist user message immediately so the frontend can refresh and render it.
    user_message = await save_user_message(db, session_id, body.content)
    await db.commit()

    # Build RAG system prompt with document context
    rag_result = await build_rag_prompt(
        db,
        body.content,
        provider=provider,
        scope_type=session.scope_type,
        document_id=session.document_id,
        document_ids=json.loads(session.document_ids_json) if session.document_ids_json else None,
    )
    logger.info(
        "Chat retrieval prepared: session_id=%s method=%s %s",
        session_id,
        rag_result.retrieval_method,
        summarize_chunks(rag_result.chunks),
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
            logger.warning(
                "Chat stream failed: session_id=%s provider=%s error=%s",
                session_id,
                summarize_provider(provider),
                str(e)[:300],
            )
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
                logger.info(
                    "Chat stream completed: session_id=%s assistant_message_id=%s chars=%d",
                    session_id,
                    assistant_msg.id,
                    len(full_content),
                )
                done_event = f"data: {json.dumps({'type': 'done', 'message_id': assistant_msg.id}, ensure_ascii=False)}\n\n"
                yield done_event
            except Exception as e:
                logger.exception(
                    "Chat assistant message persistence failed: session_id=%s error=%s",
                    session_id,
                    str(e)[:200],
                )
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


@router.post("/api/chat/sessions/{session_id}/messages/{message_id}/regenerate")
@router.post("/api/sessions/{session_id}/messages/{message_id}/regenerate", include_in_schema=False)
async def regenerate_message(
    session_id: str,
    message_id: str,
    body: MessageRegenerate,
    db: AsyncSession = Depends(get_db),
):
    session = await get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    target_message = await get_message(db, message_id)
    if not target_message or target_message.session_id != session_id:
        raise HTTPException(status_code=404, detail="消息不存在")
    if target_message.role != "assistant":
        raise HTTPException(status_code=400, detail="只能重新生成助手消息")

    messages = await list_messages(db, session_id)
    if not messages or messages[-1].id != message_id:
        raise HTTPException(status_code=400, detail="暂时只支持重新生成最后一条助手回复")

    assistant_index = next((i for i, msg in enumerate(messages) if msg.id == message_id), -1)
    if assistant_index <= 0 or messages[assistant_index - 1].role != "user":
        raise HTTPException(status_code=400, detail="未找到对应的用户提问")

    user_message = messages[assistant_index - 1]
    prior = messages[: assistant_index - 1]

    provider = None
    if session.provider_id:
        provider = await get_provider(db, session.provider_id)
    if not provider:
        provider = await get_default_provider(db)
    if not provider:
        raise HTTPException(status_code=400, detail="请先在设置中配置模型供应商")
    logger.info(
        "Chat regenerate started: session_id=%s message_id=%s provider=%s feedback=%s",
        session_id,
        message_id,
        summarize_provider(provider),
        clip_text(body.feedback or REGENERATE_FEEDBACK),
    )

    rag_result = await build_rag_prompt(
        db,
        user_message.content,
        provider=provider,
        scope_type=session.scope_type,
        document_id=session.document_id,
        document_ids=json.loads(session.document_ids_json) if session.document_ids_json else None,
    )
    feedback = body.feedback.strip() if body.feedback else REGENERATE_FEEDBACK
    regenerate_prompt = (
        f"{rag_result.system_prompt}\n\n"
        f"用户反馈：{feedback}\n"
        f"上一条回答：{target_message.content}\n"
        "请基于同一个问题重新给出更有针对性、更具体的回答，避免重复上一条回答的结构和表述。"
    )

    async def event_generator():
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
                provider,
                prior,
                user_message.content,
                system_prompt=regenerate_prompt,
            ):
                if sse_line.startswith("data: "):
                    try:
                        obj = json.loads(sse_line[6:])
                        if obj.get("type") == "token":
                            full_content += obj.get("content", "")
                    except json.JSONDecodeError:
                        pass
                yield sse_line
        except Exception as e:
            logger.warning(
                "Chat regenerate stream failed: session_id=%s message_id=%s error=%s",
                session_id,
                message_id,
                str(e)[:300],
            )
            error_event = f"data: {json.dumps({'type': 'error', 'content': str(e)[:300]}, ensure_ascii=False)}\n\n"
            yield error_event
            return

        async with async_session() as persist_db:
            try:
                updated_msg = await update_assistant_message(
                    persist_db,
                    message_id,
                    full_content,
                    sources={
                        "retrieval_method": rag_result.retrieval_method,
                        "chunks": sources_event["chunks"],
                    },
                )
                if not updated_msg:
                    raise ValueError("原助手消息不存在")
                await persist_db.commit()
                logger.info(
                    "Chat regenerate completed: session_id=%s message_id=%s chars=%d method=%s",
                    session_id,
                    updated_msg.id,
                    len(full_content),
                    rag_result.retrieval_method,
                )
                done_event = f"data: {json.dumps({'type': 'done', 'message_id': updated_msg.id}, ensure_ascii=False)}\n\n"
                yield done_event
            except Exception as e:
                logger.exception(
                    "Chat regenerate persistence failed: session_id=%s message_id=%s error=%s",
                    session_id,
                    message_id,
                    str(e)[:200],
                )
                error_event = f"data: {json.dumps({'type': 'error', 'content': f'更新助手消息失败：{str(e)[:200]}'}, ensure_ascii=False)}\n\n"
                yield error_event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Regenerated-Message-Id": message_id,
        },
    )
