"""McpSearch 工具：向量检索 MCP 工具并回表返回 schema。

Agent 通过本工具按需发现外部 MCP 能力，避免将全部 MCP schema 塞进 prompt。
"""

from __future__ import annotations

import logging

from lumen_agent.agent.tools.base import BaseTool, ToolResult
from lumen_agent.agent.tools.registry import ToolRegistry
from lumen_agent.application.service.mcp.mcp_request_context import get_allowed_server_ids
from lumen_agent.application.service.mcp.mcp_tool_query_service import McpToolQueryService
from lumen_agent.config import get_settings


@ToolRegistry.register
class McpSearch(BaseTool):
    """检索外部 MCP 工具。"""

    _logger = logging.getLogger(__name__)

    name = "mcp_search"
    description = (
        "检索已接入的外部 MCP 工具。"
        "使用前请用自然语言 query 搜索相关工具，获取 tool_name 与 parameters；"
        "需要浏览某 server 下全部工具时设置 list_all=true。"
        "确认工具后再用 mcp_call 执行。"
        "当你需要解决目前tools无法解决的问题时，可以使用该tool来获取额外的mcp能力"
        "不知道用哪个tool可以使用list_all模式"
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "检索 query，例如：'飞书多维表格 查询记录'。list_all=true 时可省略。",
            },
            "top_k": {
                "type": "integer",
                "description": "向量检索返回的最大工具数，默认 5。",
            },
            "list_all": {
                "type": "boolean",
                "description": "为 true 时列出 DB 中工具（可按 server_id 过滤），不走向量检索。",
            },
            "server_id": {
                "type": "string",
                "description": "可选，限定某个 MCP server。",
            },
        },
        "required": [],
    }

    async def execute(self, params: dict) -> ToolResult:
        # 前端 MCPServerSelector 选中的 server 范围（由 chat_service 注入）
        allowed = get_allowed_server_ids()
        if allowed is not None and not allowed:
            return ToolResult.error(
                "当前会话未选择 MCP Server。请在前端选择要使用的 MCP Server 后重试。"
            )

        server_ids = allowed
        server_id = str(params.get("server_id") or "").strip()
        if server_id:
            if server_ids is not None and server_id not in server_ids:
                return ToolResult.error(f"server_id {server_id!r} 不在当前允许的 MCP 范围内。")
            server_ids = [server_id]

        service = McpToolQueryService(get_settings())
        list_all = bool(params.get("list_all"))

        # 模式一：直接列出 DB 中 tool（不走向量）
        if list_all:
            results = await service.list_tools(
                server_id=server_id or None,
                server_ids=server_ids,
            )
            payload = {
                "list_all": True,
                "server_id": server_id or None,
                "total_hits": len(results),
                "results": results,
            }
            return ToolResult.success(payload)

        # 模式二：向量检索 top-K → 回表返回 schema
        query = str(params.get("query") or "").strip()
        if not query:
            return ToolResult.error("query 不能为空（或使用 list_all=true）。")

        payload = await service.search_tools(
            query,
            top_k=params.get("top_k"),
            server_ids=server_ids,
        )
        self._logger.info("mcp_search 完成，命中 %s 条", payload.get("total_hits"))
        return ToolResult.success(payload)
