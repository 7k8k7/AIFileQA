from datetime import datetime
from typing import Literal
from pydantic import BaseModel

DocumentStatus = Literal["上传成功", "解析中", "可用", "解析失败"]


class DocumentOut(BaseModel):
    id: str
    file_name: str
    file_ext: str
    file_size: int
    status: DocumentStatus
    error_message: str | None = None
    uploaded_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
