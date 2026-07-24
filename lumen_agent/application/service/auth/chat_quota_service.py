"""普通用户每日 ChatRun 额度的业务规则。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from lumen_agent.config import Settings, resolve_db_path
from lumen_agent.infrastructure.data_base.sqlite_daily_chat_usage import (
    SqliteDailyChatUsageRepository,
)


@dataclass(frozen=True)
class ChatQuotaReservation:
    user_id: str
    usage_date: str
    limit: int
    used_rounds: int
    reset_at: str


class DailyChatQuotaExceededError(Exception):
    """普通用户当天已达到允许的对话轮数。"""

    def __init__(self, *, limit: int, usage_date: str, reset_at: str) -> None:
        super().__init__("daily chat round limit exceeded")
        self.limit = limit
        self.usage_date = usage_date
        self.reset_at = reset_at


def _quota_window(settings: Settings) -> tuple[str, str]:
    timezone_name = str(
        settings.get("AUTH_DAILY_QUOTA_TIMEZONE", "Asia/Shanghai")
    )
    zone = ZoneInfo(timezone_name)
    now = datetime.now(zone)
    next_date = now.date() + timedelta(days=1)
    reset_at = datetime.combine(next_date, time.min, tzinfo=zone).isoformat()
    return now.date().isoformat(), reset_at


async def reserve_chat_turn(
    user: dict | None,
    settings: Settings,
) -> ChatQuotaReservation | None:
    """管理员、无限账号和关闭认证的本地模式不占用每日额度。"""
    if user is None or user.get("role") == "admin" or user.get("unlimited"):
        return None

    limit = max(0, int(user.get("daily_round_limit", 3)))
    usage_date, reset_at = _quota_window(settings)
    repo = SqliteDailyChatUsageRepository(resolve_db_path(settings))
    used_rounds = await repo.reserve(
        usage_date=usage_date,
        user_id=str(user["id"]),
        limit=limit,
    )
    if used_rounds is None:
        raise DailyChatQuotaExceededError(
            limit=limit,
            usage_date=usage_date,
            reset_at=reset_at,
        )
    return ChatQuotaReservation(
        user_id=str(user["id"]),
        usage_date=usage_date,
        limit=limit,
        used_rounds=used_rounds,
        reset_at=reset_at,
    )


async def release_chat_turn(
    reservation: ChatQuotaReservation | None,
    settings: Settings,
) -> None:
    """仅在ChatRun没有创建成功时退还已预占额度。"""
    if reservation is None:
        return
    repo = SqliteDailyChatUsageRepository(resolve_db_path(settings))
    await repo.release(
        usage_date=reservation.usage_date,
        user_id=reservation.user_id,
    )
