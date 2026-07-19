"""SSE 每条 `data:` 的 JSON 形状 + 统一事件派发器。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, Field


# ── 文本 / 思维链 ──────────────────────────────────────────────────────────────

class StreamTextData(BaseModel):
    delta: str


class StreamTextEvent(BaseModel):
    type: Literal["text"] = "text"
    data: StreamTextData


class StreamThinkingEvent(BaseModel):
    """思维链增量事件（DeepSeek thinking 模式下的 reasoning_content，已转为内部 thinking）。"""

    type: Literal["thinking"] = "thinking"
    data: StreamTextData


# ── 工具调用通知 ───────────────────────────────────────────────────────────────

class ToolCallsEventData(BaseModel):
    """本轮模型发起的工具调用列表。"""

    tool_calls: list[dict[str, Any]]   # [{"name": "read", "id": "call_xxx"}, ...]


class ToolCallsEvent(BaseModel):
    """通知前端：模型本轮发起了 N 个工具调用。"""

    type: Literal["tool_calls"] = "tool_calls"
    data: ToolCallsEventData


class StreamToolUseData(BaseModel):
    tool_call_id: str
    name: str
    arguments: dict[str, Any]


class StreamToolUseEvent(BaseModel):
    """单个工具开始执行。"""

    type: Literal["tool_use"] = "tool_use"
    data: StreamToolUseData


class StreamToolResultData(BaseModel):
    tool_call_id: str
    name: str
    status: str           # "success" | "error"
    execution_time: float
    result_preview: str   # 前 200 字符，非完整数据


class StreamToolResultEvent(BaseModel):
    """单个工具执行完毕。"""

    type: Literal["tool_result"] = "tool_result"
    data: StreamToolResultData


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


# ── 工具调用审批 ───────────────────────────────────────────────────────────────

class AwaitingApprovalData(BaseModel):
    """通知前端：本轮有工具等待人工审批。"""

    tool_calls: list[dict]  # [{"id", "name", "input"}, ...]


class AwaitingApprovalEvent(BaseModel):
    type: Literal["awaiting_approval"] = "awaiting_approval"
    data: AwaitingApprovalData


class ApprovalResultData(BaseModel):
    """单个工具调用已经确认的审批结果。"""

    tool_call_id: str
    approved: bool


class ApprovalResultEvent(BaseModel):
    """供实时订阅和历史补放恢复审批卡片状态。"""

    type: Literal["approval_result"] = "approval_result"
    data: ApprovalResultData


# ── 派发器 ────────────────────────────────────────────────────────────────────

def _make_tool_calls_event(data: Any) -> BaseModel:
    return ToolCallsEvent(data=ToolCallsEventData(tool_calls=data))


def _make_tool_use_event(data: Any) -> BaseModel:
    return StreamToolUseEvent(
        data=StreamToolUseData(
            tool_call_id=data.get("tool_call_id", ""),
            name=data.get("name", ""),
            arguments=data.get("arguments", {}),
        )
    )


def _make_tool_result_event(data: Any) -> BaseModel:
    return StreamToolResultEvent(
        data=StreamToolResultData(
            tool_call_id=data.get("tool_call_id", ""),
            name=data.get("name", ""),
            status=data.get("status", ""),
            execution_time=float(data.get("execution_time", 0.0)),
            result_preview=data.get("result_preview", ""),
        )
    )


# kind → SSE 事件工厂；新增块类型只需在此注册，路由层无需修改
_EVENT_REGISTRY: dict[str, Callable[[Any], BaseModel]] = {
    "text": lambda d: StreamTextEvent(
        data=StreamTextData(delta=d)
    ),
    "thinking": lambda d: StreamThinkingEvent(
        data=StreamTextData(delta=d)
    ),
    "tool_calls": _make_tool_calls_event,
    "awaiting_approval": lambda d: AwaitingApprovalEvent(
        data=AwaitingApprovalData(tool_calls=d)
    ),
    "approval_result": lambda d: ApprovalResultEvent(
        data=ApprovalResultData(
            tool_call_id=d.get("tool_call_id", ""),
            approved=bool(d.get("approved", False)),
        )
    ),
    "tool_use": _make_tool_use_event,
    "tool_result": _make_tool_result_event,
    "done": lambda _: AssistantDoneEvent(),
    "error": lambda d: StreamErrorEvent(data=StreamErrorData(message=str(d))),
}


class StreamEventDispatcher:
    """根据 kind 将 ``(kind, data)`` 转为对应的 SSE ``data: ...\\n\\n`` 行。"""

    @staticmethod
    def serialize(kind: str, data: str | dict | list) -> str:
        """将内部事件序列化为纯 JSON，不添加 SSE 的 id/data 外壳。"""
        factory = _EVENT_REGISTRY.get(kind, _EVENT_REGISTRY["text"])
        event = factory(data)
        return event.model_dump_json()

    def dispatch(kind: str, data: str | dict | list) -> str:
        """已注册的 kind 映射到对应 SSE 行；未注册 kind 降级为 ``text``。"""
        return f"data: {StreamEventDispatcher.serialize(kind, data)}\n\n"
