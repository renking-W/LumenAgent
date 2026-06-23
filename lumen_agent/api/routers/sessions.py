"""会话列表、历史查询与消息管理。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from lumen_agent.api.dependency import get_conversation_repo
from lumen_agent.api.schemas.session_dtos import (
    AppendMessageRequest,
    SessionSummary,
    SessionSummaryDetail,
    StoredMessage,
    UpdateTitleRequest,
)
from lumen_agent.application.service.session_service import normalize_and_prepare_content
from lumen_agent.domain.ports import ConversationRepositoryPort

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionSummary])
async def list_sessions(
    limit: int = 50,
    offset: int = 0,
    kind: int | None = None,
    repo: ConversationRepositoryPort = Depends(get_conversation_repo),
) -> list[SessionSummary]:
    """分页列出会话摘要。kind 可选：0=normal, 1=scheduled。"""
    rows = await repo.list_sessions(limit=limit, offset=offset, kind=kind)
    return [SessionSummary.model_validate(r) for r in rows]


@router.get("/{session_id}/messages", response_model=list[StoredMessage])
async def get_session_messages(
    session_id: Annotated[str, Path(min_length=1)],
    limit: int | None = None,
    before: int | None = None,
    repo: ConversationRepositoryPort = Depends(get_conversation_repo),
) -> list[StoredMessage]:
    """返回指定会话下的消息列表（按存储顺序），支持游标滚动分页。

    - 不传 ``limit``：返回全部历史消息（兼容旧版）
    - 传 ``limit``：取最新 ``limit`` 条；配合 ``before`` 实现上翻：
      首次 ``GET /{session_id}/messages?limit=20`` 取最新 20 条，
      后续 ``GET /{session_id}/messages?limit=20&before={min_seq}`` 取更早的 20 条。
    """
    if limit is not None:
        messages = await repo.list_messages_before(session_id, limit, before_seq=before)
    else:
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
        title=session["title"],
        kind=session.get("kind", 0),
    )


@router.put("/{session_id}/title", response_model=dict)
async def update_session_title(
    session_id: Annotated[str, Path(min_length=1)],
    body: UpdateTitleRequest,
    repo: ConversationRepositoryPort = Depends(get_conversation_repo),
) -> dict:
    """修改会话标题。"""
    session = await repo.get_session(session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="session not found")
    await repo.update_session_title(session_id, body.title)
    return {"status": "ok", "session_id": session_id, "title": body.title}


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
    session = await repo.get_session(session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="session not found")
    content = normalize_and_prepare_content(body.role, body.content)
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
