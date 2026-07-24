"""认证路由：登录、读取当前用户及认证状态。"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, status

from lumen_agent.api.dependency import (
    AuthContext,
    get_current_auth_context,
    get_current_user,
    get_settings,
)
from lumen_agent.api.schemas.auth_dtos import (
    AuthStatusResponse,
    AuthUserResponse,
    LoginRequest,
    LoginResponse,
)
from lumen_agent.application.service.auth.auth_service import (
    create_access_token,
    verify_password,
)
from lumen_agent.config import Settings, resolve_db_path
from lumen_agent.infrastructure.data_base.sqlite_user import SqliteUserRepository

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _public_user(user: dict) -> AuthUserResponse:
    return AuthUserResponse(**{k: v for k, v in user.items() if k != "password_hash"})


def _jwt_settings(settings: Settings) -> tuple[str, int, int]:
    """读取并校验由后端控制的 JWT 有效期与刷新窗口。"""
    secret = str(settings.get("AUTH_JWT_SECRET", "")).strip()
    try:
        expire_hours = int(settings.get("AUTH_JWT_EXPIRE_HOURS", 24))
        refresh_before_hours = int(
            settings.get("AUTH_JWT_REFRESH_BEFORE_HOURS", 8)
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT 时间配置不是有效整数",
        ) from exc

    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="认证服务尚未配置 AUTH_JWT_SECRET",
        )
    if expire_hours <= 0 or not 0 < refresh_before_hours < expire_hours:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT 有效期必须大于刷新窗口，且二者都必须为正数",
        )
    return secret, expire_hours, refresh_before_hours


@router.get("/status", response_model=AuthStatusResponse)
async def get_auth_status(
    settings: Settings = Depends(get_settings),
) -> AuthStatusResponse:
    """供前端启动时判断是否需要进入登录页。"""
    return AuthStatusResponse(auth_enabled=bool(settings.get("AUTH_ENABLED", False)))


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    """校验用户名密码并签发无状态访问令牌。"""
    secret, expire_hours, refresh_before_hours = _jwt_settings(settings)

    repo = SqliteUserRepository(resolve_db_path(settings))
    user = await repo.get_auth_record(body.username)
    if user is None or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    if not user["enabled"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用",
        )

    token, expires_at, refresh_at = create_access_token(
        user["id"],
        secret=secret,
        expire_hours=expire_hours,
        refresh_before_hours=refresh_before_hours,
    )
    await repo.update_last_login(user["id"])
    refreshed = await repo.get_by_id(user["id"])
    if refreshed is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    _logger.info("用户登录成功: user_id=%s username=%s", user["id"], user["username"])
    return LoginResponse(
        access_token=token,
        expires_at=expires_at.isoformat(),
        refresh_at=refresh_at.isoformat(),
        user=_public_user(refreshed),
    )



@router.post("/refresh", response_model=LoginResponse)
async def refresh_access_token(
    context: AuthContext = Depends(get_current_auth_context),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    """进入后台规定的刷新窗口后，使用当前 JWT 换取新 JWT。"""
    secret, expire_hours, refresh_before_hours = _jwt_settings(settings)
    try:
        remaining_seconds = int(context.payload["exp"]) - int(time.time())
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token 中缺少有效的过期时间",
        ) from exc

    if remaining_seconds > refresh_before_hours * 3600:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Access token 尚未进入刷新窗口",
        )

    token, expires_at, refresh_at = create_access_token(
        context.user["id"],
        secret=secret,
        expire_hours=expire_hours,
        refresh_before_hours=refresh_before_hours,
    )
    return LoginResponse(
        access_token=token,
        expires_at=expires_at.isoformat(),
        refresh_at=refresh_at.isoformat(),
        user=_public_user(context.user),
    )


@router.get("/me", response_model=AuthUserResponse)
async def get_me(
    current_user: dict = Depends(get_current_user),
) -> AuthUserResponse:
    """返回令牌对应的当前用户，权限字段以数据库实时状态为准。"""
    return _public_user(current_user)
