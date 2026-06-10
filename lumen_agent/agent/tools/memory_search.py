"""MemorySearch 工具：在历史记忆中检索相关内容。"""

from __future__ import annotations

import logging

from lumen_agent.agent.tools.base import BaseTool, ToolResult
from lumen_agent.agent.tools.registry import ToolRegistry
from lumen_agent.application.service.memory_rag_service import MemoryRagService
from lumen_agent.config import get_settings


@ToolRegistry.register
class MemorySearch(BaseTool):
    """检索历史记忆条目。"""

    _logger = logging.getLogger(__name__)

    name = "memory_search"
    description = "在历史记忆文件中检索与 query 相关的记忆内容，返回相似度和文本。"
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "要检索的自然语言问题或关键词。例如：'用户对什么食物过敏', '之前讨论过的项目计划'。",
            },
            "top_k": {
                "type": "integer",
                "description": "返回的最大记忆条数，默认 5 条。可选。",
            },
        },
        "required": ["query"],
    }

    async def execute(self, params: dict) -> ToolResult:
        query = str(params.get("query", "")).strip()
        if not query:
            return ToolResult.error("query 不能为空。")

        top_k = int(params.get("top_k") or 5)
        settings = get_settings()
        service = MemoryRagService(settings)
        threshold = settings.get("MEMORY_SEARCH_SIMILARITY_THRESHOLD", 0.25)

        self._logger.info(
            "记忆检索工具：开始检索，query=%r  top_k=%s  threshold=%.2f",
            query,
            top_k,
            threshold,
        )
        results = await service.search(query, top_k=top_k, similarity_threshold=threshold)
        payload = {
            "query": query,
            "top_k": top_k,
            "total_hits": len(results),
            "results": results,
        }
        self._logger.info("记忆检索工具：完成，命中 %s 条", len(results))
        return ToolResult.success(payload)
