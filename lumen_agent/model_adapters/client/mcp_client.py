"""MCP 客户端管理器（全局单例）：连接、发现并调用远程 MCP Server 工具。

MCPConnection         — 单个 MCP Server 的 SSE 连接（与之前不变）
MCPClientManager      — 全局管理器，支持启动时全连 / 按 ID 增删改查
get_mcp_manager()     — 全局单例工厂（类似 HttpPool 的 get_http_pool）
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

logger = logging.getLogger(__name__)


class MCPConnection:
    """单个 MCP Server 的 SSE 连接生命周期。"""

    def __init__(self, url: str, api_key: str | None = None) -> None:
        self.url = url
        self.api_key = api_key
        self._session: ClientSession | None = None
        self._read: Any = None
        self._write: Any = None

    async def connect(self) -> None:
        """发起 SSE 连接并初始化 MCP 会话。"""
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        ctx = sse_client(self.url, headers=headers)
        self._read, self._write = await ctx.__aenter__()
        self._sse_ctx = ctx
        self._session = await ClientSession(self._read, self._write).__aenter__()
        await self._session.initialize()
        logger.info("MCP 连接已建立：%s", self.url)

    async def list_tools(self) -> list[dict[str, Any]]:
        """调用 tools/list，返回工具定义列表（内部 dict 格式）。"""
        if self._session is None:
            raise RuntimeError("MCP 连接未初始化，请先调用 connect()")
        result = await self._session.list_tools()
        return [
            {
                "name": t.name,
                "description": t.description or "",
                "inputSchema": t.inputSchema or {"type": "object", "properties": {}},
            }
            for t in result.tools
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """调用 tools/call，返回原始 content 列表。"""
        if self._session is None:
            raise RuntimeError("MCP 连接未初始化，请先调用 connect()")
        result = await self._session.call_tool(name, arguments)
        return result.content

    async def close(self) -> None:
        """关闭会话和 SSE 连接。幂等。"""
        session = self._session
        self._session = None
        if session is not None:
            try:
                await session.__aexit__(None, None, None)
            except Exception:
                logger.debug("关闭 MCP session 时忽略异常", exc_info=True)

        ctx = getattr(self, "_sse_ctx", None)
        if ctx is not None:
            try:
                await ctx.__aexit__(None, None, None)
            except Exception:
                logger.debug("关闭 SSE 连接时忽略异常", exc_info=True)

        self._read = None
        self._write = None
        logger.info("MCP 连接已关闭：%s", self.url)


class MCPClientManager:
    """全局 MCP 连接管理器（单例）。管理所有 MCP Server 连接。"""

    def __init__(self) -> None:
        self._connections: dict[str, MCPConnection] = {}
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    # ── 批量启动 ────────────────────────────────────────────────

    async def start_all(self, servers: list[dict[str, Any]]) -> None:
        """启动时连接所有 enabled 的 MCP Server。"""
        for svr in servers:
            sid = svr["id"]
            name = svr.get("name", sid)
            url = svr["url"]
            api_key = svr.get("api_key") or None
            try:
                conn = MCPConnection(url, api_key)
                await conn.connect()
                self._connections[sid] = conn
                logger.info("MCP Server %s（%s）已连接", name, url)
            except Exception as e:
                logger.warning("MCP Server %s（%s）连接失败: %s", name, url, e)
        self._initialized = True

    # ── 单服务器管理 ────────────────────────────────────────────

    async def connect_one(self, server_id: str, url: str, api_key: str | None = None) -> bool:
        """连接单个 MCP Server 并注册到管理器。"""
        try:
            conn = MCPConnection(url, api_key)
            await conn.connect()
            self._connections[server_id] = conn
            return True
        except Exception as e:
            logger.warning("MCP Server %s 连接失败: %s", url, e)
            return False

    async def disconnect(self, server_id: str) -> None:
        """断开单个 MCP Server 连接。"""
        conn = self._connections.pop(server_id, None)
        if conn is not None:
            await conn.close()

    async def reconnect(self, server_id: str, url: str, api_key: str | None = None) -> bool:
        """断开旧连接 → 重新连接。"""
        await self.disconnect(server_id)
        return await self.connect_one(server_id, url, api_key)

    # ── 查询 ────────────────────────────────────────────────────

    def get_connection(self, server_id: str) -> MCPConnection | None:
        """按 ID 获取已连接的 MCPConnection。"""
        return self._connections.get(server_id)

    def list_connection_ids(self) -> list[str]:
        """返回所有已连接的 server_id 列表。"""
        return list(self._connections.keys())

    # ── 全局关闭 ────────────────────────────────────────────────

    async def close_all(self) -> None:
        """关闭所有连接。幂等。"""
        for conn in self._connections.values():
            await conn.close()
        self._connections.clear()
        self._initialized = False


# ── 全局单例 ─────────────────────────────────────────────────────

_manager: MCPClientManager | None = None


def get_mcp_manager() -> MCPClientManager:
    """返回应用全局唯一的 MCPClientManager 实例。"""
    global _manager
    if _manager is None:
        _manager = MCPClientManager()
    return _manager
