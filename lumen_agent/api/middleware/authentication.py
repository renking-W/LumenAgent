"""进程内 HTTP JWT 认证中间件，不缓存请求体或流式响应。"""

from __future__ import annotations

from fastapi import HTTPException, Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from lumen_agent.api.dependency import get_current_auth_context
from lumen_agent.config import get_settings


# 登录和认证状态必须在没有 JWT 时也能访问。
_PUBLIC_PATHS = {
    "/v1/auth/login",
    "/v1/auth/status",
}

# 旧 Chat API 保留给第三方 API Key；其路由继续调用 verify_api_key。
_API_KEY_PATHS = {
    "/v1/chat",
    "/v1/chat/stream",
    "/v1/chat/stream/interrupt",
    "/v1/chat/stream/approve",
}


class AuthenticationMiddleware:
    """为受保护的 ``/v1`` HTTP 请求统一校验 JWT。"""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        # WebSocket 不走 HTTP 请求头认证，由对应端点执行首帧认证。
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        settings = get_settings()
        path = scope.get("path", "").rstrip("/") or "/"
        method = scope.get("method", "GET").upper()
        # 本地关闭认证、CORS 预检和公开接口直接放行。
        # API Key兼容接口会先尝试JWT，失败后再交给路由依赖校验API Key。
        if (
            not settings.get("AUTH_ENABLED", False)
            or method == "OPTIONS"
            or path in _PUBLIC_PATHS
        ):
            await self._app(scope, receive, send)
            return

        # 进入正式路由前完成 JWT、用户启用状态和实时权限字段校验。
        request = Request(scope, receive=receive)
        try:
            context = await get_current_auth_context(
                request=request,
                settings=settings,
                authorization=request.headers.get("Authorization"),
            )
        except HTTPException as exc:
            if path in _API_KEY_PATHS:
                await self._app(scope, receive, send)
                return

            response = JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=exc.headers,
            )
            await response(scope, receive, send)
            return

        # 缓存到 ASGI scope，后续 Depends 直接复用，避免重复解析和查询数据库。
        scope.setdefault("state", {})["auth_context"] = context
        await self._app(scope, receive, send)
