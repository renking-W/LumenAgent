"""管理员用户管理路由：账号、额度和用户会话。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from lumen_agent.api.dependency import (
    get_conversation_repo,
    get_settings,
    require_admin,
)
from lumen_agent.api.schemas.admin_user_dtos import (
    AdminUserItem,
    AdminUserListResponse,
    AdminUserSessionListResponse,
    CreateAdminUserRequest,
    UpdateAdminPasswordRequest,
    UpdateAdminUserRequest,
)
from lumen_agent.application.service.auth.admin_user_service import (
    AdminSelfProtectionError,
    AdminUserConflictError,
    AdminUserNotFoundError,
    create_user as svc_create_user,
    list_user_sessions as svc_list_user_sessions,
    list_users as svc_list_users,
    update_password as svc_update_password,
    update_user as svc_update_user,
)
from lumen_agent.config import Settings, resolve_db_path
from lumen_agent.domain.ports import ConversationRepositoryPort
from lumen_agent.infrastructure.data_base.sqlite_daily_chat_usage import (
    SqliteDailyChatUsageRepository,
)
from lumen_agent.infrastructure.data_base.sqlite_user import SqliteUserRepository

router = APIRouter(prefix="/v1/admin/users", tags=["admin-users"])


def _get_user_repo(
    settings: Settings = Depends(get_settings),
) -> SqliteUserRepository:
    """注入用户仓储。"""
    return SqliteUserRepository(resolve_db_path(settings))


def _get_usage_repo(
    settings: Settings = Depends(get_settings),
) -> SqliteDailyChatUsageRepository:
    """注入每日对话用量仓储。"""
    return SqliteDailyChatUsageRepository(resolve_db_path(settings))


@router.get("", response_model=AdminUserListResponse)
async def list_users(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    query: str = Query(default="", max_length=64),
    enabled: bool | None = None,
    user_repo: SqliteUserRepository = Depends(_get_user_repo),
    usage_repo: SqliteDailyChatUsageRepository = Depends(_get_usage_repo),
    conversation_repo: ConversationRepositoryPort = Depends(get_conversation_repo),
    settings: Settings = Depends(get_settings),
) -> AdminUserListResponse:
    """分页返回用户、今日额度使用量和会话数量。"""
    return await svc_list_users(
        user_repo,
        usage_repo,
        conversation_repo,
        settings,
        limit=limit,
        offset=offset,
        query=query.strip(),
        enabled=enabled,
    )


@router.post(
    "",
    response_model=AdminUserItem,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    body: CreateAdminUserRequest,
    user_repo: SqliteUserRepository = Depends(_get_user_repo),
) -> AdminUserItem:
    """创建普通用户或管理员账号。"""
    try:
        return await svc_create_user(user_repo, body)
    except AdminUserConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.patch("/{user_id}", response_model=AdminUserItem)
async def update_user(
    user_id: str,
    body: UpdateAdminUserRequest,
    current_admin: dict | None = Depends(require_admin),
    user_repo: SqliteUserRepository = Depends(_get_user_repo),
) -> AdminUserItem:
    """修改用户角色、每日额度、无限权限或启用状态。"""
    try:
        return await svc_update_user(
            user_repo,
            user_id,
            body,
            current_admin_id=str(current_admin["id"]) if current_admin else None,
        )
    except AdminUserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except AdminSelfProtectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.put("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def update_password(
    user_id: str,
    body: UpdateAdminPasswordRequest,
    user_repo: SqliteUserRepository = Depends(_get_user_repo),
) -> None:
    """重置用户密码，不主动撤销现有无状态令牌。"""
    try:
        await svc_update_password(user_repo, user_id, body.password)
    except AdminUserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{user_id}/sessions",
    response_model=AdminUserSessionListResponse,
)
async def list_user_sessions(
    user_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user_repo: SqliteUserRepository = Depends(_get_user_repo),
    conversation_repo: ConversationRepositoryPort = Depends(get_conversation_repo),
) -> AdminUserSessionListResponse:
    """分页返回指定用户拥有的 Session。"""
    try:
        return await svc_list_user_sessions(
            user_repo,
            conversation_repo,
            user_id,
            limit=limit,
            offset=offset,
        )
    except AdminUserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc