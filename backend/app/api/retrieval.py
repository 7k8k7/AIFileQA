"""Retrieval API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.retrieval import RetrievalChunkOut, RetrievalQuery
from app.services.retrieval_service import retrieve_chunks

router = APIRouter(prefix="/api/retrieval", tags=["retrieval"])


@router.post("/chunks", response_model=list[RetrievalChunkOut])
async def search_chunks(
    data: RetrievalQuery,
    db: AsyncSession = Depends(get_db),
):
    if data.scope_type == "single" and not data.document_id:
        raise HTTPException(status_code=400, detail="single 范围必须提供 document_id")

    rows, _ = await retrieve_chunks(
        db,
        data.query,
        scope_type=data.scope_type,
        document_id=data.document_id,
        top_k=data.top_k,
    )
    return [
        RetrievalChunkOut(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            document_name=row.document_name,
            chunk_index=row.chunk_index,
            content=row.content,
            page_no=row.page_no,
            section_label=row.section_label,
            score=row.score,
        )
        for row in rows
    ]
