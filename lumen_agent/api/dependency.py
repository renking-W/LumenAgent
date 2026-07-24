"""FastAPI `Depends` 工厂：集中装配模型适配器、仓储与认证依赖。"""

from dataclasses import dataclass
import hashlib
import logging

import jwt
from fastapi import Depends, Header, HTTPException, Request, status

from lumen_agent.config import (
    Settings,
    get_settings,
    resolve_cors_origins,
    resolve_db_path,
)
from lumen_agent.infrastructure.data_base.sqlite_api_key import (
    SqliteApiKeyRepository,
)
from lumen_agent.infrastructure.data_base.sqlite_conversation import (
    SqliteConversationRepository,
)
from lumen_agent.infrastructure.data_base.sqlite_user import SqliteUserRepository
from lumen_agent.application.service.auth.auth_service import decode_access_token
from lumen_agent.model_adapters import get_model_adapter
from lumen_agent.model_adapters.base import ModelAdapter

_logger = logging.getLogger(__name__)


# ── LLM & 仓储 ────────────────────────────────────────────────────


def get_llm_client(settings: Settings = Depends(get_settings)) -> ModelAdapter:
    """注入模型适配器（当前返回 DeepSeek）。"""
    return get_model_adapter(settings)


def get_conversation_repo(
    settings: Settings = Depends(get_settings),
) -> SqliteConversationRepository:
    """注入 SQLite 会话仓储（路径由 Settings 解析）。"""
    return SqliteConversationRepository(resolve_db_path(settings))


# ── 用户认证与路由授权 ───────────────────────────────────────────

_API_KEY_HEADER = "Authorization"
_BEARER_PREFIX = "bearer"


@dataclass(frozen=True)
class AuthContext:
    """一次已认证请求中的实时用户和 JWT 载荷。"""

    user: dict
    payload: dict


async def authenticate_access_token(
    token: str,
    settings: Settings,
) -> AuthContext:
    """校验 JWT 并读取实时用户，供 HTTP 与 WebSocket 共用。"""
    secret = str(settings.get("AUTH_JWT_SECRET", "")).strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service unavailable",
        )
    try:
        payload = decode_access_token(token, secret=secret)
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # 每次认证都查询用户表，使禁用账号和角色调整立即生效。
    repo = SqliteUserRepository(resolve_db_path(settings))
    user = await repo.get_by_id(str(payload["sub"]))
    if user is None or not user["enabled"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User does not exist or is disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return AuthContext(user=user, payload=payload)


async def get_current_auth_context(
    request: Request,
    settings: Settings = Depends(get_settings),
    authorization: str | None = Header(None, alias="Authorization"),
) -> AuthContext:
    # HTTP 中间件已经认证过时直接复用；直接调用依赖时再自行校验请求头。
    """校验前端 JWT，并从数据库读取用户的实时状态与权限。"""
    existing = getattr(request.state, "auth_context", None)
    if isinstance(existing, AuthContext):
        return existing

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = _parse_bearer_token(authorization)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format, expected: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await authenticate_access_token(token, settings)


async def get_current_user(
    context: AuthContext = Depends(get_current_auth_context),
) -> dict:
    """返回已认证用户，供不关心 JWT 时间信息的接口使用。"""
    return context.user

async def require_admin(
    request: Request,
    settings: Settings = Depends(get_settings),
    authorization: str | None = Header(None, alias="Authorization"),
) -> dict | None:
    """认证开启时要求管理员角色；本地关闭认证时保持原有行为。"""
    # 本地开发可关闭认证；开启后必须同时满足登录和管理员角色。
    if not settings.get("AUTH_ENABLED", False):
        return None
    context = await get_current_auth_context(
        request=request,
        settings=settings,
        authorization=authorization,
    )
    if context.user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator permission required",
        )
    return context.user



async def verify_api_key(
    request: Request,
    settings: Settings = Depends(get_settings),
    authorization: str | None = Header(None, alias="Authorization"),
) -> None:
    """API Key 认证依赖。"""

    # ChatRun 等路由已由 JWT 中间件认证时，无需再把 JWT 当成 API Key 校验。
    context = getattr(request.state, "auth_context", None)
    if isinstance(context, AuthContext):
        return
    now_ip = request.client.host if request.client else None
    # IP 白名单只保留给 AUTH_ENABLED=false 的本地开发模式，
    # 防止反向代理将外部请求都表现为 127.0.0.1 后绕过认证。
    if not settings.get("AUTH_ENABLED", False) and _is_allow_ip(now_ip, settings):
        return

    # ── 跨域 / 无 Origin → 必须认证 ────────────────────────────
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw_key = _parse_bearer_token(authorization)
    if raw_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format, expected: Bearer <key>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # SHA-256 摘要
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    # 查 DB
    try:
        repo = SqliteApiKeyRepository(resolve_db_path(settings))
        record = await repo.get_by_hash(key_hash)
    except Exception as exc:
        _logger.exception("API Key 校验时 DB 异常")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service unavailable",
        ) from exc

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or disabled API key",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── 内部辅助 ──────────────────────────────────────────────────────


def _is_allow_ip(tar: str | None, settings: Settings) -> bool:
    """校验请求IP是否在白名单内"""
    allowed_ips = settings.get("ALLOW_IP_ADDRESS", "127.0.0.1")

    allowed_ip_list : list[str] = [s.strip() for s in allowed_ips.split(",") if s.strip()]

    if tar in allowed_ip_list:
        return True
    return False

def _parse_bearer_token(authorization: str) -> str | None:
    """从 ``Authorization`` 头中提取 ``Bearer`` token。"""
    parts = authorization.strip().split(None, 1)
    if len(parts) != 2:
        return None
    scheme, token = parts
    if scheme.lower() != _BEARER_PREFIX or not token.strip():
        return None
    return token.strip()
