"""FastAPI 入口：`create_app` 装配中间件与路由；`app` 供 uvicorn；`main` 供 `python -m`。"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from lumen_agent.api.routers import chat as chat_router
from lumen_agent.api.routers import sessions as sessions_router
from lumen_agent.api.routers import tools as tools_router
from lumen_agent.api.routers import skills as skills_router
from lumen_agent.api.routers import knowledge as knowledge_router
from lumen_agent.api.routers import memories as memories_router
from lumen_agent.config import get_settings, log_config


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期钩子：启动/关闭时管理连接池等。"""
    # ── 启动时后台索引历史记忆文件 ────────────────────────────
    try:
        asyncio.create_task(_index_memory_on_startup())
    except Exception:
        logging.exception("记忆文件后台索引启动失败")

    yield

    # ── 关闭全局 HTTP 连接池（共享 client + 所有活跃流式连接） ──
    from lumen_agent.infrastructure.http_pool import get_http_pool

    await get_http_pool().close_all()


async def _index_memory_on_startup() -> None:
    """后台任务：全量扫描每日记忆文件，向量化后写入 ChromaDB。"""
    from lumen_agent.agent.memory.memory_utils import MemoryFileUtils
    from lumen_agent.application.service.memory_rag_service import MemoryRagService

    settings = get_settings()
    workspace_path = Path(__file__).resolve().parent.parent / "work_space"
    memory_utils = MemoryFileUtils.from_workspace_path(workspace_path)
    service = MemoryRagService(settings)
    logging.info("启动后台任务：全量索引历史记忆文件...")
    await service.index_all_memory_files(memory_utils)


def create_app() -> FastAPI:
    """创建 FastAPI 实例：CORS、健康检查、挂载 chat / sessions 路由。"""
    settings = get_settings()
    application = FastAPI(
        title="Lumen Agent",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/health")
    async def health() -> dict[str, str]:
        """存活探针，不依赖外部服务。"""
        return {"status": "ok"}

    application.include_router(chat_router.router)
    application.include_router(sessions_router.router)
    application.include_router(tools_router.router)
    application.include_router(skills_router.router)
    application.include_router(knowledge_router.router)
    application.include_router(memories_router.router)
    return application


app = create_app()


def run_uvicorn() -> None:
    """仅启动 uvicorn（不重新配置日志）。"""
    import uvicorn

    settings = get_settings()
    logging.info("流明Agent已经启动，配置读取完毕")
    uvicorn.run(
        "lumen_agent.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )


def main() -> None:
    """Web 入口（仅 HTTP，无 CLI）：配置日志后启动 uvicorn。"""
    log_config()
    run_uvicorn()


if __name__ == "__main__":
    main()
