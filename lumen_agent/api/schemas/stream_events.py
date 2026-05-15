"""SSE 每条 `data:` 的 JSON 形状 + 统一事件派发器。"""

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel


class StreamMessageUpdateData(BaseModel):
    delta: str


class StreamMessageUpdateEvent(BaseModel):
    type: Literal["message_update"] = "message_update"
    data: StreamMessageUpdateData


class ReasoningUpdateEvent(BaseModel):
    """思维链增量事件（DeepSeek thinking 模式下的 reasoning_content）。"""

    type: Literal["reasoning_update"] = "reasoning_update"
    data: StreamMessageUpdateData


class StreamErrorData(BaseModel):
    message: str


class StreamErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    data: StreamErrorData


# kind → SSE 事件工厂；新增块类型只需在此注册，路由层无需修改
_EVENT_REGISTRY: dict[str, Callable[[str], BaseModel]] = {
    "content": lambda delta: StreamMessageUpdateEvent(
        data=StreamMessageUpdateData(delta=delta)
    ),
    "reasoning_content": lambda delta: ReasoningUpdateEvent(
        data=StreamMessageUpdateData(delta=delta)
    ),
    # 未来扩展示例：
    # "tool_call": lambda delta: ToolCallEvent(data=ToolCallData(delta=delta)),
}


class StreamEventDispatcher:
    """根据 kind 将 ``(kind, delta)`` 转为对应的 SSE ``data: ...\\n\\n`` 行。"""

    @staticmethod
    def dispatch(kind: str, delta: str) -> str:
        """未知 kind 降级为 message_update，保证健壮性。"""
        factory = _EVENT_REGISTRY.get(kind, _EVENT_REGISTRY["content"])
        event = factory(delta)
        return f"data: {event.model_dump_json()}\n\n"
