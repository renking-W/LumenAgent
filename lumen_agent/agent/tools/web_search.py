"""WebSearch 工具：使用 DuckDuckGo 搜索关键词并返回结果摘要。"""

from __future__ import annotations

from lumen_agent.agent.tools.base import BaseTool, ToolResult
from lumen_agent.agent.tools.registry import ToolRegistry

_DEFAULT_MAX_RESULTS = 5
_MAX_RESULTS_LIMIT = 20


@ToolRegistry.register
class WebSearch(BaseTool):
    """调用 DuckDuckGo 搜索引擎，返回与查询词相关的网页标题、链接和摘要。"""

    name = "web_search"
    description = (
        "在互联网上搜索关键词，返回相关网页的标题、URL 和摘要列表。"
        "适合需要获取最新资讯、技术文档、新闻或任何网络信息的场景。"
        f"默认返回 {_DEFAULT_MAX_RESULTS} 条结果，最多 {_MAX_RESULTS_LIMIT} 条。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词或自然语言问题。",
            },
            "max_results": {
                "type": "integer",
                "description": (
                    f"返回结果数量，默认 {_DEFAULT_MAX_RESULTS}，"
                    f"最大 {_MAX_RESULTS_LIMIT}。可选。"
                ),
            },
            "region": {
                "type": "string",
                "description": (
                    "搜索地区，影响结果语言与本地化，如 'zh-cn'（中文简体）、"
                    "'us-en'（英文）。可选，默认 'zh-cn'。"
                ),
            },
        },
        "required": ["query"],
    }

    async def execute(self, params: dict) -> ToolResult:
        try:
            from ddgs import DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS  # type: ignore[no-redef]
            except ImportError:
                return ToolResult.error(
                    "缺少依赖 'ddgs'，请执行：pip install ddgs"
                )

        query: str = str(params.get("query", "")).strip()
        if not query:
            return ToolResult.error("query 不能为空。")

        max_results_val = params.get("max_results")
        try:
            max_results = int(max_results_val) if max_results_val is not None else _DEFAULT_MAX_RESULTS
        except (TypeError, ValueError):
            return ToolResult.error("max_results 须为整数。")
        if max_results < 1 or max_results > _MAX_RESULTS_LIMIT:
            return ToolResult.error(f"max_results 须在 1～{_MAX_RESULTS_LIMIT} 之间。")

        region: str = str(params.get("region") or "zh-cn").strip()

        try:
            import asyncio
            results = await asyncio.get_event_loop().run_in_executor(
                None, lambda: _do_search(query, max_results, region)
            )
        except Exception as exc:
            return ToolResult.error(f"搜索失败：{exc}")

        if not results:
            return ToolResult.success("未找到相关结果。")

        lines: list[str] = [f"搜索词：{query}（共 {len(results)} 条结果）\n"]
        for i, r in enumerate(results, 1):
            title = r.get("title") or ""
            href = r.get("href") or r.get("url") or ""
            body = r.get("body") or ""
            lines.append(f"[{i}] {title}")
            if href:
                lines.append(f"    URL: {href}")
            if body:
                lines.append(f"    摘要: {body}")
            lines.append("")

        return ToolResult.success("\n".join(lines).rstrip())


def _do_search(query: str, max_results: int, region: str) -> list[dict]:
    """在线程池中同步执行搜索（DDGS 为同步 API）。"""
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS  # type: ignore[no-redef]
    with DDGS() as ddgs:
        return list(ddgs.text(query, region=region, max_results=max_results))
