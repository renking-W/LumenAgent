"""用例编排：按 session 从仓储取历史 → 调 LLM → 写回助手消息。"""

import logging
from collections.abc import AsyncIterator
from typing import Any

from lumen_agent.domain.ports import ConversationRepositoryPort, LLMClientPort



def _truncate_context(messages: list[dict[str, Any]], max_messages: int) -> list[dict[str, Any]]:
    """截取最近 N 条消息，供 LLM 上下文（库中仍保留全量）。"""
    if len(messages) <= max_messages:
        return list(messages)
    return messages[-max_messages:]


async def reply_single_turn(
    repo: ConversationRepositoryPort,
    llm: LLMClientPort,
    session_id: str,
    user_message: str,
    max_context_messages: int,
) -> str:
    """处理单轮会话请求——整体输出"""
    # 确保会话存在 && 添加用户消息
    await repo.ensure_session(session_id)
    await repo.append_message(session_id, "user", user_message)
    # 查找历史消息
    history = await repo.list_messages(session_id)
    logging.info(f"当前会话{session_id},查找到历史消息: {history}")

    messages = _truncate_context(history, max_context_messages)

    content = await llm.chat(messages)
    # 持久化当前消息
    await repo.append_message(session_id, "assistant", content)
    logging.info(f"当前会话{session_id},大模型返回结果：{content}")
    return content


async def reply_single_turn_stream(
    repo: ConversationRepositoryPort,
    llm: LLMClientPort,
    session_id: str,
    user_message: str,
    max_context_messages: int,
) -> AsyncIterator[str]:
    """处理单轮会话请求——流式输出"""
    # 确保会话存在 && 添加用户消息
    await repo.ensure_session(session_id)
    await repo.append_message(session_id, "user", user_message)
    # 查找历史消息
    history = await repo.list_messages(session_id)
    logging.info(f"当前会话{session_id},查找到历史消息: {history}")
    messages = _truncate_context(history, max_context_messages)
    accumulated = ""
    try:
        async for chunk in llm.chat_stream(messages):
            accumulated += chunk
            yield chunk
    except Exception:
        raise
    else:
        if accumulated.strip():
            logging.info(f"当前会话{session_id},大模型返回结果：{accumulated}")
            await repo.append_message(session_id, "assistant", accumulated)
