"""FastAPI 应用工厂：`create_app` 装配中间件与路由；`lifespan` 管理启动/关闭生命周期。"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lumen_agent.api.routers import (
    api_keys as api_keys_router,
    chat as chat_router,
    configs as configs_router,
    knowledge as knowledge_router,
    logs_router,
    mcp_servers as mcp_servers_router,
    mcp_stdio as mcp_stdio_router,
    memories as memories_router,
    scheduler_router,
    sessions as sessions_router,
    skills as skills_router,
    tools as tools_router,
    upload as upload_router,
    vm as vm_router,
    vm_ws as vm_ws_router,
)
from lumen_agent.application.uitls.dir_guide import DirGuide
from lumen_agent.config import get_settings, resolve_cors_origins, resolve_db_path
from lumen_agent.infrastructure.start_need.workspace import init_workspace

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期钩子：启动/关闭时管理连接池等。"""
    # ── 初始化工作区（幂等） ─────────────────────────────────
    init_workspace()

    # ── 启动 MCP 全局管理器（全量连接 enabled 的 HTTP + stdio MCP Server） ──
    try:
        from lumen_agent.model_adapters.client import get_mcp_manager
        from lumen_agent.infrastructure.data_base.sqlite_mcp import SqliteMCPServerRepository
        from lumen_agent.infrastructure.data_base.sqlite_mcp_stdio import SqliteMCPStdioServerRepository

        settings = get_settings()
        db_path = resolve_db_path(settings)

        http_repo = SqliteMCPServerRepository(db_path)
        enabled_http = await http_repo.list_enabled()
        await get_mcp_manager().start_all(enabled_http)

        stdio_repo = SqliteMCPStdioServerRepository(db_path)
        enabled_stdio = await stdio_repo.list_enabled()
        await get_mcp_manager().start_all_stdio(enabled_stdio)

        logging.info(
            "MCP 管理器启动，已连接 %s 个服务器（http=%s stdio=%s）",
            len(get_mcp_manager().list_connection_ids()),
            len(enabled_http),
            len(enabled_stdio),
        )
    except Exception:
        logging.exception("MCP 管理器启动失败")

    # ── 启动时后台索引历史记忆文件 ────────────────────────────
    try:
        asyncio.create_task(_index_memory_on_startup())
    except Exception:
        logging.exception("记忆文件后台索引启动失败")

    # ── 确保至少有一个 API Key（首次启动自动生成） ────────────
    try:
        await _ensure_default_api_key()
    except Exception:
        logging.exception("默认 API Key 初始化失败")

    # ── 启动调度器 + 从 DB 恢复持久化任务 ─────────────────────
    scheduler_enabled = settings.get("SCHEDULER_ENABLED", True)
    if scheduler_enabled:
        try:
            from lumen_agent.infrastructure.scheduler.scheduler_service import (
                SchedulerService,
            )

            tz = settings.get("SCHEDULER_TIMEZONE", "Asia/Shanghai")
            await SchedulerService.start(timezone=tz)
            # 从 DB 恢复用户创建的持久化任务
            await SchedulerService.restore_from_db()
            # 注册系统内置任务（清理过期执行记录等）
            SchedulerService.register_system_tasks()
        except Exception:
            logging.exception("调度器启动失败")

    yield

    # ── 关闭调度器 ─────────────────────────────────────────
    if scheduler_enabled:
        from lumen_agent.infrastructure.scheduler.scheduler_service import SchedulerService

        await SchedulerService.stop()
        logging.info("调度器已停止")

    # ── 关闭 MCP 全局连接 ──────────────────────────────────
    from lumen_agent.model_adapters.client import get_mcp_manager

    await get_mcp_manager().close_all()

    # ── 关闭全局 HTTP 连接池（共享 client + 所有活跃流式连接） ──
    from lumen_agent.infrastructure.http_pool import get_http_pool

    await get_http_pool().close_all()

    # ── 关闭知识库 SQLite 长连接 ─────────────────────────────
    from lumen_agent.api.routers.knowledge import _close_rag_service

    await _close_rag_service()

    # ── 断开所有 VM SSH 连接 ─────────────────────────────────
    try:
        from lumen_agent.application.service.vm_connection_service import (
            get_vm_connection_service,
        )
        await get_vm_connection_service().disconnect_all()
    except Exception:
        logging.exception("VM 连接断开异常")

    # ── 关闭所有 WebSocket 连接 ────────────────────────────────
    try:
        from lumen_agent.infrastructure.websocket_manager import get_ws_manager

        await get_ws_manager().close_all()
    except Exception:
        logging.exception("WebSocket 连接关闭异常")


async def _index_memory_on_startup() -> None:
    """后台任务：全量扫描每日记忆文件，向量化后写入 ChromaDB。"""
    try:
        from lumen_agent.agent.memory.memory_utils import MemoryFileUtils
        from lumen_agent.application.service.memory_rag_service import MemoryRagService

        settings = get_settings()
        workspace_path = DirGuide.workspace_dir()
        memory_utils = MemoryFileUtils.from_workspace_path(workspace_path)
        service = MemoryRagService(settings)
        logging.info("启动后台任务：全量索引历史记忆文件...")
        await service.index_all_memory_files(memory_utils)
    except Exception:
        logging.exception("记忆文件全量索引失败，将在下一次启动时重试")


async def _ensure_default_api_key() -> None:
    """第一次启动时自动生成一个默认 API Key 并打印到日志。"""
    from lumen_agent.application.service.api_key_service import generate_api_key
    from lumen_agent.infrastructure.data_base.sqlite_api_key import (
        SqliteApiKeyRepository,
    )

    settings = get_settings()
    repo = SqliteApiKeyRepository(resolve_db_path(settings))
    count = await repo.count_all()
    if count > 0:
        return  # 已有 Key，无需生成

    raw_key, key_hash = generate_api_key()
    meta = await repo.create(key_hash, name="Default Key")
    border = "=" * 60
    logging.info(border)
    logging.info("首次启动：已自动生成默认 API Key")
    logging.info("Key: %s", raw_key)
    logging.info("ID:  %s", meta["id"])
    logging.info("请妥善保管此密钥，它仅在本次启动时显示一次。")
    logging.info(border)


def create_app() -> FastAPI:
    """创建 FastAPI 实例：CORS、健康检查、挂载所有路由。"""
    settings = get_settings()
    application = FastAPI(
        title="Lumen Agent",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolve_cors_origins(settings),
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
    application.include_router(mcp_stdio_router.router)
    application.include_router(scheduler_router.router)
    application.include_router(api_keys_router.router)
    application.include_router(configs_router.router)
    application.include_router(logs_router.router)
    application.include_router(upload_router.router)
    application.include_router(vm_router.router)
    application.include_router(vm_ws_router.router)
    return application
