"""FastAPI 入口：`app` 供 uvicorn；`main` 供 `python -m`。

这个文件保持精简化 —— 实际逻辑分布在：
  - ``api/app_factory.py``    — ``create_app()``、生命周期管理
  - ``infrastructure/workspace.py``   — 工作区初始化
  - ``infrastructure/uvicorn_runner.py`` — uvicorn 启动
"""

from __future__ import annotations

from lumen_agent.api.app_factory import create_app
from lumen_agent.config import log_config
from lumen_agent.infrastructure.start_need.uvicorn_runner import run_uvicorn
from lumen_agent.infrastructure.start_need.workspace import init_workspace

app = create_app()


def main() -> None:
    """初始化运行目录并启动唯一的 Uvicorn Web 服务。"""
    log_config()
    init_workspace()
    # uvicorn 在主线程运行（阻塞）
    run_uvicorn()


if __name__ == "__main__":
    main()
