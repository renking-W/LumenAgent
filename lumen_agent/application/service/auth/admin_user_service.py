"""管理员用户管理服务：账号、额度和用户会话的业务规则。"""

from __future__ import annotations

import asyncio
import sqlite3

from lumen_agent.api.schemas.admin_user_dtos import (
    AdminUserItem,
    AdminUserListResponse,
    AdminUserSessionItem,
    AdminUserSessionListResponse,
    CreateAdminUserRequest,
    UpdateAdminUserRequest,
)
from lumen_agent.application.service.auth.auth_service import hash_password
from lumen_agent.application.service.auth.chat_quota_service import (
    get_quota_window,
)
from lumen_agent.config import Settings
from lumen_agent.infrastructure.data_base.sqlite_conversation import (
    SqliteConversationRepository,
)
from lumen_agent.infrastructure.data_base.sqlite_daily_chat_usage import (
    SqliteDailyChatUsageRepository,
)
from lumen_agent.infrastructure.data_base.sqlite_user import SqliteUserRepository


class AdminUserConflictError(Exception):
    """创建用户时用户名已存在。"""


class AdminUserNotFoundError(Exception):
    """指定用户不存在。"""


class AdminSelfProtectionError(Exception):
    """管理员尝试禁用或降级当前账号。"""


async def list_users(
    user_repo: SqliteUserRepository,
    usage_repo: SqliteDailyChatUsageRepository,
    conversation_repo: SqliteConversationRepository,
    settings: Settings,
    *,
    limit: int,
    offset: int,
    query: str,
    enabled: bool | None,
) -> AdminUserListResponse:
    """分页查询用户，并合并今日用量、会话数和概览统计。"""
    usage_date, _ = get_quota_window(settings)
    rows, total, total_users, enabled_users, unlimited_users, used_rounds_today = await asyncio.gather(
        user_repo.list_users(
            limit=limit,
            offset=offset,
            query=query,
            enabled=enabled,
        ),
        user_repo.count_users(query=query, enabled=enabled),
        user_repo.count_users(),
        user_repo.count_enabled_users(),
        user_repo.count_unlimited_users(),
        usage_repo.total_by_date(usage_date),
    )
    user_ids = [str(row["id"]) for row in rows]
    usage_by_user, sessions_by_user = await asyncio.gather(
        usage_repo.list_by_date(usage_date, user_ids),
        conversation_repo.count_sessions_by_owners(user_ids),
    )
    users = [
        AdminUserItem(
            **row,
            used_rounds=usage_by_user.get(str(row["id"]), 0),
            session_count=sessions_by_user.get(str(row["id"]), 0),
        )
        for row in rows
    ]
    return AdminUserListResponse(
        total=total,
        total_users=total_users,
        enabled_users=enabled_users,
        unlimited_users=unlimited_users,
        used_rounds_today=used_rounds_today,
        usage_date=usage_date,
        users=users,
    )


async def create_user(
    user_repo: SqliteUserRepository,
    body: CreateAdminUserRequest,
) -> AdminUserItem:
    """创建用户，并将数据库唯一键冲突转为明确的业务错误。"""
    username = body.username.strip()
    if not username:
        raise ValueError("用户名不能为空")
    try:
        user = await user_repo.create(
            username=username,
            password_hash=hash_password(body.password),
            role=body.role,
            daily_round_limit=body.daily_round_limit,
            unlimited=body.unlimited,
        )
    except sqlite3.IntegrityError as exc:
        raise AdminUserConflictError("用户名已存在") from exc
    return AdminUserItem(**user)


async def update_user(
    user_repo: SqliteUserRepository,
    user_id: str,
    body: UpdateAdminUserRequest,
    *,
    current_admin_id: str | None,
) -> AdminUserItem:
    """更新用户权限；当前管理员不能禁用或降级自己。"""
    existing = await user_repo.get_by_id(user_id)
    if existing is None:
        raise AdminUserNotFoundError("用户不存在")

    updates = body.model_dump(exclude_none=True)
    if current_admin_id == user_id:
        if updates.get("enabled") is False:
            raise AdminSelfProtectionError("不能禁用当前登录的管理员账号")
        if updates.get("role") not in {None, "admin"}:
            raise AdminSelfProtectionError("不能将当前管理员降级为普通用户")

    updated = await user_repo.update_user(user_id, updates)
    if updated is None:
        raise AdminUserNotFoundError("用户不存在")
    return AdminUserItem(**updated)


async def update_password(
    user_repo: SqliteUserRepository,
    user_id: str,
    password: str,
) -> None:
    """重置指定用户密码。现有无状态令牌继续按原过期时间有效。"""
    updated = await user_repo.update_password(user_id, hash_password(password))
    if not updated:
        raise AdminUserNotFoundError("用户不存在")


async def list_user_sessions(
    user_repo: SqliteUserRepository,
    conversation_repo: SqliteConversationRepository,
    user_id: str,
    *,
    limit: int,
    offset: int,
) -> AdminUserSessionListResponse:
    """分页查询指定用户拥有的 Session。"""
    if await user_repo.get_by_id(user_id) is None:
        raise AdminUserNotFoundError("用户不存在")
    rows, total = await asyncio.gather(
        conversation_repo.list_sessions_by_owner(
            user_id,
            limit=limit,
            offset=offset,
        ),
        conversation_repo.count_sessions_by_owner(user_id),
    )
    return AdminUserSessionListResponse(
        total=total,
        sessions=[AdminUserSessionItem(**row) for row in rows],
    )