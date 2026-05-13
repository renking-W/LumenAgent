"""应用层（用例编排）：把「用户一句话」翻译成「模型多轮 messages」并调用端口。

为什么要有这一层？
- **路由层（api）**应该尽量只做：参数校验/鉴权/错误码映射/OpenAPI 形状。
- **领域端口（domain/ports）**描述能力：例如 `LLMClientPort.chat(messages)`。
- **应用层（application）**负责把业务动作编排成对端口的调用：例如单轮对话、加载会话历史、
  写入记忆、触发工具循环等（当前仅实现最小单轮）。

这样拆分后：
- 单测可以只测 `reply_single_turn()`，注入 fake `LLMClientPort`，无需启动 FastAPI。
- 未来加 session 历史时，主要改这里，而不是让 `session_dtos` 越来越胖。
"""

from collections.abc import AsyncIterator
from typing import Any

from lumen_agent.domain.ports import LLMClientPort


async def reply_single_turn(llm: LLMClientPort, user_message: str) -> str:
    """最小单轮对话：仅包含一条 user 消息。

    Args:
        llm: 任意满足 `LLMClientPort` 的实现（当前为 `DeepSeekHttpClient`）。
        user_message: 用户输入文本（路由层已通过 Pydantic 做最小长度校验）。

    Returns:
        助手回复文本（由 LLM 客户端解析上游 JSON 得到）。

    后续演进（对照开发指南）：
    - 若提供 `session_id`：在此加载历史 messages 再 append 当前 user。
    - 若接入 system prompt：在此插入 `{"role":"system","content":...}`。
    """
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
    return await llm.chat(messages)


async def reply_single_turn_stream(
    llm: LLMClientPort,
    user_message: str,
) -> AsyncIterator[str]:
    """单轮流式：与 `reply_single_turn` 相同的 messages，经 `chat_stream` 产出文本增量。"""
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
    async for chunk in llm.chat_stream(messages):
        yield chunk
