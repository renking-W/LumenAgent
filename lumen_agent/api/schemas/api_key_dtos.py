"""API Key 管理相关的 Pydantic 请求/响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ApiKeyCreateRequest(BaseModel):
    """``POST /v1/api-keys`` 请求体。"""

    name: str = Field(default="", max_length=100, description="可选标签")


class ApiKeyResponse(BaseModel):
    """API Key 元数据（不含原始 Key，不含 hash）。"""

    id: str
    name: str
    enabled: bool
    created_at: str
    updated_at: str


class ApiKeyCreatedResponse(ApiKeyResponse):
    """创建成功后返回（含原始 Key，仅此一次）。"""

    key: str


class ApiKeyListResponse(BaseModel):
    """``GET /v1/api-keys`` 响应。"""

    total: int
    keys: list[ApiKeyResponse]


class ApiKeyToggleRequest(BaseModel):
    """``PATCH /v1/api-keys/{id}`` 请求体。"""

    enabled: bool = Field(..., description="true=启用, false=禁用")
