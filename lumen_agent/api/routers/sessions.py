"""会话列表、历史查询与消息管理。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from lumen_agent.api.dependency import get_conversation_repo
from lumen_agent.api.schemas.session_dtos import (
    AppendMessageRequest,
    SessionSummary,
    SessionSummaryDetail,
    StoredMessage,
)
from lumen_agent.domain.messages import normalize_content_blocks, text_message
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


@router.post("/{session_id}/messages", status_code=status.HTTP_201_CREATED)
async def append_session_message(
    session_id: Annotated[str, Path(min_length=1)],
    body: AppendMessageRequest,
    repo: ConversationRepositoryPort = Depends(get_conversation_repo),
) -> dict:
    """为指定会话追加一条消息，前端可自定义 ``status``。

    用途示例：
    - 中断后保存 partial 内容 → ``status=0``
    - 恢复上下文时插入系统消息 → ``status=1``
    """
    await repo.ensure_session(session_id)
    if isinstance(body.content, list):
        # content 此时已是 list[dict]，直接透传给仓储层
        content = body.content
    else:
        content = text_message(body.role, body.content)["content"]
    content = normalize_content_blocks(content)
    await repo.append_message(session_id, body.role, content, status=body.status)
    return {"status": "ok", "session_id": session_id}


@router.delete("/{session_id}", status_code=status.HTTP_200_OK)
async def delete_session(
    session_id: Annotated[str, Path(min_length=1)],
    repo: ConversationRepositoryPort = Depends(get_conversation_repo),
) -> dict:
    """删除指定会话及其全部消息。"""
    deleted = await repo.delete_session(session_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="session not found")
    return {"status": "deleted", "session_id": session_id}
