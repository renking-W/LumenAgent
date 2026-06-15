"""Uvicorn 启动器。"""

from __future__ import annotations

import logging

from lumen_agent.config import get_settings

logger = logging.getLogger(__name__)


def run_uvicorn() -> None:
    """启动 uvicorn（不重新配置日志）。"""
    import uvicorn

    settings = get_settings()
    logging.info("流明Agent已经启动，配置读取完毕")
    uvicorn.run(
        "lumen_agent.app:app",
        host=settings.get("HOST", "127.0.0.1"),
        port=settings.get("PORT", 8000),
        reload=settings.get("RELOAD", False),
    )
