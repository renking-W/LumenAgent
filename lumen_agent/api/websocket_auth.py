"""WebSocket JWT 握手、刷新与连接期权限校验。"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import HTTPException

from lumen_agent.api.dependency import AuthContext, authenticate_access_token
from lumen_agent.config import Settings, resolve_db_path
from lumen_agent.infrastructure.data_base.sqlite_user import SqliteUserRepository
from lumen_agent.infrastructure.websocket_manager import WebSocketConnectionManager


class WebSocketAuthenticationError(Exception):
    """携带应用层 WebSocket 关闭码的认证异常。"""

    def __init__(self, code: int, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


# WebSocket 使用和 HTTP 相同的过期/刷新时间，但通过控制消息同步给前端。
def _auth_times(context: AuthContext, settings: Settings) -> dict[str, str]:
    try:
        expires_at = int(context.payload["exp"])
        refresh_before = int(settings.get("AUTH_JWT_REFRESH_BEFORE_HOURS", 8))
    except (KeyError, TypeError, ValueError) as exc:
        raise WebSocketAuthenticationError(4401, "Token 时间信息无效") from exc
    refresh_at = expires_at - refresh_before * 3600
    return {
        "expires_at": datetime.fromtimestamp(expires_at, timezone.utc).isoformat(),
        "refresh_at": datetime.fromtimestamp(refresh_at, timezone.utc).isoformat(),
    }


async def _authenticate_admin_token(
    token: object,
    settings: Settings,
) -> AuthContext:
    # VM 能力只允许管理员使用，普通登录用户返回 4403。
    if not isinstance(token, str) or not token.strip():
        raise WebSocketAuthenticationError(4401, "缺少有效 Token")
    try:
        context = await authenticate_access_token(token.strip(), settings)
    except HTTPException as exc:
        raise WebSocketAuthenticationError(4401, str(exc.detail)) from exc
    if context.user["role"] != "admin":
        raise WebSocketAuthenticationError(4403, "需要管理员权限")
    return context


async def authenticate_initial_message(
    manager: WebSocketConnectionManager,
    connection_id: str,
    settings: Settings,
) -> AuthContext | None:
    """认证关闭时保持旧行为；开启时要求5秒内发送 auth 首帧。"""
    if not settings.get("AUTH_ENABLED", False):
        return None
    # 浏览器 WebSocket 无法自定义 Authorization，请求建立后从首帧读取 JWT。
    message = await manager.receive_json(connection_id, timeout=5)
    if message is None:
        raise WebSocketAuthenticationError(4408, "认证消息超时")
    if message.get("type") != "auth":
        raise WebSocketAuthenticationError(4401, "首条消息必须是 auth")
    context = await _authenticate_admin_token(message.get("token"), settings)
    await manager.send_json(
        connection_id,
        {"type": "auth_ok", **_auth_times(context, settings)},
    )
    return context


async def refresh_websocket_auth(
    manager: WebSocketConnectionManager,
    connection_id: str,
    message: dict,
    settings: Settings,
) -> AuthContext:
    """使用新的 HTTP Access Token 更新现有 WebSocket 身份。"""
    # 新 Token 已由 HTTP refresh 接口签发，这里只更新当前连接的认证上下文。
    context = await _authenticate_admin_token(message.get("token"), settings)
    await manager.send_json(
        connection_id,
        {"type": "auth_refreshed", **_auth_times(context, settings)},
    )
    return context


async def ensure_websocket_admin_active(
    context: AuthContext,
    settings: Settings,
) -> AuthContext:
    """连接期间重新读取用户，确保禁用和角色调整最多60秒生效。"""
    # 长连接不会重新经过 HTTP 中间件，因此定期回查用户状态。
    repo = SqliteUserRepository(resolve_db_path(settings))
    user = await repo.get_by_id(context.user["id"])
    if user is None or not user["enabled"]:
        raise WebSocketAuthenticationError(4403, "账号不存在或已禁用")
    if user["role"] != "admin":
        raise WebSocketAuthenticationError(4403, "需要管理员权限")
    return AuthContext(user=user, payload=context.payload)


def authenticated_receive_timeout(context: AuthContext | None) -> float:
    """让接收等待不超过 Token 剩余寿命，确保到期后及时关闭。"""
    # receive 最多等待60秒；若 Token 更早到期，则以剩余寿命作为等待上限。
    # 等待返回后下一轮会立即触发过期检查并关闭连接。
    if context is None:
        return 60
    try:
        remaining = int(context.payload["exp"]) - time.time()
    except (KeyError, TypeError, ValueError) as exc:
        raise WebSocketAuthenticationError(4401, "Token 时间信息无效") from exc
    if remaining <= 0:
        raise WebSocketAuthenticationError(4401, "Access token expired")
    return min(60, max(0.1, remaining))
