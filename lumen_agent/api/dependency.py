"""FastAPI `Depends` 工厂：集中装配模型适配器、仓储与认证依赖。"""

import hashlib
import logging

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


# ── API Key 认证 ──────────────────────────────────────────────────

_API_KEY_HEADER = "Authorization"
_BEARER_PREFIX = "bearer"


async def verify_api_key(
    request: Request,
    settings: Settings = Depends(get_settings),
    authorization: str | None = Header(None, alias="Authorization"),
) -> None:
    """API Key 认证依赖。"""

    now_ip = request.client.host
    if _is_allow_ip(now_ip,settings) :
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
