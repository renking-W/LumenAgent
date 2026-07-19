"""后台会话运行接口：启动生成、查询状态、续订事件与显式中断。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from lumen_agent.api.dependency import (
    get_conversation_repo,
    get_llm_client,
    verify_api_key,
)
from lumen_agent.api.schemas.chat_run_dtos import (
    ChatRunInterruptResponse,
    ChatRunResponse,
)
from lumen_agent.api.schemas.session_dtos import ChatRequest
from lumen_agent.application.service.chat.chat_service import (
    reply_single_turn_stream,
    reply_with_agent,
)
from lumen_agent.application.service.mcp.mcp_request_context import (
    clear_allowed_server_ids,
)
from lumen_agent.config import Settings, get_settings
from lumen_agent.domain.ports import ConversationRepositoryPort
from lumen_agent.infrastructure.approval_registry import get_approval_registry
from lumen_agent.infrastructure.chat_run_manager import (
    ActiveSessionRunError,
    ChatRun,
    ChatRunManager,
    ChatRunNotFoundError,
    ConnectCallback,
    get_chat_run_manager,
)
from lumen_agent.model_adapters.base import ModelAdapter

# ── 路由与 SSE 基础配置 ─────────────────────────────────────────
router = APIRouter(
    prefix="/v1/chat/runs",
    tags=["chat-runs"],
    dependencies=[Depends(verify_api_key)],
)

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


# ── 请求准备与生产器装配 ─────────────────────────────────────────
def _prepare_request(body: ChatRequest) -> ChatRequest:
    """补齐会话字段，并沿用定时任务无需审批的既有规则。"""
    if body.session_id is None:
        body.session_id = str(uuid4())
        body.session_kind = 0
    if body.session_kind is None:
        body.session_kind = 0
    if body.session_kind == 1:
        body.approval_mode = "none"
    return body


def _require_llm_key(settings: Settings) -> None:
    """启动后台任务前确认主模型密钥已经配置。"""
    if not str(settings.get("LLM_API_KEY", "")).strip():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM_API_KEY is not configured",
        )


def _response(run: ChatRun) -> ChatRunResponse:
    """将内部 ChatRun 快照转换为公开 DTO。"""
    return ChatRunResponse.model_validate(run.snapshot())


async def _produce(
    body: ChatRequest,
    settings: Settings,
    llm: ModelAdapter,
    repo: ConversationRepositoryPort,
    on_connect: ConnectCallback,
) -> AsyncIterator[tuple[str, str | dict | list]]:
    """运行简单对话或 Agent 流，并在任务结束时清理会话级资源。"""
    try:
        if body.mode == "agent":
            # 生成任务持有 MCP 上下文和审批注册，订阅者不参与资源清理。
            stream = reply_with_agent(
                repo,
                llm,
                body.session_id,
                body.session_kind,
                body.message,
                settings,
                body.approval_mode,
                on_connect=on_connect,
                mcp_server_ids=body.mcp_server_ids,
                self_system=body.self_system,
                image_urls=body.image_urls,
            )
        else:
            stream = reply_single_turn_stream(
                repo,
                llm,
                body.session_id,
                body.message,
                settings,
                on_connect=on_connect,
            )
        async for item in stream:
            yield item
    finally:
        if body.mode == "agent":
            clear_allowed_server_ids()
        await get_approval_registry().unregister(body.session_id)


async def start_managed_run(
    body: ChatRequest,
    settings: Settings,
    llm: ModelAdapter,
    repo: ConversationRepositoryPort,
    manager: ChatRunManager,
) -> ChatRun:
    """校验请求并交给 Manager 启动后台生成。"""
    _require_llm_key(settings)
    body = _prepare_request(body)

    def producer(on_connect: ConnectCallback):
        # producer 只负责构造异步事件流；Task 的所有权属于 ChatRunManager。
        return _produce(body, settings, llm, repo, on_connect)

    try:
        return await manager.start(body.session_id, producer)
    except ActiveSessionRunError as exc:
        # 同一 session 并发写消息会破坏顺序，因此明确返回当前 run_id。
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "message": "session already has an active run",
                "session_id": exc.session_id,
                "run_id": exc.run_id,
            },
        ) from exc


# ── Run 生命周期接口 ─────────────────────────────────────────────
@router.post("", response_model=ChatRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_chat_run(
    body: ChatRequest,
    settings: Settings = Depends(get_settings),
    llm: ModelAdapter = Depends(get_llm_client),
    repo: ConversationRepositoryPort = Depends(get_conversation_repo),
) -> ChatRunResponse:
    """启动一轮生成并立即返回运行标识，不等待模型完成。"""
    run = await start_managed_run(
        body,
        settings,
        llm,
        repo,
        get_chat_run_manager(),
    )
    return _response(run)


@router.get("", response_model=list[ChatRunResponse])
async def list_active_chat_runs() -> list[ChatRunResponse]:
    """列出当前进程内所有活跃运行，供刷新后恢复订阅。"""
    snapshots = await get_chat_run_manager().active_runs()
    return [ChatRunResponse.model_validate(item) for item in snapshots]


@router.get("/{run_id}", response_model=ChatRunResponse)
async def get_chat_run(run_id: str) -> ChatRunResponse:
    """查询单个运行的状态和最新事件游标。"""
    try:
        run = await get_chat_run_manager().get(run_id)
    except ChatRunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="chat run not found") from exc
    return _response(run)


@router.get("/{run_id}/events")
async def subscribe_chat_run(
    run_id: str,
    after: int = Query(default=0, ge=0),
) -> StreamingResponse:
    """从指定游标补放事件，并继续订阅实时 SSE。"""
    manager = get_chat_run_manager()
    try:
        run = await manager.get(run_id)
    except ChatRunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="chat run not found") from exc

    async def event_stream() -> AsyncIterator[str]:
        # event_stream 只是订阅者；它退出时不会关闭后台 Task 或模型连接。
        async for event in manager.subscribe(run_id, after=after):
            if event is None:
                # SSE 注释行作为心跳，不进入前端业务事件处理。
                yield ": keep-alive\n\n"
                continue
            # id 用于前端记录游标，data 保持统一 StreamEvent JSON。
            yield f"id: {event.seq}\ndata: {event.payload}\n\n"
        yield "data: [DONE]\n\n"

    headers = {
        **_SSE_HEADERS,
        "X-Session-Id": run.session_id,
        "X-Run-Id": run.run_id,
    }
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=headers,
    )


@router.post(
    "/{run_id}/interrupt",
    response_model=ChatRunInterruptResponse,
)
async def interrupt_chat_run(run_id: str) -> ChatRunInterruptResponse:
    """请求中断唯一对应的后台 Run。"""
    manager = get_chat_run_manager()
    try:
        run = await manager.get(run_id)
    except ChatRunNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="chat run not found") from exc
    if not await manager.interrupt(run_id):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="chat run is not active")
    return ChatRunInterruptResponse(
        status="interrupt_requested",
        run_id=run.run_id,
        session_id=run.session_id,
    )
