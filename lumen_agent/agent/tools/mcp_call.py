"""McpCall 工具：代理调用外部 MCP 工具。

Agent 先通过 mcp_search 确认 server_id / tool_name / parameters，
再通过本工具经 MCP 协议远程执行，无需将每个 MCP tool 注册进 ToolRegistry。
"""

from __future__ import annotations

import logging
from typing import Any

from lumen_agent.agent.tools.base import BaseTool, ToolResult
from lumen_agent.agent.tools.registry import ToolRegistry
from lumen_agent.application.service.mcp.mcp_request_context import get_allowed_server_ids
from lumen_agent.model_adapters.client import get_mcp_manager


def _content_to_text(content: Any) -> str:
    """将 MCP 返回的 Content 列表转为纯文本（与 MCPBridgeTool 一致）。"""
    text_parts: list[str] = []
    for item in content:
        if hasattr(item, "text") and item.text:
            text_parts.append(item.text)
        else:
            text_parts.append(str(item))
    return "\n".join(text_parts)


@ToolRegistry.register
class McpCall(BaseTool):
    """代理执行外部 MCP 工具。"""

    _logger = logging.getLogger(__name__)

    name = "mcp_call"
    description = (
        "调用外部 MCP 工具。"
        "需先通过 mcp_search 确认 server_id、tool_name 与 parameters，再传入 arguments 执行。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "server_id": {
                "type": "string",
                "description": "MCP Server ID（来自 mcp_search 结果）。",
            },
            "tool_name": {
                "type": "string",
                "description": "MCP 原生工具名 original_name（来自 mcp_search 的 tool_name）。",
            },
            "arguments": {
                "type": "object",
                "description": "传给 MCP 工具的参数对象。",
            },
        },
        "required": ["server_id", "tool_name", "arguments"],
    }

    async def execute(self, params: dict) -> ToolResult:
        server_id = str(params.get("server_id") or "").strip()
        tool_name = str(params.get("tool_name") or "").strip()
        arguments = params.get("arguments")

        if not server_id:
            return ToolResult.error("server_id 不能为空。")
        if not tool_name:
            return ToolResult.error("tool_name 不能为空。")
        if not isinstance(arguments, dict):
            return ToolResult.error("arguments 必须是 object。")

        # 校验 server 是否在前端选中的范围内
        allowed = get_allowed_server_ids()
        if allowed is not None:
            if not allowed:
                return ToolResult.error(
                    "当前会话未选择 MCP Server。请在前端选择要使用的 MCP Server 后重试。"
                )
            if server_id not in allowed:
                return ToolResult.error(
                    f"server_id {server_id!r} 不在当前允许的 MCP 范围内。"
                )

        conn = get_mcp_manager().get_connection(server_id)
        if conn is None:
            return ToolResult.error(
                f"MCP Server {server_id!r} 未连接或不存在，请检查配置与启用状态。"
            )

        self._logger.info("mcp_call: server=%s tool=%s", server_id, tool_name)
        try:
            content = await conn.call_tool(tool_name, arguments)
        except Exception as e:
            self._logger.exception("mcp_call 失败：%s/%s", server_id, tool_name)
            return ToolResult.error(f"MCP 工具 {tool_name!r} 调用失败: {e}")

        result_text = _content_to_text(content)
        self._logger.info(
            "mcp_call 完成：%s/%s 返回 %d 字符",
            server_id,
            tool_name,
            len(result_text),
        )
        return ToolResult.success(result_text)
