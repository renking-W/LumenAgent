"""FastAPI 入口：`app` 供 uvicorn；`main` 供 `python -m`。

这个文件保持精简化 —— 实际逻辑分布在：
  - ``api/app_factory.py``    — ``create_app()``、生命周期管理
  - ``infrastructure/workspace.py``   — 工作区初始化
  - ``infrastructure/flask_proxy.py`` — Flask 静态文件 + API 代理
  - ``infrastructure/uvicorn_runner.py`` — uvicorn 启动
"""

from __future__ import annotations

import logging
import threading

from lumen_agent.api.app_factory import create_app
from lumen_agent.config import log_config
from lumen_agent.infrastructure.start_need.flask_proxy import run_frontend
from lumen_agent.infrastructure.start_need.uvicorn_runner import run_uvicorn
from lumen_agent.infrastructure.start_need.workspace import init_workspace

app = create_app()


def main() -> None:
    """Web 入口：启动 Flask 线程 + uvicorn。"""
    log_config()
    init_workspace()

    # Flask 在后台线程运行
    t = threading.Thread(target=run_frontend, daemon=True)
    t.start()

    # uvicorn 在主线程运行（阻塞）
    run_uvicorn()


if __name__ == "__main__":
    main()
