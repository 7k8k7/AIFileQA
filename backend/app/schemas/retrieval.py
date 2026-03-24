from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.chat import ScopeType


class RetrievalQuery(BaseModel):
    query: str = Field(min_length=1)
    scope_type: ScopeType = "all"
    provider_id: str | None = None
    document_id: str | None = None
    document_ids: list[str] | None = None
    top_k: int = Field(default=settings.retrieval_top_k, ge=1, le=20)


class RetrievalChunkOut(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    chunk_index: int
    content: str
    page_no: int | None = None
    section_label: str | None = None
    score: float | None = None
