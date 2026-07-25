"""管理员用户管理接口 DTO。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class AdminUserItem(BaseModel):
    """管理员后台中的用户列表项。"""

    id: str
    username: str
    role: Literal["user", "admin"]
    daily_round_limit: int
    unlimited: bool
    enabled: bool
    created_at: str
    updated_at: str
    last_login_at: str | None = None
    used_rounds: int = 0
    session_count: int = 0


class AdminUserListResponse(BaseModel):
    """用户分页结果及后台概览统计。"""

    total: int
    total_users: int
    enabled_users: int
    unlimited_users: int
    used_rounds_today: int
    usage_date: str
    users: list[AdminUserItem]


class CreateAdminUserRequest(BaseModel):
    """管理员创建账号的请求体。"""

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=256)
    role: Literal["user", "admin"] = "user"
    daily_round_limit: int = Field(default=3, ge=0, le=10000)
    unlimited: bool = False


class UpdateAdminUserRequest(BaseModel):
    """管理员更新账号权限和额度的请求体。"""

    role: Literal["user", "admin"] | None = None
    daily_round_limit: int | None = Field(default=None, ge=0, le=10000)
    unlimited: bool | None = None
    enabled: bool | None = None

    @model_validator(mode="after")
    def validate_changes(self) -> "UpdateAdminUserRequest":
        """至少提供一个待修改字段。"""
        if not self.model_fields_set:
            raise ValueError("至少提供一个待修改字段")
        return self


class UpdateAdminPasswordRequest(BaseModel):
    """管理员重置用户密码的请求体。"""

    password: str = Field(min_length=8, max_length=256)


class AdminUserSessionItem(BaseModel):
    """用户拥有的会话摘要。"""

    id: str
    title: str = ""
    kind: int = 0
    created_at: str
    updated_at: str


class AdminUserSessionListResponse(BaseModel):
    """指定用户的会话分页结果。"""

    total: int
    sessions: list[AdminUserSessionItem]