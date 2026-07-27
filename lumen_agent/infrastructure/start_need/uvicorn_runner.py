"""Uvicorn 启动器。"""

from __future__ import annotations

import logging

from lumen_agent.config import get_settings

logger = logging.getLogger(__name__)


class _HealthAccessLogFilter(logging.Filter):
    """过滤 Docker/负载均衡健康检查的 uvicorn access 日志。"""

    def filter(self, record: logging.LogRecord) -> bool:
        return "GET /health " not in record.getMessage()


def run_uvicorn() -> None:
    """启动 uvicorn（不重新配置日志）。"""
    import uvicorn

    settings = get_settings()
    logging.getLogger("uvicorn.access").addFilter(_HealthAccessLogFilter())
    logging.info("流明Agent已经启动，配置读取完毕")
    uvicorn.run(
        "lumen_agent.app:app",
        host=settings.get("HOST", "127.0.0.1"),
        port=settings.get("PORT", 8000),
        reload=settings.get("RELOAD", False),
    )
