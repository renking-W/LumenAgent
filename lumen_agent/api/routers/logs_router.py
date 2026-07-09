"""日志读取路由：`GET /v1/logs` — 只做 HTTP 编排，业务逻辑委托给 log_service。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from lumen_agent.application.service.common.log_service import count_logs, read_logs

router = APIRouter(prefix="/v1", tags=["logs"])


@router.get("/logs")
async def get_logs(
    lines: int = Query(default=100, ge=1, le=5000, description="返回行数（倒序，最新在前）"),
    offset: int = Query(default=0, ge=0, description="跳过前 N 条匹配行（与 lines 配合滚动分页）"),
    level: str | None = Query(default=None, description="按级别过滤：DEBUG/INFO/WARNING/ERROR/CRITICAL"),
    keyword: str | None = Query(default=None, description="按关键字模糊过滤（忽略大小写）"),
) -> dict[str, Any]:
    """读取 agent.log，支持滚动分页与过滤。"""
    logs = read_logs(lines=lines, offset=offset, level=level, keyword=keyword)
    total = count_logs(level=level, keyword=keyword)

    return {
        "logs": logs,
        "total_lines": total,
        "log_files": ["agent.log"],
    }
