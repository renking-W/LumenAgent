"""用例编排：按 session 加载 summary + 最近原文 → 调 LLM → 落库 + 触发摘要。"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from lumen_agent.agent.tokens import get_token_counter
from lumen_agent.application.context_assembly import assemble_for_llm
from lumen_agent.application.service.summary_service import maybe_trigger_summary
from lumen_agent.application.title_service import maybe_generate_title
from lumen_agent.config import Settings
from lumen_agent.domain.messages import text_message
from lumen_agent.domain.ports import ConversationRepositoryPort
from lumen_agent.model_adapters.base import ModelAdapter, StreamHandleCallback


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
    counter = get_token_counter(settings.deepseek_model)
    context_window = settings.context_window_for(settings.deepseek_model)
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
    counter = get_token_counter(settings.deepseek_model)
    context_window = settings.context_window_for(settings.deepseek_model)
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
) -> AsyncIterator[tuple[str, Any]]:
    """用 Agent 工具循环处理会话请求——流式输出，yield ``(kind, data)``。

    kind 取值同 AgentStreamExecutor.run_stream()，包含工具执行事件。
    额外处理 ("new_messages", list[dict]) 事件：将 Agent 执行期间新产生的
    tool_use / tool_result / assistant 消息全部持久化到数据库。
    """
    from lumen_agent.agent.agent import AgentStreamExecutor
    from lumen_agent.agent.tools import init_tools
    from lumen_agent.agent.tools.registry import ToolRegistry
    from lumen_agent.agent.prompts.builder import build_system_prompt
    from lumen_agent.agent.skills import load_skills

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
    skills = load_skills()
    system_content = build_system_prompt(tools, skills)

    # 3) 组装上下文（含 token 预算检查 / 强制压缩）
    counter = get_token_counter(settings.deepseek_model)
    context_window = settings.context_window_for(settings.deepseek_model)
    ctx = await assemble_for_llm(
        repo, llm, settings,
        session_id=session_id,
        system_content=system_content or None,
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
        tools=tools,
        settings=settings,
    )

    # 5) 运行工具循环，处理事件流
    final_text = ""
    async for kind, data in executor.run_stream(messages, on_connect=on_connect):
        if kind == "new_messages":
            # 将 Agent 执行期间新产生的所有消息落库。
            # tool_result 原本以独立 role=user 消息存在，这里合并到前一条
            # assistant 消息内部嵌入存储，保证一个逻辑轮次 = 一条消息。
            new_msgs: list[dict[str, Any]] = data  # type: ignore[assignment]

            # ──Step 1: 合并 tool_result → 前一条 assistant ──────────
            merged: list[dict[str, Any]] = []
            for msg in new_msgs:
                role = msg.get("role", "")
                content = msg.get("content", [])
                if isinstance(content, list):
                    content = [b for b in content if isinstance(b, dict)]

                if (
                    role == "user"
                    and content
                    and all(b.get("type") == "tool_result" for b in content)
                ):
                    # tool_result 合并到前一条 assistant
                    if merged and merged[-1]["role"] == "assistant":
                        merged[-1]["content"].extend(content)
                    else:
                        merged.append({"role": "user", "content": content})
                elif role == "assistant":
                    # 连续 assistant 也合并（同一 agent 轮次内的多段回复）
                    if merged and merged[-1]["role"] == "assistant":
                        merged[-1]["content"].extend(content)
                    else:
                        merged.append({"role": "assistant", "content": list(content)})
                else:
                    merged.append({"role": role, "content": content})

            # ──Step 2: 兜底 — 孤立 tool_use 补 (interrupted) ──────
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

            # ──Step 3: 持久化 ──────────────────────────────────────
            for msg in merged:
                if not msg.get("content"):
                    continue
                await repo.append_message(session_id, msg["role"], msg["content"])
            # new_messages 事件不透传给前端
        elif kind == "done":
            final_text = data  # type: ignore[assignment]
            yield (kind, data)
        elif kind == "content":
            final_text += data  # type: ignore[operator]
            yield (kind, data)
        else:
            yield (kind, data)

    # 6) 轮次 +1（仅最终 assistant 回复落库后触发，tool 调用不计入）
    #    assistant 最终文本消息已由 new_messages 事件落库（agent 最后一条 assistant 消息）
    if final_text.strip():
        new_count = await repo.increment_round_counter(session_id)
        logging.info(f"[Agent] session={session_id} 工具循环结束 count={new_count}")
        asyncio.create_task(maybe_trigger_summary(repo, llm, session_id, settings))
