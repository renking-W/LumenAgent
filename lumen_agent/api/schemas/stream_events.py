"""SSE 每条 `data:` 的 JSON 形状（供 `model_dump_json`，不作 StreamingResponse 的 response_model）。"""

from typing import Literal

from pydantic import BaseModel


class StreamMessageUpdateData(BaseModel):
    delta: str


class StreamMessageUpdateEvent(BaseModel):
    type: Literal["message_update"] = "message_update"
    data: StreamMessageUpdateData


class StreamErrorData(BaseModel):
    message: str


class StreamErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    data: StreamErrorData
