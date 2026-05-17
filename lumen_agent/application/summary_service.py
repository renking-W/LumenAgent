"""滑动窗口摘要：构建 LLM 上下文 + 触发与生成新摘要。"""

from __future__ import annotations

import logging
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from lumen_agent.config import Settings
from lumen_agent.domain.ports import ConversationRepositoryPort, LLMClientPort

# prompt 模板路径：与代码同包根，方便随包发布
_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "summary.md"

_ROLE_LABEL = {"user": "用户", "assistant": "助手", "system": "系统", "tool": "工具"}


@lru_cache(maxsize=1)
def _load_prompt_template() -> str:
    """读取摘要 prompt 模板（进程内只读一次）。"""
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _format_rounds(messages: list[dict[str, Any]]) -> str:
    """把多条 ``role/content`` 拼成给 LLM 看的多轮对话文本。"""
    lines: list[str] = []
    for m in messages:
        role = _ROLE_LABEL.get(m.get("role", ""), m.get("role", ""))
        content = m.get("content", [])
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    parts.append(block["text"])
                elif block.get("type") == "thinking" and isinstance(block.get("thinking"), str):
                    parts.append(block["thinking"])
                elif block.get("type") == "tool_result" and isinstance(block.get("content"), str):
                    parts.append(block["content"])
            text = "".join(parts)
        else:
            text = str(content)
        lines.append(f"{role}：{text}")
    return "\n".join(lines)


def _render_summary_prompt(old_summary: str, rounds_text: str) -> str:
    """用 ``str.replace`` 填充 prompt 三个占位符（``new_summary`` 置空待 LLM 生成）。"""
    tpl = _load_prompt_template()
    tpl = tpl.replace("{{old_summary}}", old_summary or "")
    tpl = tpl.replace("{{seven_rounds_conversations}}", rounds_text or "")
    tpl = tpl.replace("{{new_summary}}", "")
    return tpl


def _find_complete_turns(
    msgs: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """从顺序消息列表中提取完整的 (user, assistant) 轮次对。

    跳过不成对的消息（如仅 user 无 assistant），确保每轮都是完整的一问一答。
    """
    turns: list[tuple[dict[str, Any], dict[str, Any]]] = []
    i = 0
    while i < len(msgs):
        if (
            msgs[i].get("role") == "user"
            and i + 1 < len(msgs)
            and msgs[i + 1].get("role") == "assistant"
        ):
            turns.append((msgs[i], msgs[i + 1]))
            i += 2
        else:
            i += 1
    return turns


def _message_to_text(message: dict[str, Any]) -> str:
    content = message.get("content", [])
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                parts.append(block["text"])
            elif block.get("type") == "thinking" and isinstance(block.get("thinking"), str):
                parts.append(block["thinking"])
            elif block.get("type") == "tool_result" and isinstance(block.get("content"), str):
                parts.append(block["content"])
        return "".join(parts)
    return str(content)


def _write_memory_file(
    session_id: str,
    messages: list[dict[str, Any]],
    db_path: Path,
) -> None:
    """将被强制截断的消息追加写入按日期命名的记忆文件（``YYYY-MM-DD.md``）。

    文件不存在则创建，已存在则追加；每次写入前带时间戳头部。
    """
    memory_dir = db_path.parent / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    file_path = memory_dir / f"{date_str}.md"

    parts: list[str] = [
        f"## {time_str}  session={session_id}（强制截断记录）\n\n",
    ]
    for msg in messages:
        label = _ROLE_LABEL.get(msg.get("role", ""), msg.get("role", ""))
        parts.append(f"**{label}**: {_message_to_text(msg)}\n\n")
    parts.append("---\n\n")

    with open(file_path, "a", encoding="utf-8") as f:
        f.write("".join(parts))

    logging.info(f"session={session_id} 截断记录已写入 {file_path}")


def build_llm_messages(
    summary: str,
    recent: list[dict[str, Any]],
    user_message: str,
) -> list[dict[str, Any]]:
    """拼装本轮调 LLM 的 messages：可选 system summary + 最近原始消息 + 本轮 user。"""
    msgs: list[dict[str, Any]] = []
    if summary:
        msgs.append({"role": "system", "content": [{"type": "text", "text": f"会话摘要：\n{summary}"}]})
    msgs.extend(recent)
    msgs.append({"role": "user", "content": [{"type": "text", "text": user_message}]})
    return msgs


async def maybe_trigger_summary(
    repo: ConversationRepositoryPort,
    llm: LLMClientPort,
    session_id: str,
    settings: Settings,
) -> None:
    """若当前 ``count`` 已达阈值，则压缩前 K 轮为新摘要并把 ``count`` 重置为 ``keep_turns``。

    失败不抛：仅记录日志、保持原状态，等下一轮再尝试（与指南边界约定一致）。
    """
    threshold = settings.summary_threshold_turns
    compress_turns = settings.summary_compress_turns
    keep_turns = settings.summary_keep_turns

    session = await repo.get_session(session_id)
    if session is None:
        return

    count = int(session["count"])

    # ── 兜底：摘要持续失败，count 到达 threshold*2 ──────────────────────────
    # 将溢出的轮次写入记忆文件，然后强制重置 count，防止上下文无限膨胀
    if count >= threshold * 2:
        logging.warning(
            f"session={session_id} 摘要持续失败 count={count}，"
            f"触发强制截断，溢出内容写入记忆文件"
        )
        # 取当前窗口全部消息，提取完整轮次
        all_window = await repo.list_recent_messages(session_id, count * 2)
        turns = _find_complete_turns(all_window)
        # 保留最近 keep_turns 轮，其余写入记忆文件
        lost_turns = turns[:-keep_turns] if len(turns) > keep_turns else []
        if lost_turns:
            lost_msgs = [msg for pair in lost_turns for msg in pair]
            try:
                _write_memory_file(
                    session_id,
                    lost_msgs,
                    settings.conversation_db_path_resolved(),
                )
            except Exception:
                logging.exception(f"session={session_id} 写入记忆文件失败，跳过")
        await repo.update_summary(
            session_id,
            new_summary=session["summary"],
            new_count=keep_turns,
        )
        return

    if count < threshold:
        return

    # ── 正常摘要触发 ─────────────────────────────────────────────────────────
    try:
        # 取当前会话全部消息，按完整 (user, assistant) 轮次切片，避免在轮次中间截断
        all_msgs = await repo.list_messages(session_id)
        turns = _find_complete_turns(all_msgs)

        if len(turns) < threshold:
            logging.warning(
                f"session={session_id} 触发摘要但完整轮次不足"
                f"（expect={threshold} got={len(turns)}），跳过"
            )
            return

        # 前 compress_turns 轮压缩为摘要
        to_compress = [msg for pair in turns[:compress_turns] for msg in pair]
        rounds_text = _format_rounds(to_compress)

        # 渲染 prompt（含文件读取），放在 try 块内以确保异常可被捕获并记录
        prompt = _render_summary_prompt(session["summary"], rounds_text)

        # 校验占位符已全部替换，防止模板文件字符异常时静默发送未渲染的 prompt
        if "{{" in prompt:
            logging.error(
                f"session={session_id} prompt 模板占位符未完全替换，跳过摘要（请检查 summary.md 格式）"
            )
            return

        new_summary = await llm.chat([{"role": "user", "content": [{"type": "text", "text": prompt}]}])
    except Exception:
        # 失败：不阻塞主响应，count 保持不变，等下一轮再尝试
        logging.exception(f"session={session_id} 摘要生成过程异常，跳过本次更新")
        return

    new_summary = (new_summary or "").strip()
    if not new_summary:
        logging.warning(f"session={session_id} 摘要 LLM 返回空，跳过更新")
        return

    await repo.update_summary(
        session_id,
        new_summary=new_summary,
        new_count=keep_turns,
    )
    logging.info(
        f"session={session_id} 摘要更新成功 count_reset={keep_turns} summary_len={len(new_summary)}"
    )
