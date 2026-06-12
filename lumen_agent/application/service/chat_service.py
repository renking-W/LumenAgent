"""用例编排：按 session 加载 summary + 最近原文 → 调 LLM → 落库 + 触发摘要。"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from lumen_agent.agent.tokens import get_token_counter
from lumen_agent.application.common.context_assembly import assemble_for_llm
from lumen_agent.application.service.summary_service import maybe_trigger_summary
from lumen_agent.application.service.title_service import maybe_generate_title
from lumen_agent.config import Settings, get_context_window
from lumen_agent.domain.messages import text_message
from lumen_agent.domain.ports import ConversationRepositoryPort
from lumen_agent.model_adapters.base import ModelAdapter, StreamHandleCallback


async def merge_and_persist_messages(
    repo: ConversationRepositoryPort,
    session_id: str,
    new_messages: list[dict[str, Any]],
) -> None:
    """合并、回填并持久化 Agent 工具循环产生的新消息。

    处理内容：
    1. 将 tool_result 与前面的 assistant 消息合并（避免存储冗余的"用户"角色消息）
    2. 回填没有 tool_result 的孤立 tool_use 的 (interrupted)
    3. 将合并后的每条消息写入 DB
    """
    # Step 1: 将 tool_result 与前面的 assistant 合并
    merged: list[dict[str, Any]] = []
    for msg in new_messages:
        role = msg.get("role", "")
        content = msg.get("content", [])
        if isinstance(content, list):
            content = [b for b in content if isinstance(b, dict)]

        if (
            role == "user"
            and content
            and all(b.get("type") == "tool_result" for b in content)
        ):
            if merged and merged[-1]["role"] == "assistant":
                merged[-1]["content"].extend(content)
            else:
                merged.append({"role": "user", "content": content})
        elif role == "assistant":
            if merged and merged[-1]["role"] == "assistant":
                merged[-1]["content"].extend(content)
            else:
                merged.append({"role": "assistant", "content": list(content)})
        else:
            merged.append({"role": role, "content": content})

    # Step 2: 兜底 — 孤立 tool_use 补 (interrupted)
    for msg in merged:
        if msg["role"] != "assistant":
            continue
        use_ids = {
            b["id"] for b in msg["content"]
            if b.get("type") == "tool_use" and b.get("id")
        }
        result_ids = {
            b["tool_use_id"] for b in msg["content"]
            if b.get("type") == "tool_result" and b.get("tool_use_id")
        }
        for tid in use_ids - result_ids:
            msg["content"].append({
                "type": "tool_result",
                "tool_use_id": tid,
                "content": "(interrupted)",
                "is_error": True,
            })

    # Step 3: 持久化
    for msg in merged:
        if not msg.get("content"):
            continue
        await repo.append_message(session_id, msg["role"], msg["content"])


async def reply_single_turn(
    repo: ConversationRepositoryPort,
    llm: ModelAdapter,
    session_id: str,
    user_message: str,
    settings: Settings,
) -> str:
    """处理单轮会话请求——整体输出。"""
    # 1) 会话准备 + 用户消息落库（不增 count）
    await repo.ensure_session(session_id)
    user_blocks = text_message("user", user_message)["content"]
    await repo.append_message(session_id, "user", user_blocks)

    # 异步生成会话标题（仅首次消息触发）
    asyncio.create_task(maybe_generate_title(repo, llm, session_id, user_message))

    # 2) 组装上下文（含 token 预算检查 / 强制压缩）
    counter = get_token_counter(settings.get("DEEPSEEK_MODEL", "deepseek-v4-flash"))
    context_window = get_context_window(settings, settings.get("DEEPSEEK_MODEL", "deepseek-v4-flash"))
    ctx = await assemble_for_llm(
        repo, llm, settings,
        session_id=session_id,
        system_content=None,
        user_message=user_message,
        counter=counter,
        context_window=context_window,
    )
    # 移除列表末尾自动追加的 user 消息（assemble_for_llm 已包含），直接使用
    messages = ctx.messages
    logging.info(
        f"session={session_id} 上下文构建完成 summary={bool(ctx.summary_used)} "
        f"kept_turns={ctx.kept_turns} total_tokens={ctx.total_tokens} "
        f"force_compressed={ctx.force_compressed}"
    )

    # 3) 调 LLM（返回含 thinking 的 content blocks）
    assistant_blocks = await llm.chat_blocks(messages)

    # 4) 助手消息落库 + 轮次 +1 + 摘要触发
    # assistant_blocks 已包含 text + thinking 块
    await repo.append_message(session_id, "assistant", assistant_blocks)
    new_count = await repo.increment_round_counter(session_id)
    logging.info(f"session={session_id} 助手已落库 count={new_count}")
    asyncio.create_task(maybe_trigger_summary(repo, llm, session_id, settings))

    # 返回纯文本给 API 层（不含 thinking 块）
    return next((b["text"] for b in assistant_blocks if b.get("type") == "text"), "")


async def reply_single_turn_stream(
    repo: ConversationRepositoryPort,
    llm: ModelAdapter,
    session_id: str,
    user_message: str,
    settings: Settings,
    on_connect: StreamHandleCallback | None = None,
) -> AsyncIterator[tuple[str, str]]:
    """处理单轮会话请求——流式输出，yield ``(kind, delta)``。

    参数:
        on_connect: 连接建立后的回调，传递 ``StreamHandle`` 供注册到中断注册表。
    """
    # 1) 会话准备 + 用户消息落库
    await repo.ensure_session(session_id)
    user_blocks = text_message("user", user_message)["content"]
    await repo.append_message(session_id, "user", user_blocks)

    # 异步生成会话标题（仅首次消息触发）
    asyncio.create_task(maybe_generate_title(repo, llm, session_id, user_message))

    # 2) 组装上下文
    counter = get_token_counter(settings.get("DEEPSEEK_MODEL", "deepseek-v4-flash"))
    context_window = get_context_window(settings, settings.get("DEEPSEEK_MODEL", "deepseek-v4-flash"))
    ctx = await assemble_for_llm(
        repo, llm, settings,
        session_id=session_id,
        system_content=None,
        user_message=user_message,
        counter=counter,
        context_window=context_window,
    )
    messages = ctx.messages
    logging.info(
        f"session={session_id} 流式上下文构建完成 summary={bool(ctx.summary_used)} "
        f"kept_turns={ctx.kept_turns} total_tokens={ctx.total_tokens} "
        f"force_compressed={ctx.force_compressed}"
    )

    # 3) 流式生成；累加 content + reasoning_content 用于落库
    accumulated = ""
    accumulated_thinking = ""
    async for kind, chunk in llm.chat_stream(messages, on_connect=on_connect):
        if kind == "content":
            accumulated += chunk
        elif kind == "reasoning_content":
            accumulated_thinking += chunk
        yield (kind, chunk)

    # 4) 正常结束：助手落库（含 thinking 块）+ 轮次 +1 + 摘要触发
    if accumulated.strip() or accumulated_thinking.strip():
        assistant_blocks: list[dict[str, Any]] = []
        if accumulated_thinking.strip():
            assistant_blocks.append({"type": "thinking", "thinking": accumulated_thinking})
        if accumulated.strip():
            assistant_blocks.append({"type": "text", "text": accumulated})
        await repo.append_message(session_id, "assistant", assistant_blocks)
        new_count = await repo.increment_round_counter(session_id)
        logging.info(f"session={session_id} 流式助手已落库 count={new_count}")
        asyncio.create_task(maybe_trigger_summary(repo, llm, session_id, settings))


async def reply_with_agent(
    repo: ConversationRepositoryPort,
    llm: ModelAdapter,
    session_id: str,
    user_message: str,
    settings: Settings,
    on_connect: StreamHandleCallback | None = None,
    mcp_servers: list[Any] | None = None,
    mcp_server_ids: list[str] | None = None,
) -> AsyncIterator[tuple[str, Any]]:
    """用 Agent 工具循环处理会话请求——流式输出，yield ``(kind, data)``。

    kind 取值同 AgentStreamExecutor.run_stream()，包含工具执行事件。
    额外处理 ("new_messages", list[dict]) 事件：将 Agent 执行期间新产生的
    tool_use / tool_result / assistant 消息全部持久化到数据库。

    参数:
        mcp_servers: 可选，外部 MCP Server 列表，仅 agent 模式下生效。
    """
    from lumen_agent.agent.agent import AgentStreamExecutor
    from lumen_agent.agent.tools import init_tools
    from lumen_agent.agent.tools.registry import ToolRegistry
    from lumen_agent.agent.tools.mcp_bridge import MCPBridgeTool
    from lumen_agent.agent.prompts.builder import build_system_prompt
    from lumen_agent.agent.skills import load_skills
    from lumen_agent.infrastructure.client.mcp_client import get_mcp_manager

    # 确保工具已注册（幂等）
    init_tools()

    # 1) 会话准备 + 用户消息落库
    await repo.ensure_session(session_id)
    user_blocks = text_message("user", user_message)["content"]
    await repo.append_message(session_id, "user", user_blocks)

    # 异步生成会话标题（仅首次消息触发）
    asyncio.create_task(maybe_generate_title(repo, llm, session_id, user_message))

    # 2) 构建 system 提示词
    tools = ToolRegistry.create_all_tools()

    # ── MCP 工具发现与加载 ─────────────────────────────────────
    mcp_tools: list[Any] = []

    # a) 从全局 MCP 管理器获取已连接的连接
    # 仅当前端通过 mcp_server_ids 明确指定时，才加载对应 MCP Server 的工具
    # 不传 mcp_server_ids 或传 None → 不加载任何 MCP 工具
    global_mgr = get_mcp_manager()
    if mcp_server_ids:
        for sid in mcp_server_ids:
            conn = global_mgr.get_connection(sid)
            if conn is None:
                logging.warning("MCP Server %s 未连接或不存在，已跳过", sid)
                continue
            try:
                remote_tool_defs = await conn.list_tools()
                for td in remote_tool_defs:
                    mcp_tools.append(MCPBridgeTool(td, conn, sid))
                logging.info("MCP Server %s 加载了 %d 个工具", sid, len(remote_tool_defs))
            except Exception:
                logging.warning("MCP Server %s 获取工具列表失败，已跳过", sid, exc_info=True)

    # b) 动态传入的 mcp_servers（临时连接）
    temp_connections: list[Any] = []
    if mcp_servers:
        for config in mcp_servers:
            url = config.url if hasattr(config, "url") else config.get("url", "")
            api_key = (
                config.api_key
                if hasattr(config, "api_key")
                else config.get("api_key")
            )
            try:
                from lumen_agent.infrastructure.client.mcp_client import MCPConnection
                conn = MCPConnection(url, api_key)
                await conn.connect()
                temp_connections.append(conn)
                remote_tool_defs = await conn.list_tools()
                for td in remote_tool_defs:
                    mcp_tools.append(MCPBridgeTool(td, conn, url))
                logging.info("动态 MCP Server %s 加载了 %d 个工具", url, len(remote_tool_defs))
            except Exception:
                logging.warning("动态 MCP Server %s 连接失败，已跳过", url, exc_info=True)

    all_tools = tools + mcp_tools
    skills = load_skills()
    system_content = build_system_prompt(all_tools, skills) or None

    try:
        # 3) 组装上下文（含 token 预算检查 / 强制压缩）
        counter = get_token_counter(settings.get("DEEPSEEK_MODEL", "deepseek-v4-flash"))
        context_window = get_context_window(settings, settings.get("DEEPSEEK_MODEL", "deepseek-v4-flash"))
        ctx = await assemble_for_llm(
            repo, llm, settings,
            session_id=session_id,
            system_content=system_content,
            user_message=user_message,
            counter=counter,
            context_window=context_window,
        )
        messages = ctx.messages
        logging.info(
            f"[Agent] session={session_id} 上下文构建完成 "
            f"summary={bool(ctx.summary_used)} kept_turns={ctx.kept_turns} "
            f"total_tokens={ctx.total_tokens} force_compressed={ctx.force_compressed}"
        )

        # 4) 创建 AgentStreamExecutor
        executor = AgentStreamExecutor(
            adapter=llm,
            tools=all_tools,
            settings=settings,
        )

        # 5) 运行工具循环，处理事件流
        final_text = ""
        async for kind, data in executor.run_stream(messages, on_connect=on_connect):
            if kind == "new_messages":
                await merge_and_persist_messages(repo, session_id, data)  # type: ignore[arg-type]
            elif kind == "done":
                final_text = data  # type: ignore[assignment]
                yield (kind, data)
            elif kind == "content":
                final_text += data  # type: ignore[operator]
                yield (kind, data)
            else:
                yield (kind, data)

        # 6) 轮次 +1
        if final_text.strip():
            new_count = await repo.increment_round_counter(session_id)
            logging.info(f"[Agent] session={session_id} 工具循环结束 count={new_count}")
            asyncio.create_task(maybe_trigger_summary(repo, llm, session_id, settings))

    finally:
        # 只清理临时连接的 MCP，全局管理器由 lifespan 管理
        for conn in temp_connections:
            await conn.close()
