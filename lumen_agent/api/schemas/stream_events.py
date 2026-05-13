"""SSE 下行事件体（`text/event-stream` 中每条 `data:` 的 JSON）。

说明：
- 这些模型**不作为** `StreamingResponse` 的 `response_model`（OpenAPI 对流式 body 支持有限）。
- 用于路由内 `model_dump_json()`，与前端约定字段形状，避免手写 `dict` 拼错键名。
"""

from typing import Literal

from pydantic import BaseModel, Field


class StreamMessageUpdateData(BaseModel):
    """`message_update` 事件载荷。"""

    delta: str = Field(..., description="本轮助手增量文本")


class StreamMessageUpdateEvent(BaseModel):
    """增量文本事件（对齐开发指南阶段 2 的 message_update 命名）。"""

    type: Literal["message_update"] = "message_update"
    data: StreamMessageUpdateData


class StreamErrorData(BaseModel):
    """流中错误事件载荷（与 `HTTPException.detail` 同源文案）。"""

    message: str = Field(..., description="错误说明")


class StreamErrorEvent(BaseModel):
    """流式过程中失败且已建立 SSE 后发送，随后应结束流。"""

    type: Literal["error"] = "error"
    data: StreamErrorData
