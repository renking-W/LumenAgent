"""用户登录与身份查询 DTO。"""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class AuthUserResponse(BaseModel):
    id: str
    username: str
    role: str
    daily_round_limit: int
    unlimited: bool
    enabled: bool
    created_at: str
    last_login_at: str | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: str
    refresh_at: str
    user: AuthUserResponse


class AuthStatusResponse(BaseModel):
    auth_enabled: bool
