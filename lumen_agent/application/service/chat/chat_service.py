"""用例编排：按 session 加载 summary + 最近原文 → 调 LLM → 落库 + 触发摘要。"""

from __future__ import annotations

import asyncio
import httpx
import base64
import logging
import mimetypes
from collections.abc import AsyncIterator
from typing import Any

from lumen_agent.agent.tokens import get_token_counter
from lumen_agent.application.common.context_assembly import assemble_for_llm
from lumen_agent.application.service.mcp.mcp_lookup import load_enabled_mcp_servers_for_prompt
from lumen_agent.application.service.chat.summary_service import maybe_trigger_summary
from lumen_agent.application.service.chat.title_service import maybe_generate_title
from lumen_agent.application.uitls.dir_guide import DirGuide
from lumen_agent.config import Settings, get_context_window
from lumen_agent.domain.messages import image_block, text_message
from lumen_agent.domain.ports import ConversationRepositoryPort
from lumen_agent.model_adapters.base import ModelAdapter, StreamHandleCallback


async def merge_and_persist_messages(
    repo: ConversationRepositoryPort,
    session_id: str,
    new_messages: list[dict[str, Any]],
    *,
    status: int = 1,
) -> None:
    """合并、回填并持久化 Agent 工具循环产生的新消息。

    处理内容：
    1. 将 tool_result 与前面的 assistant 消息合并（避免存储冗余的"用户"角色消息）
    2. 回填没有 tool_result 的孤立 tool_use 的 (interrupted)
    3. 将合并后的每条消息写入 DB
    4. status=0 表示消息由中断流程保存，status=1 表示正常完成
    """
    # Step 1: 将 tool_result 与前面的 assistant 合并
    merged: list[dict[str, Any]] = []
    for msg in new_messages:
        role = msg.get("role", "")
        content = msg.get("content", [])
        if isinstance(content, list):
            content = [b for b in content if isinstance(b, dict)]

        if (
            role == "user"
            and content
            and all(b.get("type") == "tool_result" for b in content)
        ):
            if merged and merged[-1]["role"] == "assistant":
                merged[-1]["content"].extend(content)
            else:
                merged.append({"role": "user", "content": content})
        elif role == "assistant":
            if merged and merged[-1]["role"] == "assistant":
                merged[-1]["content"].extend(content)
            else:
                merged.append({"role": "assistant", "content": list(content)})
        else:
            merged.append({"role": role, "content": content})

    # Step 2: 兜底 — 孤立 tool_use 补 (interrupted)
    for msg in merged:
        if msg["role"] != "assistant":
            continue
        use_ids = {
            b["id"] for b in msg["content"]
            if b.get("type") == "tool_use" and b.get("id")
        }
        result_ids = {
            b["tool_use_id"] for b in msg["content"]
            if b.get("type") == "tool_result" and b.get("tool_use_id")
        }
        for tid in use_ids - result_ids:
            msg["content"].append({
                "type": "tool_result",
                "tool_use_id": tid,
                "content": "(interrupted)",
                "is_error": True,
            })

    # Step 3: 持久化
    for msg in merged:
        if not msg.get("content"):
            continue
        await repo.append_message(session_id, msg["role"], msg["content"], status=status)


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

    # 异步生成会话标题（仅首次消息触发）
    asyncio.create_task(maybe_generate_title(repo, llm, session_id, user_message))

    # 2) 组装上下文（含 token 预算检查 / 强制压缩）
    counter = get_token_counter(settings.get("LLM_MODEL", "deepseek-v4-flash"))
    context_window = get_context_window(settings, settings.get("LLM_MODEL", "deepseek-v4-flash"))
    ctx = await assemble_for_llm(
        repo, llm, settings,
        session_id=session_id,
        system_content=None,
        user_message=user_message,
        counter=counter,
        context_window=context_window,
    )
    # 移除列表末尾自动追加的 user 消息（assemble_for_llm 已包含），直接使用
    messages = ctx.messages
    logging.info(
        f"session={session_id} 上下文构建完成 summary={bool(ctx.summary_used)} "
        f"kept_turns={ctx.kept_turns} total_tokens={ctx.total_tokens} "
        f"force_compressed={ctx.force_compressed}"
    )

    # 3) 调 LLM（返回含 thinking 的 content blocks）
    assistant_blocks = await llm.chat_blocks(messages)

    # 4) 助手消息落库 + 轮次 +1 + 摘要触发
    # assistant_blocks 已包含 text + thinking 块
    await repo.append_message(session_id, "assistant", assistant_blocks)
    new_count = await repo.increment_round_counter(session_id)
    logging.info(f"session={session_id} 助手已落库 count={new_count}")
    asyncio.create_task(maybe_trigger_summary(repo, llm, session_id, settings))

    # 返回纯文本给 API 层（不含 thinking 块）
    return next((b["text"] for b in assistant_blocks if b.get("type") == "text"), "")


async def reply_single_turn_stream(
    repo: ConversationRepositoryPort,
    llm: ModelAdapter,
    session_id: str,
    user_message: str,
    settings: Settings,
    on_connect: StreamHandleCallback | None = None,
) -> AsyncIterator[tuple[str, str]]:
    """处理单轮会话请求——流式输出，yield ``(kind, delta)``。

    参数:
        on_connect: 连接建立后的回调，传递 ``StreamHandle`` 供注册到中断注册表。
    """
    # 1) 会话准备 + 用户消息落库
    await repo.ensure_session(session_id)
    user_blocks = text_message("user", user_message)["content"]
    await repo.append_message(session_id, "user", user_blocks)

    # 异步生成会话标题（仅首次消息触发）
    asyncio.create_task(maybe_generate_title(repo, llm, session_id, user_message))

    # 2) 组装上下文
    counter = get_token_counter(settings.get("LLM_MODEL", "deepseek-v4-flash"))
    context_window = get_context_window(settings, settings.get("LLM_MODEL", "deepseek-v4-flash"))
    ctx = await assemble_for_llm(
        repo, llm, settings,
        session_id=session_id,
        system_content=None,
        user_message=user_message,
        counter=counter,
        context_window=context_window,
    )
    messages = ctx.messages
    logging.info(
        f"session={session_id} 流式上下文构建完成 summary={bool(ctx.summary_used)} "
        f"kept_turns={ctx.kept_turns} total_tokens={ctx.total_tokens} "
        f"force_compressed={ctx.force_compressed}"
    )

    # 3) 流式生成；累加 text + thinking 用于落库
    accumulated = ""
    accumulated_thinking = ""
    async def persist_partial_message() -> None:
        """将简单模式已经收到的增量保存为中断消息。"""
        blocks: list[dict[str, Any]] = []
        if accumulated_thinking.strip():
            blocks.append({"type": "thinking", "thinking": accumulated_thinking})
        if accumulated.strip():
            blocks.append({"type": "text", "text": accumulated})
        if blocks:
            await repo.append_message(
                session_id,
                "assistant",
                blocks,
                status=0,
            )

    try:
        async for kind, chunk in llm.chat_stream(messages, on_connect=on_connect):
            if kind == "text":
                accumulated += chunk
            elif kind == "thinking":
                accumulated_thinking += chunk
            yield (kind, chunk)
    except (httpx.ReadError, asyncio.CancelledError):
        # 显式 interrupt 取消 owner task 后，在后端保存 partial 回复。
        await persist_partial_message()
        yield ("error", "stream_interrupted")
        return
    except Exception:
        await persist_partial_message()
        raise

    # 4) 正常结束：助手落库（含 thinking 块）+ 轮次 +1 + 摘要触发
    if accumulated.strip() or accumulated_thinking.strip():
        assistant_blocks: list[dict[str, Any]] = []
        if accumulated_thinking.strip():
            assistant_blocks.append({"type": "thinking", "thinking": accumulated_thinking})
        if accumulated.strip():
            assistant_blocks.append({"type": "text", "text": accumulated})
        await repo.append_message(session_id, "assistant", assistant_blocks)
        new_count = await repo.increment_round_counter(session_id)
        logging.info(f"session={session_id} 流式助手已落库 count={new_count}")
        asyncio.create_task(maybe_trigger_summary(repo, llm, session_id, settings))


def _build_data_uri_blocks(image_urls: list[str]) -> list[dict]:
    """将图片 URL（/v1/files/{name}）解析为 base64 data URI 图像块列表。

    URL 若不是本地文件引用（/v1/files/...），则直接当作远端 URL 传递给 LLM。
    读取失败时记录警告并跳过，不中断请求。
    """
    from lumen_agent.application.uitls.dir_guide import DirGuide

    blocks: list[dict] = []
    tmp_dir = DirGuide.tmp_dir()

    for url in image_urls:
        try:
            if url.startswith("/v1/files/"):
                filename = url.removeprefix("/v1/files/")
                # 防路径穿越
                if "/" in filename or "\\" in filename or ".." in filename:
                    logging.warning("跳过非法图片路径：%s", url)
                    continue
                file_path = tmp_dir / filename
                if not file_path.is_file():
                    logging.warning("图片文件不存在，已跳过：%s", file_path)
                    continue
                data = file_path.read_bytes()
                mime = mimetypes.guess_type(str(file_path))[0] or "image/jpeg"
                b64 = base64.b64encode(data).decode()
                data_uri = f"data:{mime};base64,{b64}"
                blocks.append({"type": "image_url", "image_url": {"url": data_uri}})
            else:
                # 外部 URL 直接传给 LLM
                blocks.append({"type": "image_url", "image_url": {"url": url}})
        except Exception:
            logging.warning("构建图片 data URI 失败，已跳过：%s", url, exc_info=True)

    return blocks


async def reply_with_agent(
    repo: ConversationRepositoryPort,
    llm: ModelAdapter,
    session_id: str,
    session_kind: int,
    user_message: str,
    settings: Settings,
    approval_mode: str | None = None,
    on_connect: StreamHandleCallback | None = None,
    mcp_server_ids: list[str] | None = None,
    self_system: str | None = None,
    image_urls: list[str] | None = None,
) -> AsyncIterator[tuple[str, Any]]:
    """用 Agent 工具循环处理会话请求——流式输出，yield ``(kind, data)``。

    kind 取值同 AgentStreamExecutor.run_stream()，包含工具执行事件。
    额外处理 ("new_messages", list[dict]) 事件：将 Agent 执行期间新产生的
    tool_use / tool_result / assistant 消息全部持久化到数据库。

    参数:
        mcp_servers: 可选，外部 MCP Server 列表，仅 agent 模式下生效。
    """
    from lumen_agent.agent.agent import AgentStreamExecutor
    from lumen_agent.agent.tools import init_tools
    from lumen_agent.agent.tools.registry import ToolRegistry
    from lumen_agent.agent.prompts.builder import build_system_prompt
    from lumen_agent.agent.skills import load_skills
    from lumen_agent.application.service.mcp.mcp_request_context import set_allowed_server_ids

    # 确保工具已注册（幂等）
    init_tools()

    # 1) 会话准备 + 用户消息落库
    await repo.ensure_session(session_id, session_kind)
    user_blocks = text_message("user", user_message)["content"]
    # 持久化时附带轻量图像引用（存 URL 路径，不存 data URI）
    if image_urls:
        for img_url in image_urls:
            user_blocks.append(image_block(img_url))  # type: ignore[arg-type]
    await repo.append_message(session_id, "user", user_blocks)

    # 异步生成会话标题（仅首次消息触发）
    asyncio.create_task(maybe_generate_title(repo, llm, session_id, user_message))

    # 2) 构建 system 提示词（MCP 工具通过 mcp_search / mcp_call 按需使用，不再全量注入 MCPBridgeTool）
    all_tools = ToolRegistry.create_all_tools()
    skills = load_skills()
    enabled_mcp = await load_enabled_mcp_servers_for_prompt()
    system_content = build_system_prompt(
        all_tools, skills, self_system, session_kind, mcp_servers=enabled_mcp
    ) or None

    # mcp_call 允许的 server id：默认全部已启用 + 调用方额外传入
    allowed_ids = [s["id"] for s in enabled_mcp]
    for sid in (mcp_server_ids or []):
        if sid not in allowed_ids:
            allowed_ids.append(sid)
    set_allowed_server_ids(allowed_ids)

    # 3) 组装上下文（含 token 预算检查 / 强制压缩）
    counter = get_token_counter(settings.get("LLM_MODEL", "deepseek-v4-flash"))
    context_window = get_context_window(settings, settings.get("LLM_MODEL", "deepseek-v4-flash"))

    # 将图片即时转为 base64 data URI，随请求体内联发给 LLM（不入库）
    image_extra_blocks: list[dict] | None = None
    if image_urls:
        image_extra_blocks = _build_data_uri_blocks(image_urls)

    ctx = await assemble_for_llm(
        repo, llm, settings,
        session_id=session_id,
        system_content=system_content,
        user_message=user_message,
        counter=counter,
        context_window=context_window,
        user_extra_blocks=image_extra_blocks,
    )
    messages = ctx.messages
    logging.info(
        f"[Agent] session={session_id} 上下文构建完成 "
        f"summary={bool(ctx.summary_used)} kept_turns={ctx.kept_turns} "
        f"total_tokens={ctx.total_tokens} force_compressed={ctx.force_compressed}"
    )

    # 4) 创建 AgentStreamExecutor
    from lumen_agent.infrastructure.approval_registry import get_approval_registry

    executor = AgentStreamExecutor(
        adapter=llm,
        tools=all_tools,
        settings=settings,
        session_id=session_id,
        approval_registry=get_approval_registry(),
        approval_mode=  approval_mode if approval_mode else  settings.get("TOOL_APPROVAL_MODE", "none"),
        approval_timeout=settings.get("TOOL_APPROVAL_TIMEOUT", 300),
    )

    # 5) 运行工具循环，处理事件流
    final_text = ""
    initial_len = len(messages)
    persist_status = 1

    async def persistable_events():
        """兜住工具审批/执行阶段的任务取消。

        如果取消发生在模型流内，AgentStreamExecutor 会自行产出 new_messages；
        这里只处理取消尚未被内部生成器转换为事件的阶段。
        """
        try:
            async for event in executor.run_stream(messages, on_connect=on_connect):
                yield event
        except asyncio.CancelledError:
            pending = messages[initial_len:]
            if pending:
                await merge_and_persist_messages(
                    repo, session_id, pending, status=0
                )
            raise

    async for kind, data in persistable_events():
        if kind == "new_messages":
            await merge_and_persist_messages(repo, session_id, data, status=persist_status)  # type: ignore[arg-type]
            # status=0 表示本轮被显式中断，前端仍可展示但不计正常轮次。
        elif kind == "error" and data == "stream_interrupted":
            persist_status = 0
            yield (kind, data)
        elif kind == "done":
            final_text = data  # type: ignore[assignment]
            yield (kind, data)
        elif kind == "text":
            final_text += data  # type: ignore[operator]
            yield (kind, data)
        else:
            yield (kind, data)

    # 6) 轮次 +1
    if final_text.strip() and persist_status == 1:
        new_count = await repo.increment_round_counter(session_id)
        logging.info(f"[Agent] session={session_id} 工具循环结束 count={new_count}")
        asyncio.create_task(maybe_trigger_summary(repo, llm, session_id, settings))
