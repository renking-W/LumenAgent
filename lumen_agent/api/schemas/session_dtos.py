"""HTTP JSON：对话请求 / 响应体与会话 REST DTO。"""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    content: str


class SessionSummary(BaseModel):
    id: str
    created_at: str
    updated_at: str


class StoredMessage(BaseModel):
    role: str
    content: str
