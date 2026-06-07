"""MCPBridgeTool：将远程 MCP Server 暴露的工具包装为本地 BaseTool，可被 Agent 直接调用。"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from lumen_agent.agent.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class MCPBridgeTool(BaseTool):
    """包装远程 MCP 工具为本地 BaseTool，execute() 通过 MCP 协议远程调用。

    不通过 @ToolRegistry.register 注册全局，仅在每次请求时由
    reply_with_agent 动态实例化并合并到工具列表。
    """

    name: str = ""
    description: str = ""
    parameters: dict = {}

    def __init__(
        self,
        tool_def: dict[str, Any],
        connection: "MCPConnection",  # noqa: F821 – 运行时导入避免循环
        server_url: str,
    ) -> None:
        original_name = tool_def["name"]
        # 防命名冲突：mcp_<url_hash6>_<tool_name>
        server_tag = hashlib.md5(server_url.encode()).hexdigest()[:6]
        self.name = f"mcp_{server_tag}_{original_name}"
        self.description = tool_def.get("description", "")
        raw_schema = tool_def.get("inputSchema", {})
        self.parameters = raw_schema if isinstance(raw_schema, dict) else {
            "type": "object", "properties": {}
        }
        self._connection = connection
        self._original_name = original_name

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """通过 MCP 协议远程调用工具，返回结果。"""
        logger.info(
            "MCP 工具调用：%s（远程名：%s）", self.name, self._original_name,
        )
        try:
            content = await self._connection.call_tool(self._original_name, params)
        except Exception as e:
            logger.exception("MCP 工具 '%s' 调用异常", self._original_name)
            return ToolResult.error(f"MCP 工具 '{self._original_name}' 调用失败: {e}")

        # 将 MCP 返回的 Content 列表转为纯文本
        text_parts: list[str] = []
        for item in content:
            if hasattr(item, "text") and item.text:
                text_parts.append(item.text)
            else:
                text_parts.append(str(item))

        result_text = "\n".join(text_parts)
        logger.info(
            "MCP 工具 '%s' 返回完成（%d 字符）",
            self._original_name, len(result_text),
        )
        return ToolResult.success(result_text)
