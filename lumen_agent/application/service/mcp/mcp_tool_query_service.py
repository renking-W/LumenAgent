"""MCP 工具检索/列表业务逻辑（供 mcp_search、mcp_call 调试 API 复用）。

流程：Chroma 向量召回 tool_id → SQLite 回表取完整 schema → 组装 Agent/API 响应。
"""

from __future__ import annotations

from typing import Any

from lumen_agent.application.service.mcp.mcp_tool_rag_service import McpToolRagService
from lumen_agent.config import Settings, get_settings, resolve_db_path
from lumen_agent.infrastructure.data_base.sqlite_mcp import SqliteMCPServerRepository
from lumen_agent.infrastructure.data_base.sqlite_mcp_stdio import SqliteMCPStdioServerRepository
from lumen_agent.infrastructure.data_base.sqlite_mcp_tools import SqliteMCPToolRepository


class McpToolQueryService:
    """MCP 工具查询服务。"""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        db_path = resolve_db_path(self._settings)
        self._tool_repo = SqliteMCPToolRepository(db_path)
        self._http_repo = SqliteMCPServerRepository(db_path)
        self._stdio_repo = SqliteMCPStdioServerRepository(db_path)
        self._rag = McpToolRagService(self._settings)

    async def _server_name_map(self) -> dict[tuple[str, str], str]:
        """构建 (server_kind, server_id) → 显示名称 映射。"""
        mapping: dict[tuple[str, str], str] = {}
        for s in await self._http_repo.list_all():
            mapping[("http", s["id"])] = s["name"]
        for s in await self._stdio_repo.list_all():
            mapping[("stdio", s["id"])] = s["name"]
        return mapping

    def _tool_to_result(
        self, tool: dict[str, Any], server_names: dict[tuple[str, str], str], score: float | None = None
    ) -> dict[str, Any]:
        """将 SQLite 记录转为 Agent/API 统一的 tool 结果结构。"""
        key = (tool["server_kind"], tool["server_id"])
        row: dict[str, Any] = {
            "tool_id": tool["id"],
            "server_id": tool["server_id"],
            "server_kind": tool["server_kind"],
            "server_name": server_names.get(key, tool["server_id"]),
            "tool_name": tool["original_name"],
            "description": tool.get("description") or "",
            "parameters": tool.get("input_schema") or {},
        }
        if score is not None:
            row["score"] = score
        return row

    async def search_tools(
        self,
        query: str,
        *,
        top_k: int | None = None,
        server_ids: list[str] | None = None,
        similarity_threshold: float | None = None,
    ) -> dict[str, Any]:
        """向量检索 + 回表，返回 top-K tool 详情。"""
        k = top_k or int(self._settings.get("MCP_TOOL_SEARCH_TOP_K", 5))
        threshold = similarity_threshold
        if threshold is None:
            threshold = float(self._settings.get("MCP_TOOL_SEARCH_SIMILARITY_THRESHOLD", 0.2))

        hits = await self._rag.search(
            query,
            top_k=k,
            similarity_threshold=threshold,
            server_ids=server_ids,
        )
        tool_ids = [h["tool_id"] for h in hits if h.get("tool_id")]
        tools = await self._tool_repo.get_by_ids(tool_ids)
        tool_map = {t["id"]: t for t in tools}
        server_names = await self._server_name_map()

        # 保持 Chroma 返回的顺序（按相似度排序）
        results: list[dict[str, Any]] = []
        for hit in hits:
            tool = tool_map.get(hit.get("tool_id", ""))
            if tool is None:
                continue
            results.append(
                self._tool_to_result(tool, server_names, score=hit.get("score"))
            )
        return {
            "query": query,
            "top_k": k,
            "total_hits": len(results),
            "results": results,
        }

    async def list_tools(
        self,
        *,
        server_kind: str | None = None,
        server_id: str | None = None,
        server_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """直接列出 DB 中已索引 tool（mcp_search list_all 模式 / 调试 API）。"""
        tools = await self._tool_repo.list_all(
            server_kind=server_kind,
            server_id=server_id,
            server_ids=server_ids,
        )
        server_names = await self._server_name_map()
        return [self._tool_to_result(t, server_names) for t in tools]

    async def get_tool(self, tool_id: str) -> dict[str, Any] | None:
        """查询单条 tool 详情（含 search_doc，供调试 API）。"""
        tool = await self._tool_repo.get(tool_id)
        if tool is None:
            return None
        server_names = await self._server_name_map()
        result = self._tool_to_result(tool, server_names)
        result["search_doc"] = tool.get("search_doc") or ""
        result["schema_hash"] = tool.get("schema_hash") or ""
        result["created_at"] = tool.get("created_at")
        result["updated_at"] = tool.get("updated_at")
        return result
