"""会话列表与历史查询。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from lumen_agent.api.dependency import get_conversation_repo
from lumen_agent.api.schemas.session_dtos import (
    SessionSummary,
    SessionSummaryDetail,
    StoredMessage,
)
from lumen_agent.domain.ports import ConversationRepositoryPort

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionSummary])
async def list_sessions(
    limit: int = 50,
    offset: int = 0,
    repo: ConversationRepositoryPort = Depends(get_conversation_repo),
) -> list[SessionSummary]:
    """分页列出会话摘要。"""
    rows = await repo.list_sessions(limit=limit, offset=offset)
    return [SessionSummary.model_validate(r) for r in rows]


@router.get("/{session_id}/messages", response_model=list[StoredMessage])
async def get_session_messages(
    session_id: Annotated[str, Path(min_length=1)],
    repo: ConversationRepositoryPort = Depends(get_conversation_repo),
) -> list[StoredMessage]:
    """返回指定会话下的全部消息（按存储顺序）。"""
    messages = await repo.list_messages(session_id, is_all=False)
    return [StoredMessage.model_validate(m) for m in messages]


@router.get("/{session_id}/summary", response_model=SessionSummaryDetail)
async def get_session_summary(
    session_id: Annotated[str, Path(min_length=1)],
    repo: ConversationRepositoryPort = Depends(get_conversation_repo),
) -> SessionSummaryDetail:
    """返回指定会话的当前摘要与未压缩轮次计数。"""
    session = await repo.get_session(session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="session not found")
    return SessionSummaryDetail(
        session_id=session["id"],
        summary=session["summary"],
        count=session["count"],
    )
