"""FastAPI 入口：`create_app` 装配中间件与路由；`app` 供 uvicorn；`main` 供 `python -m`。"""

import asyncio
import shutil
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
from lumen_agent.api.routers import mcp_servers as mcp_servers_router
from lumen_agent.config import get_settings, log_config

# ── 项目根目录（基于 app.py 位置推断） ─────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
# ── 模板文档目录 ─────────────────────────────────────────────
_DOCS_DIR = Path(__file__).resolve().parent / "agent" / "prompts" / "docs"
# ── 需要拷贝到工作区的文件 ────────────────────────────────────
_WORKSPACE_SEED_FILES = ["ME.md", "MEMORY.md", "RULE.md", "USER.md"]


def _init_workspace() -> None:
    """初始化工作区：work_space 不存在时自动创建目录结构并拷贝模板文件。"""
    workspace = _PROJECT_ROOT / "work_space"
    if workspace.exists():
        return

    logging.info("工作区不存在，触发初始化：%s", workspace)

    # 创建目录结构
    (workspace / "memory").mkdir(parents=True, exist_ok=True)
    (workspace / "skills").mkdir(parents=True, exist_ok=True)

    # 拷贝模板文件
    for filename in _WORKSPACE_SEED_FILES:
        src = _DOCS_DIR / filename
        if src.exists():
            shutil.copy2(src, workspace / filename)
            logging.info("  已拷贝：%s → work_space/%s", filename, filename)
        else:
            logging.warning("  模板文件不存在，跳过：%s", src)

    logging.info("工作区初始化完成：")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期钩子：启动/关闭时管理连接池等。"""
    # ── 初始化工作区（幂等） ─────────────────────────────────
    _init_workspace()

    # ── 启动 MCP 全局管理器（全量连接 enabled 的 MCP Server） ──
    try:
        from lumen_agent.infrastructure.client.mcp_client import get_mcp_manager
        from lumen_agent.infrastructure.data_base.sqlite_mcp import SqliteMCPServerRepository

        settings = get_settings()
        repo = SqliteMCPServerRepository(settings.conversation_db_path_resolved())
        enabled_servers = await repo.list_enabled()
        await get_mcp_manager().start_all(enabled_servers)
        logging.info(
            "MCP 管理器启动，已连接 %s / %s 个服务器",
            len(get_mcp_manager().list_connection_ids()),
            len(enabled_servers),
        )
    except Exception:
        logging.exception("MCP 管理器启动失败")

    # ── 启动时后台索引历史记忆文件 ────────────────────────────
    try:
        asyncio.create_task(_index_memory_on_startup())
    except Exception:
        logging.exception("记忆文件后台索引启动失败")

    yield

    # ── 关闭 MCP 全局连接 ──────────────────────────────────
    from lumen_agent.infrastructure.client.mcp_client import get_mcp_manager

    await get_mcp_manager().close_all()

    # ── 关闭全局 HTTP 连接池（共享 client + 所有活跃流式连接） ──
    from lumen_agent.infrastructure.http_pool import get_http_pool

    await get_http_pool().close_all()

    # ── 关闭知识库 SQLite 长连接 ─────────────────────────────
    from lumen_agent.api.routers.knowledge import _close_rag_service

    await _close_rag_service()


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
    application.include_router(mcp_servers_router.router)
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
    _init_workspace()
    run_uvicorn()


if __name__ == "__main__":
    main()
