"""配置编辑接口的请求/响应 DTO。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ConfigItemResponse(BaseModel):
    """单个配置项。"""

    key: str
    value: Any
    category: str  # "basic" | "advanced"


class ConfigListResponse(BaseModel):
    """配置列表响应。"""

    basic: list[ConfigItemResponse]
    advanced: list[ConfigItemResponse]


class UpdateConfigRequest(BaseModel):
    """更新配置请求。"""

    key: str = Field(..., min_length=1, description="配置键名（大小写不敏感）")
    value: str = Field(..., description="配置值")


class UpdateConfigResponse(BaseModel):
    """更新配置响应。"""

    status: str = "ok"
    key: str
    value: str
    source: str = ".env"
    note: str
