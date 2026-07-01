"""MCP 客户端管理器（全局单例）：连接、发现并调用远程 MCP Server 工具。

_BaseMCPConnection    — 公共基类（list_tools / call_tool / close）
MCPConnection         — HTTP MCP Server（SSE 或 Streamable HTTP，自动探测并写回 transport）
MCPStdioConnection    — 本地 stdio MCP Server（command + args）
MCPClientManager      — 全局管理器，http 与 stdio 连接统一存储，通过 ID 前缀区分
get_mcp_manager()     — 全局单例工厂
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client

logger = logging.getLogger(__name__)


# ── 公共基类 ─────────────────────────────────────────────────────

class _BaseMCPConnection:
    """MCP 连接公共接口（鸭子类型基类）。"""

    async def connect(self) -> None:
        raise NotImplementedError

    async def list_tools(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError

    def _tools_from_result(self, result: Any) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description or "",
                "inputSchema": t.inputSchema or {"type": "object", "properties": {}},
            }
            for t in result.tools
        ]


# ── HTTP 连接（SSE / Streamable HTTP） ───────────────────────────

class MCPConnection(_BaseMCPConnection):
    """HTTP MCP Server 的连接生命周期。

    transport 参数：
    - ``"sse"``             → 强制使用 Legacy HTTP+SSE
    - ``"streamable_http"`` → 强制使用 Streamable HTTP
    - ``""``（默认）        → 自动探测：先试 Streamable HTTP，失败回退 SSE
    """

    def __init__(
        self,
        url: str,
        api_key: str | None = None,
        transport: str = "",
    ) -> None:
        self.url = url
        self.api_key = api_key
        self.transport = transport
        self.resolved_transport: str = ""
        self._session: ClientSession | None = None
        self._read: Any = None
        self._write: Any = None
        self._transport_ctx: Any = None

    # ── 内部工具 ─────────────────────────────────────────────────

    def _build_http_client(self) -> httpx.AsyncClient | None:
        if self.api_key:
            return httpx.AsyncClient(
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=30,
            )
        return None

    async def _try_streamable_http(self) -> bool:
        """尝试建立 Streamable HTTP 连接。返回是否成功。"""
        try:
            http_client = self._build_http_client()
            ctx = streamable_http_client(self.url, http_client=http_client)
            self._read, self._write, _get_sid = await ctx.__aenter__()
            self._transport_ctx = ctx
            self._session = await ClientSession(self._read, self._write).__aenter__()
            await self._session.initialize()
            self.resolved_transport = "streamable_http"
            logger.info("MCP Streamable HTTP 连接已建立：%s", self.url)
            return True
        except Exception as e:
            logger.debug("Streamable HTTP 探测失败 %s：%s", self.url, e)
            await self._cleanup_partial()
            return False

    async def _try_sse(self) -> bool:
        """尝试建立 SSE 连接。返回是否成功。"""
        try:
            headers: dict[str, str] = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            ctx = sse_client(self.url, headers=headers)
            self._read, self._write = await ctx.__aenter__()
            self._transport_ctx = ctx
            self._session = await ClientSession(self._read, self._write).__aenter__()
            await self._session.initialize()
            self.resolved_transport = "sse"
            logger.info("MCP SSE 连接已建立：%s", self.url)
            return True
        except Exception as e:
            logger.debug("SSE 探测失败 %s：%s", self.url, e)
            await self._cleanup_partial()
            return False

    async def _cleanup_partial(self) -> None:
        """清理部分建立的连接资源。"""
        if self._session is not None:
            try:
                await self._session.__aexit__(None, None, None)
            except Exception:
                pass
            self._session = None

        if self._transport_ctx is not None:
            try:
                await self._transport_ctx.__aexit__(None, None, None)
            except Exception:
                pass
            self._transport_ctx = None

        self._read = None
        self._write = None

    # ── 公开接口 ─────────────────────────────────────────────────

    async def connect(self) -> None:
        """根据 transport 建立连接；为空时自动探测（先 streamable_http，回退 sse）。"""
        if self.transport == "streamable_http":
            if not await self._try_streamable_http():
                raise RuntimeError(f"Streamable HTTP 连接失败：{self.url}")

        elif self.transport == "sse":
            if not await self._try_sse():
                raise RuntimeError(f"SSE 连接失败：{self.url}")

        else:
            # 自动探测
            if not await self._try_streamable_http():
                if not await self._try_sse():
                    raise RuntimeError(
                        f"MCP Server 连接失败（streamable_http 和 sse 均不可用）：{self.url}"
                    )

    async def list_tools(self) -> list[dict[str, Any]]:
        if self._session is None:
            raise RuntimeError("MCP 连接未初始化，请先调用 connect()")
        result = await self._session.list_tools()
        return self._tools_from_result(result)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if self._session is None:
            raise RuntimeError("MCP 连接未初始化，请先调用 connect()")
        result = await self._session.call_tool(name, arguments)
        return result.content

    async def close(self) -> None:
        """关闭会话和传输连接。幂等。"""
        session = self._session
        self._session = None
        if session is not None:
            try:
                await session.__aexit__(None, None, None)
            except Exception:
                logger.debug("关闭 MCP session 时忽略异常", exc_info=True)

        ctx = self._transport_ctx
        self._transport_ctx = None
        if ctx is not None:
            try:
                await ctx.__aexit__(None, None, None)
            except Exception:
                logger.debug("关闭传输连接时忽略异常", exc_info=True)

        self._read = None
        self._write = None
        logger.info("MCP HTTP 连接已关闭：%s", self.url)


# ── stdio 连接 ────────────────────────────────────────────────────

class MCPStdioConnection(_BaseMCPConnection):
    """本地 stdio MCP Server 的连接生命周期。"""

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> None:
        self.command = command
        self.args = args or []
        self.env = env or None
        self.cwd = cwd or None
        self._session: ClientSession | None = None
        self._read: Any = None
        self._write: Any = None
        self._transport_ctx: Any = None

    async def connect(self) -> None:
        """启动子进程并建立 stdio MCP 会话。"""
        params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=self.env,
            cwd=self.cwd,
        )
        ctx = stdio_client(params)
        self._read, self._write = await ctx.__aenter__()
        self._transport_ctx = ctx
        self._session = await ClientSession(self._read, self._write).__aenter__()
        await self._session.initialize()
        logger.info("MCP stdio 连接已建立：%s %s", self.command, " ".join(self.args))

    async def list_tools(self) -> list[dict[str, Any]]:
        if self._session is None:
            raise RuntimeError("MCP stdio 连接未初始化，请先调用 connect()")
        result = await self._session.list_tools()
        return self._tools_from_result(result)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if self._session is None:
            raise RuntimeError("MCP stdio 连接未初始化，请先调用 connect()")
        result = await self._session.call_tool(name, arguments)
        return result.content

    async def close(self) -> None:
        """关闭会话和子进程。幂等。"""
        session = self._session
        self._session = None
        if session is not None:
            try:
                await session.__aexit__(None, None, None)
            except Exception:
                logger.debug("关闭 stdio session 时忽略异常", exc_info=True)

        ctx = self._transport_ctx
        self._transport_ctx = None
        if ctx is not None:
            try:
                await ctx.__aexit__(None, None, None)
            except Exception:
                logger.debug("关闭 stdio 进程时忽略异常", exc_info=True)

        self._read = None
        self._write = None
        logger.info("MCP stdio 连接已关闭：%s", self.command)


# ── 全局管理器 ────────────────────────────────────────────────────

class MCPClientManager:
    """全局 MCP 连接管理器（单例）。统一管理 http 与 stdio 两类连接。

    http  连接 ID 前缀：``mcp-``
    stdio 连接 ID 前缀：``stdio-``
    """

    def __init__(self) -> None:
        self._connections: dict[str, _BaseMCPConnection] = {}
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    # ── 批量启动 ────────────────────────────────────────────────

    async def start_all(self, servers: list[dict[str, Any]]) -> None:
        """启动时连接所有 enabled 的 HTTP MCP Server。"""
        for svr in servers:
            sid = svr["id"]
            name = svr.get("name", sid)
            url = svr["url"]
            api_key = svr.get("api_key") or None
            transport = svr.get("transport") or ""
            ok, resolved = await self.connect_one(sid, url, api_key, transport)
            if ok:
                logger.info("MCP Server %s（%s）已连接 transport=%s", name, url, resolved)
            else:
                logger.warning("MCP Server %s（%s）连接失败", name, url)
        self._initialized = True

    async def start_all_stdio(self, servers: list[dict[str, Any]]) -> None:
        """启动时连接所有 enabled 的 stdio MCP Server。"""
        for svr in servers:
            sid = svr["id"]
            name = svr.get("name", sid)
            ok = await self.connect_stdio_one(
                sid,
                svr["command"],
                svr.get("args") or [],
                svr.get("env") or None,
                svr.get("cwd") or None,
            )
            if ok:
                logger.info("MCP stdio Server %s 已连接", name)
            else:
                logger.warning("MCP stdio Server %s 连接失败", name)

    # ── 单服务器管理（HTTP） ────────────────────────────────────

    async def connect_one(
        self,
        server_id: str,
        url: str,
        api_key: str | None = None,
        transport: str = "",
    ) -> tuple[bool, str]:
        """连接单个 HTTP MCP Server 并注册到管理器。

        Returns
        -------
        (ok, resolved_transport)
            ok — 连接是否成功
            resolved_transport — 实际使用的 transport（"sse" / "streamable_http"）
        """
        try:
            conn = MCPConnection(url, api_key, transport)
            await conn.connect()
            self._connections[server_id] = conn
            return True, conn.resolved_transport
        except Exception as e:
            logger.warning("MCP Server %s 连接失败: %s", url, e)
            return False, ""

    async def disconnect(self, server_id: str) -> None:
        """断开单个 MCP Server 连接。"""
        conn = self._connections.pop(server_id, None)
        if conn is not None:
            await conn.close()

    async def reconnect(
        self,
        server_id: str,
        url: str,
        api_key: str | None = None,
        transport: str = "",
    ) -> tuple[bool, str]:
        """断开旧连接 → 重新连接（HTTP）。"""
        await self.disconnect(server_id)
        return await self.connect_one(server_id, url, api_key, transport)

    # ── 单服务器管理（stdio） ───────────────────────────────────

    async def connect_stdio_one(
        self,
        server_id: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> bool:
        """连接单个 stdio MCP Server 并注册到管理器。"""
        try:
            conn = MCPStdioConnection(command, args, env, cwd)
            await conn.connect()
            self._connections[server_id] = conn
            return True
        except Exception as e:
            logger.warning("MCP stdio Server %s 连接失败: %s", command, e)
            return False

    async def disconnect_stdio(self, server_id: str) -> None:
        """断开单个 stdio MCP Server 连接（与 disconnect 等价，保留语义别名）。"""
        await self.disconnect(server_id)

    # ── 查询 ────────────────────────────────────────────────────

    def get_connection(self, server_id: str) -> _BaseMCPConnection | None:
        """按 ID 获取已连接的 MCP 连接（http 或 stdio 均可）。"""
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
