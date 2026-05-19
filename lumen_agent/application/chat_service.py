"""用例编排：按 session 加载 summary + 最近原文 → 调 LLM → 落库 + 触发摘要。"""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from lumen_agent.application.summary_service import build_llm_messages, maybe_trigger_summary
from lumen_agent.config import Settings
from lumen_agent.domain.messages import text_message
from lumen_agent.domain.ports import ConversationRepositoryPort
from lumen_agent.model_adapters.base import ModelAdapter


async def _load_context(
    repo: ConversationRepositoryPort,
    session_id: str,
) -> tuple[str, list[dict[str, Any]]]:
    """读取会话摘要 + 当前未摘要窗口的全部原文（含本轮已落库的 user）。"""
    session = await repo.get_session(session_id)
    if session is None:
        return "", []
    count = int(session["count"])

    recent = await repo.list_recent_messages(session_id, count)
    return session["summary"], recent


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

    # 2) 读 summary + 最近原文（recent 含本轮 user，需剥离避免重复）
    summary, recent = await _load_context(repo, session_id)
    history_recent = recent[:-1] if recent and recent[-1].get("role") == "user" else recent
    messages = build_llm_messages(summary, history_recent, user_message)
    logging.info(
        f"session={session_id} 上下文构建完成 summary={bool(summary)} recent={len(history_recent)}"
    )

    # 3) 调 LLM
    content = await llm.chat(messages)

    # 4) 助手消息落库 + 轮次 +1 + 摘要触发
    assistant_blocks = text_message("assistant", content)["content"]
    await repo.append_message(session_id, "assistant", assistant_blocks)
    new_count = await repo.increment_round_counter(session_id)
    logging.info(f"session={session_id} 助手已落库 count={new_count}")
    # 后台异步触发摘要，不阻塞当前响应返回
    asyncio.create_task(maybe_trigger_summary(repo, llm, session_id, settings))

    return content


async def reply_single_turn_stream(
    repo: ConversationRepositoryPort,
    llm: ModelAdapter,
    session_id: str,
    user_message: str,
    settings: Settings,
) -> AsyncIterator[tuple[str, str]]:
    """处理单轮会话请求——流式输出，yield ``(kind, delta)``。"""
    # 1) 会话准备 + 用户消息落库
    await repo.ensure_session(session_id)
    user_blocks = text_message("user", user_message)["content"]
    await repo.append_message(session_id, "user", user_blocks)

    # 2) 读 summary + 最近原文，剥离本轮 user
    summary, recent = await _load_context(repo, session_id)
    history_recent = recent[:-1] if recent and recent[-1].get("role") == "user" else recent
    messages = build_llm_messages(summary, history_recent, user_message)
    logging.info(
        f"session={session_id} 流式上下文构建完成 summary={bool(summary)} recent={len(history_recent)}"
    )

    # 3) 流式生成；只累加 content 部分落库，reasoning_content 透传但不入库
    accumulated = ""
    async for kind, chunk in llm.chat_stream(messages):
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
) -> AsyncIterator[tuple[str, Any]]:
    """用 Agent 工具循环处理会话请求——流式输出，yield ``(kind, data)``。

    kind 取值同 AgentStreamExecutor.run_stream()，包含工具执行事件。
    """
    from lumen_agent.agent.agent import AgentStreamExecutor
    from lumen_agent.agent.tools import init_tools
    from lumen_agent.agent.tools.registry import ToolRegistry
    from lumen_agent.prompts.builder import build_system_prompt

    # 确保工具已注册（幂等，多次调用无副作用）
    init_tools()

    # 1) 会话准备 + 用户消息落库
    await repo.ensure_session(session_id)
    user_blocks = text_message("user", user_message)["content"]
    await repo.append_message(session_id, "user", user_blocks)

    # 2) 加载历史（summary + recent），剥离本轮 user（已在上面落库）
    summary, recent = await _load_context(repo, session_id)
    history_recent = recent[:-1] if recent and recent[-1].get("role") == "user" else recent
    messages = build_llm_messages(summary, history_recent, user_message)

    # 3) 构建 system 提示词并注入到消息首位
    tools = ToolRegistry.create_all_tools()
    system_content = build_system_prompt(tools)
    if system_content:
        messages = [{"role": "system", "content": system_content}] + messages

    logging.info(
        f"[Agent] session={session_id} 上下文构建完成 "
        f"summary={bool(summary)} recent={len(history_recent)}"
    )

    # 4) 创建 AgentStreamExecutor
    executor = AgentStreamExecutor(
        adapter=llm,
        tools=tools,
        settings=settings,
    )

    # 5) 运行工具循环，收集最终回复文本
    final_text = ""
    async for kind, data in executor.run_stream(messages):
        if kind == "done":
            final_text = data  # type: ignore[assignment]
        elif kind == "content":
            final_text += data  # type: ignore[operator]
        yield (kind, data)

    # 6) 助手最终回复落库 + 轮次 +1 + 摘要触发
    if final_text.strip():
        assistant_blocks = text_message("assistant", final_text)["content"]
        await repo.append_message(session_id, "assistant", assistant_blocks)
        new_count = await repo.increment_round_counter(session_id)
        logging.info(f"[Agent] session={session_id} 助手已落库 count={new_count}")
        asyncio.create_task(maybe_trigger_summary(repo, llm, session_id, settings))
