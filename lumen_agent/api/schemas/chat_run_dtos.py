"""后台会话运行 DTO：启动结果、运行状态与中断响应。"""

from typing import Literal

from pydantic import BaseModel


class ChatRunResponse(BaseModel):
    """单轮后台生成的公开状态。"""

    run_id: str
    session_id: str
    status: Literal["running", "completed", "interrupted", "failed"]
    last_event_id: int = 0


class ChatRunInterruptResponse(BaseModel):
    """显式中断请求的确认响应。"""

    status: Literal["interrupt_requested"]
    run_id: str
    session_id: str
