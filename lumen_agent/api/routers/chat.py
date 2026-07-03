"""对话路由：`POST /v1/chat` 整段 JSON；`POST /v1/chat/stream` SSE；`POST /v1/chat/stream/interrupt` 中断流式对话。"""
import asyncio
import logging
from collections.abc import AsyncIterator
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from lumen_agent.api.dependency import get_conversation_repo, get_llm_client, verify_api_key
from lumen_agent.api.schemas.approval_dtos import ApproveRequest, ApproveResponse
from lumen_agent.api.schemas.session_dtos import ChatRequest, ChatResponse, InterruptRequest
from lumen_agent.api.schemas.stream_events import (
    StreamErrorData,
    StreamErrorEvent,
    StreamEventDispatcher,
)
from lumen_agent.application.service.chat_service import reply_single_turn, reply_single_turn_stream, reply_with_agent
from lumen_agent.application.uitls.llm_error_policy import (
    llm_chain_failure_detail,
    llm_chain_failure_http_status,
)
from lumen_agent.config import Settings, get_settings
from lumen_agent.domain.messages import text_message
from lumen_agent.domain.ports import ConversationRepositoryPort
from lumen_agent.infrastructure.approval_registry import get_approval_registry
from lumen_agent.infrastructure.http_pool import StreamHandle
from lumen_agent.infrastructure.sse_registry import get_sse_registry
from lumen_agent.model_adapters.base import ModelAdapter

router = APIRouter(
    prefix="/v1",
    tags=["chat"],
    dependencies=[Depends(verify_api_key)],
)

_LLM_STREAM_FAILURES = (httpx.HTTPStatusError, httpx.RequestError, RuntimeError)

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _sse_error_line(exc: BaseException) -> str:
    """将 LLM 链路异常序列化为 SSE error 事件行。"""
    event = StreamErrorEvent(data=StreamErrorData(message=llm_chain_failure_detail(exc)))
    return f"data: {event.model_dump_json()}\n\n"


def _require_api_key(settings: Settings) -> None:
    """校验 API KEY 是否配置。"""
    if not settings.get("LLM_API_KEY", "").strip():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM_API_KEY is not configured",
        )


def _resolve_session(body: ChatRequest | None) -> ChatRequest:
    """预处理session字段"""
    # 没有携带session_id字段的请求，一律视为普通内部会话 kind=0
    if body.session_id is None:
        body.session_id = str(uuid4())
        body.session_kind = 0
    # 没有携带 session_kind 时，默认为0（内部会话）
    if body.session_kind is None:
        body.session_kind = 0
    # kind=1 定时任务下无脑放行命令
    if body.session_kind == 1:
        body.approval_mode = "none"
    return body


@router.post("/chat", response_model=ChatResponse)
async def post_chat(
    body: ChatRequest,
    settings: Settings = Depends(get_settings),
    llm: ModelAdapter = Depends(get_llm_client),
    repo: ConversationRepositoryPort = Depends(get_conversation_repo),
) -> ChatResponse:
    """整段对话：落库 user/assistant，返回 ``ChatResponse``（含 ``session_id``）。"""
    body = _resolve_session(body)
    logging.info(f"接受到整体对话请求：{body.message}，session_id:{body.session_id}")
    _require_api_key(settings)
    try:
        content = await reply_single_turn(
            repo,
            llm,
            body.session_id,
            body.message,
            settings,
        )
    except _LLM_STREAM_FAILURES as e:
        raise HTTPException(
            status_code=llm_chain_failure_http_status(e),
            detail=llm_chain_failure_detail(e),
        ) from e
    logging.info(f"大模型返回结果：{content}")
    assistant_blocks = text_message("assistant", content)["content"]
    return ChatResponse(content=assistant_blocks, session_id=body.session_id)


@router.post("/chat/stream")
async def post_chat_stream(
    body: ChatRequest,
    settings: Settings = Depends(get_settings),
    llm: ModelAdapter = Depends(get_llm_client),
    repo: ConversationRepositoryPort = Depends(get_conversation_repo),
) -> StreamingResponse:
    """SSE 流式对话：首包前失败走 HTTP；流中失败发 ``error`` 事件；``X-Session-Id`` 在响应头回传。"""
    _require_api_key(settings)
    body = _resolve_session(body)
    logging.info(f"接受到流式对话请求：{body.message}，session_id:{body.session_id}")

    response_headers = {**_SSE_HEADERS, "X-Session-Id": body.session_id}

    # ── 中断注册表 ───────────────────────────────────────────────
    registry = get_sse_registry()

    async def on_connect(handle: StreamHandle) -> None:
        """LLM 连接建立后注册到中断注册表。"""
        await registry.register(body.session_id, handle)

    if body.mode == "agent":
        stream_it = reply_with_agent(
            repo, llm, body.session_id, body.session_kind, body.message, settings, body.approval_mode,
            on_connect=on_connect,
            mcp_servers=body.mcp_servers,
            mcp_server_ids=body.mcp_server_ids,
            self_system=body.self_system,
            image_urls=body.image_urls,
        )
    else:
        stream_it = reply_single_turn_stream(
            repo, llm, body.session_id, body.message, settings,
            on_connect=on_connect,
        )
    agen = stream_it.__aiter__()
    try:
        first_kind, first_delta = await agen.__anext__()
    except StopAsyncIteration:
        logging.warning("大模型无增量返回")
        await registry.unregister(body.session_id)

        async def empty_stream() -> AsyncIterator[str]:
            """无增量时仅结束标记。"""
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            empty_stream(),
            media_type="text/event-stream",
            headers=response_headers,
        )
    except _LLM_STREAM_FAILURES as e:
        await registry.unregister(body.session_id)
        raise HTTPException(
            status_code=llm_chain_failure_http_status(e),
            detail=llm_chain_failure_detail(e),
        ) from e

    async def event_stream() -> AsyncIterator[str]:
        """通过 StreamEventDispatcher 派发每个 (kind, delta)，正常结束或错误后输出 ``[DONE]``。"""
        try:
            yield StreamEventDispatcher.dispatch(first_kind, first_delta)
            try:
                async for kind, delta in agen:
                    yield StreamEventDispatcher.dispatch(kind, delta)
                yield "data: [DONE]\n\n"
            except _LLM_STREAM_FAILURES as e:
                yield _sse_error_line(e)
                yield "data: [DONE]\n\n"
            except asyncio.CancelledError:
                # 客户端断开 SSE 连接，静默终止，不打印错误堆栈
                yield "data: [DONE]\n\n"
        finally:
            await registry.unregister(body.session_id)
            await get_approval_registry().unregister(body.session_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=response_headers,
    )


@router.post("/chat/stream/interrupt")
async def interrupt_stream(body: InterruptRequest) -> dict:
    """中断指定会话的活跃流式连接。

    关闭上游 StreamHandle（LLM HTTP 连接），流式生成器随之结束。
    前端检测到流中断后，可自行通过 ``POST /v1/sessions/{session_id}/messages`` 保存 partial 内容。
    """
    registry = get_sse_registry()
    ok = await registry.interrupt(body.session_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active stream for session {body.session_id}",
        )
    logging.info(f"会话 {body.session_id} 流式连接已中断")

    # 级联终止该会话下所有活跃的 sub-agent run
    try:
        from lumen_agent.application.service.sub_agent_service import get_sub_agent_service
        service = get_sub_agent_service()
        for run_id, handle in list(service._runs.items()):
            if (
                handle.parent_session_id == body.session_id
                and handle.status in ("running", "asking", "starting")
            ):
                logging.info("级联终止 sub-agent run: %s", run_id)
                await service.stop_run(run_id)
    except Exception:
        logging.exception("级联终止 sub-agent 时出错")

    return {"status": "interrupted", "session_id": body.session_id}


@router.post("/chat/stream/approve", response_model=ApproveResponse)
async def approve_tool_call(body: ApproveRequest) -> ApproveResponse:
    """提交工具调用审批决策。批量提交 tool_call_id → 批准/拒绝。"""
    registry = get_approval_registry()
    updated = 0
    logging.info(
        "审批提交请求: session=%s approvals=%s pending_keys=%s",
        body.session_id, body.approvals,
        list(registry._pending.keys()) if hasattr(registry, '_pending') else '?',
    )
    for tool_call_id, decision in body.approvals.items():
        ok = await registry.approve(body.session_id, tool_call_id, decision)
        if ok:
            updated += 1
    logging.info("审批提交: session=%s updated=%d", body.session_id, updated)
    return ApproveResponse(status="ok", updated=updated)
