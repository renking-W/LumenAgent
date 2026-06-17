"""工具调用审批 DTO。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ApproveRequest(BaseModel):
    """审批请求：批量提交工具调用决策。"""

    session_id: str = Field(..., min_length=1, description="会话 ID")
    approvals: dict[str, bool] = Field(
        ...,
        description="tool_call_id → true(批准) / false(拒绝)",
    )


class ApproveResponse(BaseModel):
    """审批响应。"""

    status: str = "ok"
    updated: int = Field(default=0, description="本次生效的决策数")
