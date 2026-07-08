"""MCP 工具检索范围：按请求注入 allowed_server_ids。

chat_service 在 Agent 循环开始前 set，mcp_search / mcp_call 在 execute 时 get，
用于限定前端 MCPServerSelector 选中的 MCP Server 范围。
"""

from __future__ import annotations

from contextvars import ContextVar, Token

_allowed_server_ids: ContextVar[list[str] | None] = ContextVar(
    "mcp_allowed_server_ids", default=None
)


def set_allowed_server_ids(server_ids: list[str] | None) -> Token:
    """写入当前请求的 MCP Server 白名单，返回 token 供 finally 中 reset。"""
    return _allowed_server_ids.set(server_ids)


def clear_allowed_server_ids() -> None:
    """清除 MCP Server 白名单（不依赖 Token，适用于 SSE 等跨 task 场景）。"""
    _allowed_server_ids.set(None)


def reset_allowed_server_ids(token: Token) -> None:
    """恢复上下文，避免污染后续请求。

    SSE 流式响应可能在不同 asyncio Context 中关闭 generator，reset(token) 会失败；
    此时降级为 clear。
    """
    try:
        _allowed_server_ids.reset(token)
    except ValueError:
        _allowed_server_ids.set(None)


def get_allowed_server_ids() -> list[str] | None:
    """读取当前请求的 MCP Server 白名单。

    返回 None 表示未设置范围限制（调试 API 等场景）；
    返回 [] 表示前端未选择任何 MCP Server。
    """
    return _allowed_server_ids.get()
