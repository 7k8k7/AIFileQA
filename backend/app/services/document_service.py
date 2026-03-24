"""Document CRUD + file upload service."""
from pathlib import Path

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document
from app.schemas.document import DocumentOut
from app.schemas.common import PaginatedResponse


async def _promote_ready_documents(db: AsyncSession) -> None:
    """Backfill legacy uploads to `可用` until the async parser exists."""
    rows = (
        await db.execute(
            select(Document).where(
                Document.status == "上传成功",
                Document.error_message.is_(None),
            )
        )
    ).scalars().all()
    for row in rows:
        row.status = "可用"
    if rows:
        await db.flush()


async def list_documents(
    db: AsyncSession,
    *,
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse[DocumentOut]:
    """List documents with optional keyword filter + pagination."""
    await _promote_ready_documents(db)

    base = select(Document)
    if keyword:
        base = base.where(Document.file_name.ilike(f"%{keyword}%"))

    # total count
    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # page items
    q = (
        base
        .order_by(Document.uploaded_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(q)).scalars().all()

    return PaginatedResponse[DocumentOut](
        items=[DocumentOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_document(db: AsyncSession, doc_id: str) -> Document | None:
    await _promote_ready_documents(db)
    return (await db.execute(select(Document).where(Document.id == doc_id))).scalar_one_or_none()


async def create_document(
    db: AsyncSession,
    *,
    file_name: str,
    file_ext: str,
    file_size: int,
    storage_path: str,
) -> Document:
    """Insert a new document record.

    The current backend does not run an async parser yet, so a successful upload
    is made available immediately for chat usage.
    """
    doc = Document(
        file_name=file_name,
        file_ext=file_ext,
        file_size=file_size,
        storage_path=storage_path,
        status="可用",
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    return doc


async def delete_document(db: AsyncSession, doc_id: str) -> bool:
    """Delete document record + its file on disk. Returns False if not found."""
    doc = await get_document(db, doc_id)
    if not doc:
        return False

    # Remove file from disk
    file_path = Path(doc.storage_path)
    if file_path.exists():
        file_path.unlink(missing_ok=True)

    await db.delete(doc)
    await db.flush()
    return True


def save_upload_file(file_name: str, content: bytes) -> Path:
    """Save raw bytes to uploads dir, return the Path."""
    dest = settings.upload_path / file_name
    # Avoid overwrite — append suffix if exists
    counter = 1
    while dest.exists():
        stem = Path(file_name).stem
        suffix = Path(file_name).suffix
        dest = settings.upload_path / f"{stem}_{counter}{suffix}"
        counter += 1
    dest.write_bytes(content)
    return dest
