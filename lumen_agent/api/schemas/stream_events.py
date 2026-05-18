"""SSE 每条 `data:` 的 JSON 形状 + 统一事件派发器。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, Field


# ── 文本 / 思维链 ──────────────────────────────────────────────────────────────

class StreamMessageUpdateData(BaseModel):
    delta: str


class StreamMessageUpdateEvent(BaseModel):
    type: Literal["message_update"] = "message_update"
    data: StreamMessageUpdateData


class ReasoningUpdateEvent(BaseModel):
    """思维链增量事件（DeepSeek thinking 模式下的 reasoning_content）。"""

    type: Literal["reasoning_update"] = "reasoning_update"
    data: StreamMessageUpdateData


# ── 工具调用通知 ───────────────────────────────────────────────────────────────

class ToolCallsEventData(BaseModel):
    """本轮模型发起的工具调用列表。"""

    tool_calls: list[dict[str, Any]]   # [{"name": "read", "id": "call_xxx"}, ...]


class ToolCallsEvent(BaseModel):
    """通知前端：模型本轮发起了 N 个工具调用。"""

    type: Literal["tool_calls"] = "tool_calls"
    data: ToolCallsEventData


class ToolExecutionStartData(BaseModel):
    tool_call_id: str
    name: str
    arguments: dict[str, Any]


class ToolExecutionStartEvent(BaseModel):
    """单个工具开始执行。"""

    type: Literal["tool_execution_start"] = "tool_execution_start"
    data: ToolExecutionStartData


class ToolExecutionEndData(BaseModel):
    tool_call_id: str
    name: str
    status: str           # "success" | "error"
    execution_time: float
    result_preview: str   # 前 200 字符，非完整数据


class ToolExecutionEndEvent(BaseModel):
    """单个工具执行完毕。"""

    type: Literal["tool_execution_end"] = "tool_execution_end"
    data: ToolExecutionEndData


class AssistantDoneEvent(BaseModel):
    """Agent 单轮推理结束（正文已由前述 ``message_update`` 增量送达，此处不重复全文）。"""

    type: Literal["assistant_done"] = "assistant_done"
    data: dict[str, Any] = Field(default_factory=dict)


# ── 错误 ───────────────────────────────────────────────────────────────────────

class StreamErrorData(BaseModel):
    message: str


class StreamErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    data: StreamErrorData


# ── 派发器 ────────────────────────────────────────────────────────────────────

def _make_tool_calls_event(data: Any) -> BaseModel:
    return ToolCallsEvent(data=ToolCallsEventData(tool_calls=data))


def _make_tool_execution_start_event(data: Any) -> BaseModel:
    return ToolExecutionStartEvent(
        data=ToolExecutionStartData(
            tool_call_id=data.get("tool_call_id", ""),
            name=data.get("name", ""),
            arguments=data.get("arguments", {}),
        )
    )


def _make_tool_execution_end_event(data: Any) -> BaseModel:
    return ToolExecutionEndEvent(
        data=ToolExecutionEndData(
            tool_call_id=data.get("tool_call_id", ""),
            name=data.get("name", ""),
            status=data.get("status", ""),
            execution_time=float(data.get("execution_time", 0.0)),
            result_preview=data.get("result_preview", ""),
        )
    )


# kind → SSE 事件工厂；新增块类型只需在此注册，路由层无需修改
_EVENT_REGISTRY: dict[str, Callable[[Any], BaseModel]] = {
    "content": lambda d: StreamMessageUpdateEvent(
        data=StreamMessageUpdateData(delta=d)
    ),
    "reasoning_content": lambda d: ReasoningUpdateEvent(
        data=StreamMessageUpdateData(delta=d)
    ),
    "tool_calls": _make_tool_calls_event,
    "tool_execution_start": _make_tool_execution_start_event,
    "tool_execution_end": _make_tool_execution_end_event,
    "done": lambda _: AssistantDoneEvent(),
    "error": lambda d: StreamErrorEvent(data=StreamErrorData(message=str(d))),
}


class StreamEventDispatcher:
    """根据 kind 将 ``(kind, data)`` 转为对应的 SSE ``data: ...\\n\\n`` 行。"""

    @staticmethod
    def dispatch(kind: str, data: str | dict | list) -> str:
        """已注册的 kind 映射到对应 SSE 行；未注册 kind 降级为 ``message_update``（避免静默丢事件）。"""
        factory = _EVENT_REGISTRY.get(kind, _EVENT_REGISTRY["content"])
        event = factory(data)
        return f"data: {event.model_dump_json()}\n\n"
