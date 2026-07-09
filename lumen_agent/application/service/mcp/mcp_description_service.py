"""MCP Server description 自动生成：基于 mcp_tools 工具描述 + 可选用户参考。

流程（由 mcp_server_service / mcp_stdio_server_service 编排）：
1. 首次 sync 将远程 tools 写入 mcp_tools 表
2. 本模块读取 tools → 调 LLM 生成固定格式描述（≤400 字）
3. 写回 mcp_servers / mcp_stdio_servers.description
4. 二次 sync 刷新 Chroma search_doc 中的 [server_note] 行
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from lumen_agent.application.service.mcp.mcp_tool_sync_service import McpToolSyncService
from lumen_agent.application.uitls.dir_guide import DirGuide
from lumen_agent.config import Settings, get_settings, resolve_db_path
from lumen_agent.infrastructure.data_base.sqlite_mcp import SqliteMCPServerRepository
from lumen_agent.infrastructure.data_base.sqlite_mcp_stdio import SqliteMCPStdioServerRepository
from lumen_agent.infrastructure.data_base.sqlite_mcp_tools import SqliteMCPToolRepository
from lumen_agent.model_adapters.base import ModelAdapter

_logger = logging.getLogger(__name__)

_PROMPT_PATH = DirGuide.mcp_server_description_prompt_path()


@lru_cache(maxsize=1)
def _load_prompt_template() -> str:
    """读取 MCP 描述生成 prompt 模板（进程内只读一次）。"""
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _format_tool_descriptions(tools: list[dict[str, Any]]) -> str:
    """将 mcp_tools 行格式化为 prompt 所需的「工具名: 描述」列表。"""
    if not tools:
        # disabled / sync 失败 / 0 工具时仍走 LLM，但无工具细节可引用
        return "（暂无已索引工具）"
    lines: list[str] = []
    for tool in tools:
        name = tool.get("original_name") or tool.get("name") or "unknown"
        desc = (tool.get("description") or "").strip() or "（无描述）"
        lines.append(f"{name}: {desc}")
    return "\n".join(lines)


def _render_prompt(
    *,
    server_name: str,
    server_kind: str,
    user_hint: str | None,
    tools: list[dict[str, Any]],
) -> str:
    """用 str.replace 填充 prompt 占位符（与 title_service 保持一致）。"""
    tpl = _load_prompt_template()
    tpl = tpl.replace("{{server_name}}", server_name)
    tpl = tpl.replace("{{server_kind}}", server_kind)
    tpl = tpl.replace("{{user_hint}}", (user_hint or "").strip() or "无")
    tpl = tpl.replace("{{tool_descriptions}}", _format_tool_descriptions(tools))
    return tpl

def _fallback_description(
    *,
    server_name: str,
    server_kind: str,
    user_hint: str | None,
    tool_count: int,
) -> str:
    """LLM 不可用或生成失败时的固定格式兜底，不阻塞 CRUD。"""
    hint = (user_hint or "").strip()
    base = (
        f"【名称】{server_name}\n"
        f"【类型】{server_kind}\n"
        f"【能力】基于 {tool_count} 个工具的外部 MCP 服务"
    )
    if hint:
        base += f"；{hint}"
    base += "\n【场景】按需通过 mcp_search 发现具体工具后调用\n【备注】无"
    return base


async def generate_server_description(
    llm: ModelAdapter,
    *,
    server_name: str,
    server_kind: str,
    user_hint: str | None,
    tools: list[dict[str, Any]],
) -> str:
    """调用 LLM 生成固定格式的 server description（≤400 字）。

    user_hint 来自用户在前端填写的「描述（可选）」，仅作生成参考，
    不会原样写入 DB；最终 description 由 LLM 按模板输出。
    """
    prompt = _render_prompt(
        server_name=server_name,
        server_kind=server_kind,
        user_hint=user_hint,
        tools=tools,
    )
    # 占位符残留说明模板与代码不同步，直接 fallback
    if "{{server_name}}" in prompt or "{{server_kind}}" in prompt or "{{tool_descriptions}}" in prompt or "{{user_hint}}" in prompt:
        _logger.error("MCP description prompt 占位符未完全替换")
        return _fallback_description(
            server_name=server_name,
            server_kind=server_kind,
            user_hint=user_hint,
            tool_count=len(tools),
        )

    try:
        raw = await llm.chat(
            [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        )
        text = (raw or "").strip()
        if text:
            return text
    except Exception:
        _logger.exception("MCP Server %s description LLM 生成失败", server_name)

    return _fallback_description(
        server_name=server_name,
        server_kind=server_kind,
        user_hint=user_hint,
        tool_count=len(tools),
    )


async def refresh_server_description_after_sync(
    llm: ModelAdapter | None,
    settings: Settings | None,
    *,
    server_kind: str,
    server_id: str,
    server_name: str,
    user_hint: str | None,
    resync: bool = True,
) -> str:
    """读取已索引 tools → 生成 description → 写库 → 可选二次 sync。

    二次 sync 目的：McpToolSyncService 会把 server description 写入
    每个 tool 的 search_doc（[server_note]），供 mcp_search 向量检索使用。
    """
    settings = settings or get_settings()
    db_path = resolve_db_path(settings)
    tool_repo = SqliteMCPToolRepository(db_path)
    tools = await tool_repo.list_all(server_kind=server_kind, server_id=server_id)

    if llm is not None:
        description = await generate_server_description(
            llm,
            server_name=server_name,
            server_kind=server_kind,
            user_hint=user_hint,
            tools=tools,
        )
    else:
        # 路由未注入 LLM 时（理论上不应发生）仍保证有可读描述
        description = _fallback_description(
            server_name=server_name,
            server_kind=server_kind,
            user_hint=user_hint,
            tool_count=len(tools),
        )

    if server_kind == "http":
        repo = SqliteMCPServerRepository(db_path)
    else:
        repo = SqliteMCPStdioServerRepository(db_path)
    await repo.update(server_id, {"description": description})

    # 有工具时才二次 sync，避免空 server 无意义重连
    if resync and tools:
        try:
            await McpToolSyncService(settings).sync_server(server_kind, server_id)
        except Exception:
            _logger.exception(
                "MCP Server %s description 更新后二次 sync 失败", server_id
            )

    _logger.info(
        "MCP Server %s description 已生成（%d 字，%d 个工具）",
        server_name,
        len(description),
        len(tools),
    )
    return description
