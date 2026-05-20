"""上下文组装与 token 预算检查。

assemble_for_llm() 是所有入口（单轮 / 流式 / Agent）的统一历史拼接点：
  1. 从数据库取全部历史消息
  2. 按完整轮次切分
  3. 对 tool_result.content 做超长压缩
  4. 计算总 token；若超过 context_window * force_compress_ratio 则触发强制压缩后重拼
  5. 返回可直接送入 LLM 的 messages 列表
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from lumen_agent.agent.context import (
    compress_tool_blocks,
    extract_complete_turns,
    turns_to_messages,
)
from lumen_agent.agent.tokens import TokenCounter
from lumen_agent.config import Settings
from lumen_agent.domain.ports import ConversationRepositoryPort, LLMClientPort

logger = logging.getLogger(__name__)


@dataclass
class AssembledContext:
    """assemble_for_llm() 的返回值。"""

    messages: list[dict[str, Any]]
    """最终送入 LLM 的 messages（含 system、history、本轮 user）。"""

    summary_used: str
    """本次拼接所使用的会话摘要（空字符串表示无摘要）。"""

    kept_turns: int
    """保留的完整历史轮次数。"""

    force_compressed: bool = False
    """是否在本次请求中触发了强制压缩。"""

    total_tokens: int = 0
    """拼接后估算的总 token 数（含 system）。"""


async def assemble_for_llm(
    repo: ConversationRepositoryPort,
    llm: LLMClientPort,
    settings: Settings,
    *,
    session_id: str,
    system_content: str | None,
    user_message: str,
    counter: TokenCounter,
    context_window: int,
) -> AssembledContext:
    """组装本轮 LLM 输入消息，含 token 预算检查与强制压缩。

    参数
    ----
    repo            会话数据库端口
    llm             LLM 客户端端口（force_compress_now 会用到）
    settings        应用配置
    session_id      当前会话 ID
    system_content  系统提示词字符串（None 表示不注入 system 消息）
    user_message    本轮用户输入（已落库，不再重复写入）
    counter         TokenCounter 实例
    context_window  当前模型的上下文窗口（token 数）

    返回
    ----
    AssembledContext，其 .messages 可直接传给 LLM / AgentStreamExecutor。
    """
    force_threshold = int(context_window * settings.context_force_compress_ratio)

    async def _build(after_compress: bool = False) -> AssembledContext:
        session = await repo.get_session(session_id)
        summary = (session.get("summary") or "") if session else ""

        all_msgs = await repo.list_messages(session_id)

        turns = extract_complete_turns(all_msgs)
        # 去掉不含 assistant 回复的尾部不完整轮次
        complete_turns = [t for t in turns if any(m.get("role") == "assistant" for m in t)]

        # 压缩 tool_result.content 超长内容
        history_msgs = compress_tool_blocks(
            turns_to_messages(complete_turns),
            counter,
            tool_result_token_limit=settings.tool_result_compress_token_limit,
            head_tail_chars=settings.tool_result_head_tail_chars,
        )

        # 构建 messages：[system?] + [summary system?] + history + user
        messages: list[dict[str, Any]] = []

        if system_content:
            messages.append({"role": "system", "content": system_content})

        if summary:
            messages.append(
                {
                    "role": "system",
                    "content": [{"type": "text", "text": f"会话摘要：\n{summary}"}],
                }
            )

        messages.extend(history_msgs)
        messages.append(
            {"role": "user", "content": [{"type": "text", "text": user_message}]}
        )

        total_tokens = counter.count_messages(messages)

        return AssembledContext(
            messages=messages,
            summary_used=summary,
            kept_turns=len(complete_turns),
            force_compressed=after_compress,
            total_tokens=total_tokens,
        )

    ctx = await _build()

    if ctx.total_tokens > force_threshold:
        logger.warning(
            "[ContextAssembly] session=%s total_tokens=%d > threshold=%d，触发强制压缩",
            session_id, ctx.total_tokens, force_threshold,
        )
        from lumen_agent.application.summary_service import force_compress_now
        await force_compress_now(
            repo, llm, settings,
            session_id=session_id,
            keep_last_turn=True,
        )
        ctx = await _build(after_compress=True)
        logger.info(
            "[ContextAssembly] session=%s 强制压缩后 total_tokens=%d",
            session_id, ctx.total_tokens,
        )
    else:
        logger.info(
            "[ContextAssembly] session=%s total_tokens=%d kept_turns=%d",
            session_id, ctx.total_tokens, ctx.kept_turns,
        )

    return ctx
