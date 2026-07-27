"""会话标题生成：基于用户第一条消息调 LLM 生成简洁标题。"""

from __future__ import annotations

import logging
from functools import lru_cache

from lumen_agent.application.uitls.dir_guide import DirGuide
from lumen_agent.domain.ports import ConversationRepositoryPort
from lumen_agent.model_adapters.base import ModelAdapter

# prompt 模板路径
_PROMPT_PATH = DirGuide.title_prompt_path()


@lru_cache(maxsize=1)
def _load_prompt_template() -> str:
    """读取标题生成 prompt 模板（进程内只读一次）。"""
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _render_title_prompt(first_message: str) -> str:
    """用 ``str.replace`` 填充 prompt 占位符。"""
    tpl = _load_prompt_template()
    tpl = tpl.replace("{{first_message}}", first_message.strip())
    return tpl


def _fallback_title(first_message: str) -> str:
    """标题生成失败时使用用户首条消息作为兜底标题。"""
    return " ".join(first_message.split()).strip()


async def _use_fallback_title(
    repo: ConversationRepositoryPort,
    session_id: str,
    first_message: str,
) -> None:
    """把用户首条消息写作标题；空消息不写。"""
    fallback = _fallback_title(first_message)
    if not fallback:
        logging.warning(f"session={session_id} 标题兜底内容为空，跳过")
        return
    await repo.update_session_title(session_id, fallback)
    logging.info(f"session={session_id} 已使用用户消息作为兜底标题: {fallback}")


async def maybe_generate_title(
    repo: ConversationRepositoryPort,
    llm: ModelAdapter,
    session_id: str,
    first_message: str,
) -> None:
    """若会话标题为空，则根据用户首条消息生成标题并持久化。

    失败不抛：仅记录日志，保持空标题，等手动修改或下次触发。
    """
    try:
        session = await repo.get_session(session_id)
        if session is None:
            return
        if session.get("title", "").strip():
            # 标题已存在，无需生成
            return

        prompt = _render_title_prompt(first_message)
        if "{{" in prompt:
            logging.error(
                f"session={session_id} 标题 prompt 模板占位符未替换，使用兜底标题"
            )
            await _use_fallback_title(repo, session_id, first_message)
            return

        raw_title = await llm.chat(
            [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        )
        title = (raw_title or "").strip().strip('"').strip("'").strip()
        if not title:
            logging.warning(f"session={session_id} 标题 LLM 返回空，使用兜底标题")
            await _use_fallback_title(repo, session_id, first_message)
            return

        await repo.update_session_title(session_id, title)
        logging.info(f"session={session_id} 标题已自动生成: {title}")

    except Exception as exc:
        logging.warning(
            f"session={session_id} 标题生成失败，使用兜底标题: {exc}"
        )
        try:
            await _use_fallback_title(repo, session_id, first_message)
        except Exception:
            logging.exception(f"session={session_id} 兜底标题写入失败，跳过")
