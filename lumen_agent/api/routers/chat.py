"""对话路由：`POST /v1/chat` 整段 JSON；`POST /v1/chat/stream` SSE。"""
import logging
from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from lumen_agent.api.dependency import get_conversation_repo, get_llm_client
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
from lumen_agent.domain.ports import ConversationRepositoryPort, LLMClientPort

router = APIRouter(prefix="/v1", tags=["chat"])

_LLM_STREAM_FAILURES = (httpx.HTTPStatusError, httpx.RequestError, RuntimeError)

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _sse_data_line(event: StreamMessageUpdateEvent | StreamErrorEvent) -> str:
    """将事件模型序列化为一行 SSE ``data: ...\\n\\n``。"""
    return f"data: {event.model_dump_json()}\n\n"


def _require_api_key(settings: Settings) -> None:
    """校验API KEY是否配置"""
    if not settings.deepseek_api_key.strip():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DEEPSEEK_API_KEY is not configured",
        )


@router.post("/chat", response_model=ChatResponse)
async def post_chat(
    body: ChatRequest,
    settings: Settings = Depends(get_settings),
    llm: LLMClientPort = Depends(get_llm_client),
    repo: ConversationRepositoryPort = Depends(get_conversation_repo),
) -> ChatResponse:
    """整段对话：落库 user/assistant，返回 ``ChatResponse``。"""
    logging.info(f"接受到整体对话请求：{body.message}，session_id:{body.session_id}")
    _require_api_key(settings)
    try:
        content = await reply_single_turn(
            repo,
            llm,
            body.session_id,
            body.message,
            settings.conversation_max_context_messages,
        )
    except _LLM_STREAM_FAILURES as e:
        raise HTTPException(
            status_code=llm_chain_failure_http_status(e),
            detail=llm_chain_failure_detail(e),
        ) from e
    logging.info(f"大模型返回结果：{content}")
    return ChatResponse(content=content)


@router.post("/chat/stream")
async def post_chat_stream(
    body: ChatRequest,
    settings: Settings = Depends(get_settings),
    llm: LLMClientPort = Depends(get_llm_client),
    repo: ConversationRepositoryPort = Depends(get_conversation_repo),
) -> StreamingResponse:
    """SSE 流式对话：首包前失败走 HTTP；流中失败发 ``error`` 事件。"""
    _require_api_key(settings)

    stream_it = reply_single_turn_stream(
        repo,
        llm,
        body.session_id,
        body.message,
        settings.conversation_max_context_messages,
    )
    agen = stream_it.__aiter__()
    try:
        first_delta = await agen.__anext__()
    except StopAsyncIteration:
        logging.warning("大模型无增量返回")
        async def empty_stream() -> AsyncIterator[str]:
            """无增量时仅结束标记。"""
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
        """输出 ``message_update`` 增量，正常结束或错误后输出 ``[DONE]``。"""
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
