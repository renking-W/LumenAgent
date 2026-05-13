"""对话相关 HTTP 路由（OpenAPI 边界）。

本模块只做「Web 层」该做的事：
- 声明 URL、方法、标签（影响 `/docs` 分组）
- 使用 Pydantic schema 固定请求体 / SSE 事件 JSON 形状
- 将异常映射为合适的 HTTP 状态码（尽量不泄漏内部堆栈到 detail）

刻意不做：
- 直接拼 httpx 请求（那在 `infrastructure/deepseek_client.py`）
- 复杂业务编排（那在 `application/chat_service.py`）

路径说明：
- `APIRouter(prefix="/v1")` + `@router.post("/chat")` => **`POST /v1/chat`**
- `APIRouter(prefix="/v1")` + `@router.post("/chat/stream")` => **`POST /v1/chat/stream`**（SSE）
"""

from typing import Annotated, AsyncIterator

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from lumen_agent.api.dependency import get_llm_client
from lumen_agent.api.schemas.session_dtos import ChatRequest, ChatResponse
from lumen_agent.api.schemas.stream_events import (
    StreamErrorData,
    StreamErrorEvent,
    StreamMessageUpdateData,
    StreamMessageUpdateEvent,
)
from lumen_agent.application.chat_service import reply_single_turn, reply_single_turn_stream
from lumen_agent.application.llm_error_policy import (
    llm_chain_failure_detail,
    llm_chain_failure_http_status,
)
from lumen_agent.config import Settings, get_settings
from lumen_agent.domain.ports import LLMClientPort

# tags：OpenAPI 文档分组；prefix：为该 router 下所有路径加统一前缀。
router = APIRouter(prefix="/v1", tags=["chat"])

_LLM_STREAM_FAILURES = (httpx.HTTPStatusError, httpx.RequestError, RuntimeError)

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _sse_data_line(event: StreamMessageUpdateEvent | StreamErrorEvent) -> str:
    return f"data: {event.model_dump_json()}\n\n"


@router.post("/chat", response_model=ChatResponse)
async def post_chat(
    body: ChatRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    llm: Annotated[LLMClientPort, Depends(get_llm_client)],
) -> ChatResponse:
    """最小对话接口：用户输入一句话，返回模型一句话。

    错误语义（尽量对齐常见网关实践）：
    - **503**：本服务配置缺失（未配 API Key），属于“服务端未就绪/未配置”，不是客户端拼错字段。
    - **502**：上游 DeepSeek 或网络链路失败（或响应结构不符合最小可用假设）。

    注意：
    - `detail` 在 502 时可能包含上游响应体片段，用于排障；生产若担心信息外泄，应加脱敏/日志分流。
    """
    # 配置缺失：尽早失败，避免无意义打到公网（也避免 httpx 报更难懂的 TLS/HTTP 错误）。
    if not settings.deepseek_api_key.strip():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DEEPSEEK_API_KEY is not configured",
        )

    try:
        # 业务编排入口：当前仅单轮；未来可在此注入 session_id、用户身份、审计 id 等。
        content = await reply_single_turn(llm, body.message)
    except _LLM_STREAM_FAILURES as e:
        raise HTTPException(
            status_code=llm_chain_failure_http_status(e),
            detail=llm_chain_failure_detail(e),
        ) from e

    return ChatResponse(content=content)


@router.post("/chat/stream")
async def post_chat_stream(
    body: ChatRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    llm: Annotated[LLMClientPort, Depends(get_llm_client)],
) -> StreamingResponse:
    """SSE 流式对话：事件 JSON 与 `api/schemas/stream_events.py` 一致，结束行为 `data: [DONE]`。

    在**尚未向客户端写出任何 SSE 行**前发生的失败：返回与普通 `POST /v1/chat` 相同的 JSON `HTTPException`。
    已开始推流后的失败：写入 `type=error` 事件，`data.message` 与上述 `detail` 同源（`llm_chain_failure_detail`）。
    """
    if not settings.deepseek_api_key.strip():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DEEPSEEK_API_KEY is not configured",
        )

    stream_it = reply_single_turn_stream(llm, body.message)
    agen = stream_it.__aiter__()
    try:
        first_delta = await agen.__anext__()
    except StopAsyncIteration:
        async def empty_stream() -> AsyncIterator[str]:
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            empty_stream(),
            media_type="text/event-stream",
            headers=_SSE_HEADERS,
        )
    except _LLM_STREAM_FAILURES as e:
        raise HTTPException(
            status_code=llm_chain_failure_http_status(e),
            detail=llm_chain_failure_detail(e),
        ) from e

    async def event_stream() -> AsyncIterator[str]:
        yield _sse_data_line(
            StreamMessageUpdateEvent(data=StreamMessageUpdateData(delta=first_delta)),
        )
        try:
            while True:
                delta = await agen.__anext__()
                yield _sse_data_line(
                    StreamMessageUpdateEvent(data=StreamMessageUpdateData(delta=delta)),
                )
        except StopAsyncIteration:
            yield "data: [DONE]\n\n"
        except _LLM_STREAM_FAILURES as e:
            yield _sse_data_line(
                StreamErrorEvent(data=StreamErrorData(message=llm_chain_failure_detail(e))),
            )
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
