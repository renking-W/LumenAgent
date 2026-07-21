"""文件上传相关 DTO。"""

from __future__ import annotations

from pydantic import BaseModel


class UploadResponse(BaseModel):
    """POST /v1/upload 响应体。"""

    filename: str
    url: str
    path: str
    content_type: str
    size: int
