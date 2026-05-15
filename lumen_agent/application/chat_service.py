"""用例编排：按 session 加载 summary + 最近原文 → 调 LLM → 落库 + 触发摘要。"""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from lumen_agent.application.summary_service import build_llm_messages, maybe_trigger_summary
from lumen_agent.config import Settings
from lumen_agent.domain.ports import ConversationRepositoryPort, LLMClientPort


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
    llm: LLMClientPort,
    session_id: str,
    user_message: str,
    settings: Settings,
) -> str:
    """处理单轮会话请求——整体输出。"""
    # 1) 会话准备 + 用户消息落库（不增 count）
    await repo.ensure_session(session_id)
    await repo.append_message(session_id, "user", user_message)

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
    await repo.append_message(session_id, "assistant", content)
    new_count = await repo.increment_round_counter(session_id)
    logging.info(f"session={session_id} 助手已落库 count={new_count}")
    # 后台异步触发摘要，不阻塞当前响应返回
    asyncio.create_task(maybe_trigger_summary(repo, llm, session_id, settings))

    return content


async def reply_single_turn_stream(
    repo: ConversationRepositoryPort,
    llm: LLMClientPort,
    session_id: str,
    user_message: str,
    settings: Settings,
) -> AsyncIterator[tuple[str, str]]:
    """处理单轮会话请求——流式输出，yield ``(kind, delta)``。"""
    # 1) 会话准备 + 用户消息落库
    await repo.ensure_session(session_id)
    await repo.append_message(session_id, "user", user_message)

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
        await repo.append_message(session_id, "assistant", accumulated)
        new_count = await repo.increment_round_counter(session_id)
        logging.info(f"session={session_id} 流式助手已落库 count={new_count}")
        asyncio.create_task(maybe_trigger_summary(repo, llm, session_id, settings))
