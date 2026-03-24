"""Document API endpoints."""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.schemas.common import PaginatedResponse
from app.schemas.document import DocumentOut
from app.services.document_service import (
    list_documents,
    get_document,
    create_document,
    delete_document,
    save_upload_file,
)

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("", response_model=PaginatedResponse[DocumentOut])
async def get_documents(
    keyword: str = Query("", description="文件名关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await list_documents(db, keyword=keyword, page=page, page_size=page_size)


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document_by_id(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
):
    doc = await get_document(db, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return DocumentOut.model_validate(doc)


@router.post("", response_model=DocumentOut, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    # Validate size
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"文件大小超过 {settings.max_upload_size_mb}MB 限制")

    # Validate extension
    name = file.filename or "unknown"
    ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    allowed = {".pdf", ".docx", ".doc", ".txt", ".md", ".markdown"}
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}")

    # Save file to disk
    dest = save_upload_file(name, content)

    # Create DB record
    doc = await create_document(
        db,
        file_name=name,
        file_ext=ext,
        file_size=len(content),
        storage_path=str(dest),
    )
    return DocumentOut.model_validate(doc)


@router.delete("/{doc_id}", status_code=204)
async def remove_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
):
    deleted = await delete_document(db, doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="文档不存在")
