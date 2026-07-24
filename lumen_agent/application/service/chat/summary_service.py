"""滑动窗口摘要：构建 LLM 上下文 + 触发与生成新摘要。"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from lumen_agent.agent.context import extract_complete_turns, turns_to_messages
from lumen_agent.agent.memory.memory_utils import MemoryFileUtils
from lumen_agent.application.uitls.dir_guide import DirGuide
from lumen_agent.config import Settings
from lumen_agent.domain.ports import ConversationRepositoryPort, LLMClientPort

# prompt 模板路径：与代码同包根，方便随包发布
_PROMPT_PATH = DirGuide.summary_prompt_path()
_LONG_MEMORY_PROMPT_PATH = DirGuide.memory_refine_prompt_path()

_ROLE_LABEL = {"user": "用户", "assistant": "助手", "system": "系统", "tool": "工具"}
_SUMMARY_REQUIRED_PLACEHOLDERS = {"{{old_summary}}", "{{rounds_text}}"}
_SUMMARY_ALLOWED_PLACEHOLDERS = _SUMMARY_REQUIRED_PLACEHOLDERS | {"{{new_summary}}"}
_SUMMARY_PLACEHOLDER_RE = re.compile(r"{{[^{}]+}}")


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


def _validate_summary_template(template: str) -> None:
    """在插入对话内容前校验摘要模板的必需、未知和残缺占位符。"""
    cleaned = _SUMMARY_PLACEHOLDER_RE.sub("", template)
    if "{{" in cleaned or "}}" in cleaned:
        raise ValueError("摘要模板存在格式不完整的占位符")

    placeholders = set(_SUMMARY_PLACEHOLDER_RE.findall(template))
    missing = _SUMMARY_REQUIRED_PLACEHOLDERS - placeholders
    if missing:
        raise ValueError(f"摘要模板缺少占位符: {sorted(missing)}")

    unknown = placeholders - _SUMMARY_ALLOWED_PLACEHOLDERS
    if unknown:
        raise ValueError(f"摘要模板存在未知占位符: {sorted(unknown)}")


def _render_summary_prompt(old_summary: str, rounds_text: str) -> str:
    """校验原始模板后填充摘要和对话内容，避免正文占位符触发误判。"""
    template = _load_prompt_template()
    _validate_summary_template(template)
    return (
        template.replace("{{old_summary}}", old_summary or "")
        .replace("{{rounds_text}}", rounds_text or "")
        .replace("{{new_summary}}", "")
    )


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


_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


def _extract_json_object(text: str) -> str | None:
    """从文本中提取第一个完整的 JSON 对象（支持嵌套花括号）。"""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _extract_json_text(raw: str) -> str:
    """清洗 LLM 返回值，尽量提取可解析的 JSON 字符串。"""
    text = (raw or "").strip()
    if not text:
        return ""

    fence_match = _FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    extracted = _extract_json_object(text)
    return extracted if extracted is not None else text


def _parse_summary_payload(raw: str) -> tuple[str, str]:
    """兼容旧文本与新 JSON 摘要返回值（含 markdown 代码块包裹）。"""
    text = (raw or "").strip()
    if not text:
        return "", ""

    json_text = _extract_json_text(text)
    try:
        data = json.loads(json_text)
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


_MEMORY_UTILS = MemoryFileUtils(memory_dir=DirGuide.memory_dir())


def _load_text_if_exists(path: Path) -> str:
    return _MEMORY_UTILS.read_text_if_exists(path)


async def _write_daily_memory_append(
    session_id: str,
    count_summary: str,
    *,
    entry_id: str,
) -> None:
    """按稳定区间 ID 写入当日记忆，并以相同 ID 更新向量索引。"""
    result = _MEMORY_UTILS.append_daily_summary(
        session_id,
        count_summary,
        entry_id=entry_id,
    )
    if result is not None:
        file_path, ts = result
        logging.info("session=%s 当日记忆已写入 %s entry_id=%s", session_id, file_path, entry_id)
        # 同步写入 ChromaDB 向量索引；失败不影响已持久化的 Markdown。
        try:
            body = (count_summary or "").strip()
            header = f"## {ts}  session={session_id}  entry_id={entry_id}\n\n"
            entry_text = header + body
            metadata = {
                "source": "daily",
                "date": ts[:10],
                "session_id": session_id,
                "timestamp": ts,
                "entry_id": entry_id,
            }
            from lumen_agent.application.service.embedding.memory_rag_service import MemoryRagService
            from lumen_agent.config import get_settings

            service = MemoryRagService(get_settings())
            await service.index_entry(entry_text, entry_id, metadata)
            logging.info("session=%s 记忆向量索引完成 entry_id=%s", session_id, entry_id)
        except Exception:
            logging.exception("session=%s 记忆向量索引失败，不影响文件写入", session_id)


def _write_memory_file(
    session_id: str,
    messages: list[dict[str, Any]],
    *,
    entry_id: str,
) -> None:
    """按稳定区间 ID 将强制截断消息写入当日记忆文件。"""
    file_path = _MEMORY_UTILS.append_message_backup(
        session_id=session_id,
        messages=messages,
        role_label_map=_ROLE_LABEL,
        message_to_text_fn=_message_to_text,
        entry_id=entry_id,
    )
    logging.info(
        "session=%s 截断记录已写入 %s entry_id=%s",
        session_id,
        file_path,
        entry_id,
    )


async def maybe_trigger_summary(
    repo: ConversationRepositoryPort,
    llm: LLMClientPort,
    session_id: str,
    settings: Settings,
) -> None:
    """达到阈值后，原子抢占并压缩尚未处理的固定消息区间。"""
    threshold = settings.get("SUMMARY_THRESHOLD_TURNS", 6)
    keep_turns = settings.get("SUMMARY_KEEP_TURNS", 2)
    stale_seconds = settings.get("SUMMARY_COMPACTION_STALE_SECONDS", 1800)

    # 先做无锁快速判断，未达到阈值时避免额外写事务。
    session = await repo.get_session(session_id)
    if session is None or int(session["count"]) < threshold:
        return

    claim = await repo.claim_summary_compaction(
        session_id,
        stale_after_seconds=stale_seconds,
    )
    if claim is None:
        logging.debug("session=%s 已有摘要任务运行，跳过重复触发", session_id)
        return

    started_at = claim.get("compaction_started_at")
    if not isinstance(started_at, str):
        logging.error("session=%s 摘要任务缺少抢占时间，跳过", session_id)
        return

    completed = False
    try:
        count = int(claim["count"])
        if count < threshold:
            return

        start_seq = int(claim["summary_cursor_seq"]) + 1
        pending_messages = await repo.list_messages_range(
            session_id,
            start_seq=start_seq,
        )
        turns = _find_complete_turns(pending_messages)
        if len(turns) < threshold:
            logging.warning(
                "session=%s 触发摘要但游标后的完整轮次不足（expect=%s got=%s），跳过",
                session_id,
                threshold,
                len(turns),
            )
            return

        # 摘要持续失败时直接备份溢出原文，并推进游标防止上下文无限膨胀。
        if count >= threshold * 2:
            to_compress_turns = turns[:-keep_turns] if keep_turns > 0 else turns
            to_compress = turns_to_messages(to_compress_turns)
            end_seq = max(int(message["seq"]) for message in to_compress)
            entry_id = f"session:{session_id}:seq:{start_seq}-{end_seq}"
            _write_memory_file(
                session_id,
                to_compress,
                entry_id=f"{entry_id}:backup",
            )
            completed = await repo.complete_summary_compaction(
                session_id,
                compaction_started_at=started_at,
                new_summary=claim["summary"],
                summary_cursor_seq=end_seq,
                compressed_turns=len(to_compress_turns),
            )
            if completed:
                logging.warning(
                    "session=%s 摘要持续失败，已备份并跳过 %s 轮，cursor=%s",
                    session_id,
                    len(to_compress_turns),
                    end_seq,
                )
            return

        to_compress_turns = turns[:-keep_turns] if keep_turns > 0 else turns
        if not to_compress_turns:
            return
        to_compress = turns_to_messages(to_compress_turns)
        end_seq = max(int(message["seq"]) for message in to_compress)
        entry_id = f"session:{session_id}:seq:{start_seq}-{end_seq}"
        rounds_text = _format_rounds(to_compress)
        prompt = _render_summary_prompt(claim["summary"], rounds_text)
        raw_summary = await llm.chat(
            [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        )
        new_summary, count_summary = _parse_summary_payload(raw_summary)
        if not new_summary and not count_summary:
            logging.warning("session=%s 摘要 LLM 返回空，跳过更新", session_id)
            return

        await _write_daily_memory_append(
            session_id,
            count_summary,
            entry_id=entry_id,
        )
        completed = await repo.complete_summary_compaction(
            session_id,
            compaction_started_at=started_at,
            new_summary=new_summary,
            summary_cursor_seq=end_seq,
            compressed_turns=len(to_compress_turns),
        )
        if not completed:
            logging.warning("session=%s 摘要任务所有权已失效，放弃提交", session_id)
            return

        try:
            asyncio.create_task(_maybe_refine_long_memory(llm))
        except Exception:
            logging.exception("长期记忆整理任务创建失败")
        logging.info(
            "session=%s 摘要更新成功 compressed_turns=%s cursor=%s summary_len=%s",
            session_id,
            len(to_compress_turns),
            end_seq,
            len(new_summary),
        )
    except Exception:
        logging.exception("session=%s 摘要生成过程异常，保持原状态", session_id)
    finally:
        if not completed:
            await repo.release_summary_compaction(
                session_id,
                compaction_started_at=started_at,
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
    """原子压缩游标后的历史，仅保留最后一轮或压缩全部完整轮次。"""
    stale_seconds = settings.get("SUMMARY_COMPACTION_STALE_SECONDS", 1800)
    claim = await repo.claim_summary_compaction(
        session_id,
        stale_after_seconds=stale_seconds,
    )
    if claim is None:
        logging.info("[ForceCompress] session=%s 已有压缩任务运行，跳过", session_id)
        return

    started_at = claim.get("compaction_started_at")
    if not isinstance(started_at, str):
        logging.error("[ForceCompress] session=%s 缺少抢占时间，跳过", session_id)
        return

    completed = False
    try:
        start_seq = int(claim["summary_cursor_seq"]) + 1
        pending_messages = await repo.list_messages_range(
            session_id,
            start_seq=start_seq,
        )
        turns = _find_complete_turns(pending_messages)
        retained_turns = 1 if keep_last_turn else 0
        if len(turns) <= retained_turns:
            logging.info("[ForceCompress] session=%s 可压缩轮次不足，跳过", session_id)
            return

        to_compress_turns = turns[:-1] if keep_last_turn else turns
        to_compress = turns_to_messages(to_compress_turns)
        end_seq = max(int(message["seq"]) for message in to_compress)
        entry_id = f"session:{session_id}:seq:{start_seq}-{end_seq}"

        # 强制压缩保留原文备份，重试同一区间时会覆盖同一条目。
        _write_memory_file(
            session_id,
            to_compress,
            entry_id=f"{entry_id}:backup",
        )
        rounds_text = _format_rounds(to_compress)
        prompt = _render_summary_prompt(claim["summary"], rounds_text)
        raw_summary = await llm.chat(
            [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        )
        new_summary, count_summary = _parse_summary_payload(raw_summary)
        if not new_summary and not count_summary:
            logging.warning("[ForceCompress] session=%s 摘要 LLM 返回空，跳过更新", session_id)
            return

        await _write_daily_memory_append(
            session_id,
            count_summary,
            entry_id=entry_id,
        )
        completed = await repo.complete_summary_compaction(
            session_id,
            compaction_started_at=started_at,
            new_summary=new_summary,
            summary_cursor_seq=end_seq,
            compressed_turns=len(to_compress_turns),
        )
        if not completed:
            logging.warning("[ForceCompress] session=%s 任务所有权已失效，放弃提交", session_id)
            return

        try:
            asyncio.create_task(_maybe_refine_long_memory(llm))
        except Exception:
            logging.exception("长期记忆整理任务创建失败")
        logging.info(
            "[ForceCompress] session=%s 强制压缩完成 compressed_turns=%s cursor=%s summary_len=%s",
            session_id,
            len(to_compress_turns),
            end_seq,
            len(new_summary),
        )
    except Exception:
        logging.exception("[ForceCompress] session=%s 强制压缩异常，保持原状", session_id)
    finally:
        if not completed:
            await repo.release_summary_compaction(
                session_id,
                compaction_started_at=started_at,
            )
