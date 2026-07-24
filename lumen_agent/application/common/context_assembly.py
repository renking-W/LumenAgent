"""上下文组装与 token 预算检查。

assemble_for_llm() 是所有入口（单轮 / 流式 / Agent）的统一历史拼接点：
  1. 从数据库取最近 N 条消息（FETCH_LIMIT = summary_threshold_turns × 10），避免 OOM
  2. 按完整轮次切分，校验首条消息为 user（丢弃残缺首轮）
  3. 只保留最近 10 轮完整对话，对 tool_result.content 做超长压缩
  4. 计算总 token；若超过 context_window * force_compress_ratio 则触发强制压缩后重拼
  5. 返回可直接送入 LLM 的 messages 列表
"""

from __future__ import annotations

import base64
import logging
import mimetypes
from dataclasses import dataclass
from typing import Any

from lumen_agent.agent.context import (
    compress_tool_blocks,
    extract_complete_turns,
    turns_to_messages,
)
from lumen_agent.agent.tokens import TokenCounter
from lumen_agent.application.uitls.dir_guide import DirGuide
from lumen_agent.config import Settings
from lumen_agent.domain.ports import ConversationRepositoryPort, LLMClientPort
from lumen_agent.domain.messages import file_block_to_text

logger = logging.getLogger(__name__)


def _prepare_image_block_for_llm(block: dict[str, Any]) -> dict[str, Any] | None:
    """将数据库中的本地图片引用转换成模型可直接读取的 Data URI。"""
    image_url = block.get("image_url")
    url = str(image_url.get("url") or "") if isinstance(image_url, dict) else ""
    if not url.startswith("/v1/files/"):
        return block

    filename = url.removeprefix("/v1/files/")
    # 本地图片名称只允许单层文件名，避免越权读取其他路径。
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        logger.warning("跳过非法图片路径：%s", url)
        return None

    file_path = DirGuide.tmp_dir() / filename
    try:
        data = file_path.read_bytes()
    except OSError:
        logger.warning("图片文件不存在或不可读，已跳过：%s", file_path)
        return None

    mime = mimetypes.guess_type(str(file_path))[0] or "image/jpeg"
    encoded = base64.b64encode(data).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{mime};base64,{encoded}"},
    }


def _prepare_history_for_llm(messages: list[dict]) -> list[dict]:
    """把数据库内容块转换成模型兼容格式，不修改持久化原始数据。"""
    prepared: list[dict] = []
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            prepared.append(message)
            continue

        blocks: list[dict[str, Any]] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "file":
                blocks.append(file_block_to_text(block))
            elif block.get("type") == "image_url":
                image_block = _prepare_image_block_for_llm(block)
                if image_block is not None:
                    blocks.append(image_block)
            else:
                blocks.append(block)
        prepared.append({**message, "content": blocks})
    return prepared


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
    counter         TokenCounter 实例
    context_window  当前模型的上下文窗口（token 数）

    返回
    ----
    AssembledContext，其 .messages 可直接传给 LLM / AgentStreamExecutor。
    """
    force_threshold = int(context_window * settings.get("CONTEXT_FORCE_COMPRESS_RATIO", 0.5))

    async def _build(after_compress: bool = False) -> AssembledContext:
        session = await repo.get_session(session_id)
        summary = (session.get("summary") or "") if session else ""

        # 只取最近 N 条消息而非全量
        fetch_limit = settings.get("SUMMARY_THRESHOLD_TURNS", 6)
        all_msgs = await repo.list_recent_messages(session_id, fetch_limit)

        turns = extract_complete_turns(all_msgs)
        # list_recent_messages 从末尾截取，首轮可能残缺，丢弃
        if turns and turns[0][0].get("role") != "user":
            turns.pop(0)
        # 修复历史中的残缺轮次；最后一条 User 消息由 verify_message 保持未完成状态。
        complete_turns = verify_message(turns)
        # 压缩 tool_result.content 超长内容
        history_msgs = compress_tool_blocks(
            turns_to_messages(complete_turns),
            counter,
            tool_result_token_limit=settings.get("TOOL_RESULT_COMPRESS_TOKEN_LIMIT", 2000),
            head_tail_chars=settings.get("TOOL_RESULT_HEAD_TAIL_CHARS", 20),
        )
        history_msgs = _prepare_history_for_llm(history_msgs)

        # 构建 messages：[system?] + [summary system?] + 数据库消息
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
        from lumen_agent.application.service.chat.summary_service import force_compress_now
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

def verify_message(turns: list[list[dict]]) -> list[list[dict]]:
    """校验并格式化消息。"""

    def _empty_assistant() -> dict:
        return {
            "role": "assistant",
            "content": [{"type": "text", "text": ""}],
        }

    complete_turns: list[list[dict]] = []
    for turn_index, turn in enumerate(turns):
        fixed_turn: list[dict] = []
        for idx, msg in enumerate(turn):
            fixed_turn.append(msg)
            is_last = idx == len(turn) - 1
            is_final_user = (
                turn_index == len(turns) - 1
                and is_last
                and msg.get("role") == "user"
            )
            next_is_assistant = (
                not is_last and turn[idx + 1].get("role") == "assistant"
            )
            if (
                msg.get("role") == "user"
                and (is_last or not next_is_assistant)
                and not is_final_user
            ):
                fixed_turn.append(_empty_assistant())
        complete_turns.append(fixed_turn)
    return complete_turns
