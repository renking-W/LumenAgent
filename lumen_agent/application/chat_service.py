"""用例编排：按 session 加载 summary + 最近原文 → 调 LLM → 落库 + 触发摘要。"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from lumen_agent.agent.tokens import get_token_counter
from lumen_agent.application.context_assembly import assemble_for_llm
from lumen_agent.application.summary_service import maybe_trigger_summary
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

    # 3) 调 LLM
    content = await llm.chat(messages)

    # 4) 助手消息落库 + 轮次 +1 + 摘要触发
    assistant_blocks = text_message("assistant", content)["content"]
    await repo.append_message(session_id, "assistant", assistant_blocks)
    new_count = await repo.increment_round_counter(session_id)
    logging.info(f"session={session_id} 助手已落库 count={new_count}")
    asyncio.create_task(maybe_trigger_summary(repo, llm, session_id, settings))

    return content


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

    # 3) 流式生成；只累加 content 部分落库，reasoning_content 透传但不入库
    accumulated = ""
    async for kind, chunk in llm.chat_stream(messages, on_connect=on_connect):
        if kind == "content":
            accumulated += chunk
        yield (kind, chunk)

    # 4) 正常结束：助手落库 + 轮次 +1 + 摘要触发
    if accumulated.strip():
        assistant_blocks = text_message("assistant", accumulated)["content"]
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
            # 将 Agent 执行期间新产生的所有消息（tool_use / tool_result / assistant）落库
            # 跳过已落库的 user 消息（assemble_for_llm 已过滤历史 user，本轮 user 在步骤 1 落库）
            new_msgs: list[dict[str, Any]] = data  # type: ignore[assignment]
            for msg in new_msgs:
                role = msg.get("role", "")
                content = msg.get("content", [])
                if not role or not content:
                    continue
                # 过滤掉 thinking 块（不持久化 thinking）
                if isinstance(content, list):
                    filtered = [
                        b for b in content
                        if isinstance(b, dict) and b.get("type") != "thinking"
                    ]
                    if not filtered:
                        continue
                    content = filtered
                await repo.append_message(session_id, role, content)
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
