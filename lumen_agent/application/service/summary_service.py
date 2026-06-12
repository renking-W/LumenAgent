"""滑动窗口摘要：构建 LLM 上下文 + 触发与生成新摘要。"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from lumen_agent.agent.context import extract_complete_turns, turns_to_messages
from lumen_agent.agent.memory.memory_utils import MemoryFileUtils
from lumen_agent.config import Settings
from lumen_agent.domain.ports import ConversationRepositoryPort, LLMClientPort

# prompt 模板路径：与代码同包根，方便随包发布
_PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "agent" / "prompts" / "docs" / "summary.md"
_LONG_MEMORY_PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "agent" / "prompts" / "docs" / "memory_refine.md"

_ROLE_LABEL = {"user": "用户", "assistant": "助手", "system": "系统", "tool": "工具"}


@lru_cache(maxsize=1)
def _load_prompt_template() -> str:
    """读取摘要 prompt 模板（进程内只读一次）。"""
    return _PROMPT_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _load_long_memory_prompt_template() -> str:
    """读取长期记忆整理 prompt 模板（进程内只读一次）。"""
    return _LONG_MEMORY_PROMPT_PATH.read_text(encoding="utf-8")


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
    tpl = tpl.replace("{{rounds_text}}", rounds_text or "")
    tpl = tpl.replace("{{new_summary}}", "")
    return tpl


def _find_complete_turns(
    msgs: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    """从顺序消息列表中提取完整轮次列表。

    以「非 tool_result 的 user 消息」为轮次起点，每个轮次包含该 user 消息
    以及后续所有 assistant、tool_use、tool_result 消息，直到下一个真实 user 消息。

    只保留最终包含 assistant 回复的完整轮次（丢弃尾部不完整的 user-only 轮次）。
    """
    all_turns = extract_complete_turns(msgs)
    complete: list[list[dict[str, Any]]] = []
    for turn in all_turns:
        # 至少含一条 assistant 消息才算完整轮次
        if any(m.get("role") == "assistant" for m in turn):
            complete.append(turn)
    return complete


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


def _parse_summary_payload(raw: str) -> tuple[str, str]:
    """兼容旧文本与新 JSON 摘要返回值。"""
    text = (raw or "").strip()
    if not text:
        return "", ""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text, text

    if isinstance(data, dict):
        new_summary = str(data.get("new_summary", "") or "").strip()
        count_summary = str(data.get("count_summary", "") or "").strip()
        return new_summary, count_summary
    return text, text


def _load_and_refine_memory(prompt_template: str, memory_text: str) -> str:
    prompt = prompt_template.replace("{{memory_text}}", memory_text or "")
    if "{{" in prompt:
        raise ValueError("memory refine prompt contains unreplaced placeholder")
    return prompt


_MEMORY_UTILS = MemoryFileUtils(
    memory_dir=Path(__file__).resolve().parent.parent.parent.parent / "work_space" / "memory",
)


def _load_text_if_exists(path: Path) -> str:
    return _MEMORY_UTILS.read_text_if_exists(path)


async def _write_daily_memory_append(
    session_id: str,
    count_summary: str,
) -> None:
    """将 count_summary 追加写入当天的记忆文档，同时写入向量索引库。"""
    result = _MEMORY_UTILS.append_daily_summary(session_id, count_summary)
    if result is not None:
        file_path, ts = result
        logging.info("session=%s 当日记忆已追加到 %s", session_id, file_path)
        # 同步写入 ChromaDB 向量索引（异步任务，失败不阻塞主流程）
        try:
            body = (count_summary or "").strip()
            header = f"## {ts}  session={session_id}\n\n"
            entry_text = header + body
            ts_safe = ts.replace(":", "-").replace(" ", "_")
            entry_id = f"daily:{ts[:10]}:{ts_safe}:{session_id}"
            metadata = {
                "source": "daily",
                "date": ts[:10],
                "session_id": session_id,
                "timestamp": ts,
            }
            from lumen_agent.application.service.memory_rag_service import MemoryRagService
            from lumen_agent.config import get_settings

            service = MemoryRagService(get_settings())
            await service.index_entry(entry_text, entry_id, metadata)
            logging.info("session=%s 记忆向量索引完成", session_id)
        except Exception:
            logging.exception("session=%s 记忆向量索引失败，不影响文件写入", session_id)


def _write_memory_file(
    session_id: str,
    messages: list[dict[str, Any]],
) -> None:
    """将被强制截断的消息追加写入按日期命名的记忆文件（``YYYY-MM-DD.md``）。"""
    file_path = _MEMORY_UTILS.append_message_backup(
        session_id=session_id,
        messages=messages,
        role_label_map=_ROLE_LABEL,
        message_to_text_fn=_message_to_text,
    )
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
    threshold = settings.get("SUMMARY_THRESHOLD_TURNS", 6)
    compress_turns = settings.get("SUMMARY_COMPRESS_TURNS", 4)
    keep_turns = settings.get("SUMMARY_KEEP_TURNS", 2)

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
            lost_msgs = turns_to_messages(lost_turns)
            try:
                _write_memory_file(
                    session_id,
                    lost_msgs,
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

        # 从后往前数，跳过保留的 keep_turns 轮，其余压缩为摘要
        to_compress = turns_to_messages(turns[:-keep_turns]) if keep_turns > 0 else turns_to_messages(turns)
        rounds_text = _format_rounds(to_compress)

        # 渲染 prompt（含文件读取），放在 try 块内以确保异常可被捕获并记录
        prompt = _render_summary_prompt(session["summary"], rounds_text)

        # 校验占位符已全部替换，防止模板文件字符异常时静默发送未渲染的 prompt
        if "{{" in prompt:
            logging.error(
                f"session={session_id} prompt 模板占位符未完全替换，跳过摘要（请检查 summary.md 格式）"
            )
            return

        raw_summary = await llm.chat([{"role": "user", "content": [{"type": "text", "text": prompt}]}])
    except Exception:
        # 失败：不阻塞主响应，count 保持不变，等下一轮再尝试
        logging.exception(f"session={session_id} 摘要生成过程异常，跳过本次更新")
        return

    new_summary, count_summary = _parse_summary_payload(raw_summary)
    if not new_summary and not count_summary:
        logging.warning(f"session={session_id} 摘要 LLM 返回空，跳过更新")
        return

    try:
        await _write_daily_memory_append(session_id, count_summary)
    except Exception:
        logging.exception(f"session={session_id} 追加当日记忆失败")

    await repo.update_summary(
        session_id,
        new_summary=new_summary,
        new_count=keep_turns,
    )
    try:
        asyncio.create_task(_maybe_refine_long_memory(llm))
    except Exception:
        logging.exception("长期记忆整理任务创建失败")
    logging.info(
        f"session={session_id} 摘要更新成功 count_reset={keep_turns} summary_len={len(new_summary)}"
    )


async def _maybe_refine_long_memory(llm: LLMClientPort) -> None:
    """当 MEMORY.md 过大时，触发长期记忆整理并覆盖写回。"""
    memory_path = _MEMORY_UTILS.memory_file_path()
    if not _MEMORY_UTILS.exists(memory_path):
        return
    if _MEMORY_UTILS.file_size(memory_path) <= 150 * 1024:
        return

    memory_text = _load_text_if_exists(memory_path)
    if not memory_text.strip():
        return

    prompt_template = _load_long_memory_prompt_template()
    prompt = _load_and_refine_memory(prompt_template, memory_text)
    logging.warning("长期记忆超过阈值，触发整理：%s", memory_path)
    try:
        refined = await llm.chat([{"role": "user", "content": [{"type": "text", "text": prompt}]}])
    except Exception:
        logging.exception("长期记忆整理失败，保留原内容")
        return

    refined_text = (refined or "").strip()
    if not refined_text:
        logging.warning("长期记忆整理返回空，保留原内容")
        return

    memory_path.write_text(refined_text + "\n", encoding="utf-8")
    logging.info("长期记忆整理完成并已覆盖写回 %s", memory_path)


async def force_compress_now(
    repo: ConversationRepositoryPort,
    llm: LLMClientPort,
    settings: Settings,
    *,
    session_id: str,
    keep_last_turn: bool = True,
) -> None:
    """将「除最后一轮以外」的全部历史强制压缩进 summary，重置 count 为 1。

    步骤：
    1. 取全部消息，按完整轮次切分。
    2. 若历史只有 0–1 轮，无需压缩，直接返回。
    3. 把需压缩的轮次文本喂 LLM 生成新 summary（追加到当前 summary 后）。
    4. 将原文备份写入 memory/YYYY-MM-DD.md。
    5. 更新 sessions.summary 并把 count 重置为 1（仅保留最后 1 轮）。

    失败不抛异常：仅记录 ERROR，保持原状，让调用方决定是否重试。
    """
    try:
        session = await repo.get_session(session_id)
        if session is None:
            logging.warning(f"[ForceCompress] session={session_id} 不存在，跳过")
            return

        all_msgs = await repo.list_messages(session_id)
        turns = _find_complete_turns(all_msgs)

        if len(turns) <= 1:
            logging.info(f"[ForceCompress] session={session_id} 轮次不足 2，无需强制压缩")
            return

        if keep_last_turn:
            to_compress_turns = turns[:-1]
            # 最后一轮保留，count 重置为 1
            new_count = 1
        else:
            to_compress_turns = turns
            new_count = 0

        to_compress_msgs = turns_to_messages(to_compress_turns)

        # 备份原文到 memory 文件
        try:
            _write_memory_file(
                session_id,
                to_compress_msgs,
            )
        except Exception:
            logging.exception(f"[ForceCompress] session={session_id} 写入 memory 文件失败，继续摘要")

        # 生成新摘要
        rounds_text = _format_rounds(to_compress_msgs)
        old_summary = session.get("summary") or ""
        prompt = _render_summary_prompt(old_summary, rounds_text)

        if "{{" in prompt:
            logging.error(f"[ForceCompress] session={session_id} prompt 模板未完全渲染，跳过")
            return

        raw_summary = await llm.chat(
            [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        )
        new_summary, count_summary = _parse_summary_payload(raw_summary)
        if not new_summary and not count_summary:
            logging.warning(f"[ForceCompress] session={session_id} 摘要 LLM 返回空，跳过更新")
            return

        try:
            await _write_daily_memory_append(session_id, count_summary)
        except Exception:
            logging.exception(f"[ForceCompress] session={session_id} 追加当日记忆失败")

        await repo.update_summary(session_id, new_summary=new_summary, new_count=new_count)
        # 异步任务，不阻塞主进程
        try:
            asyncio.create_task(_maybe_refine_long_memory(llm))
        except Exception:
            logging.exception("长期记忆整理任务创建失败")
        logging.info(
            f"[ForceCompress] session={session_id} 强制压缩完成 "
            f"count_reset={new_count} summary_len={len(new_summary)}"
        )

    except Exception:
        logging.exception(f"[ForceCompress] session={session_id} 强制压缩异常，保持原状")
