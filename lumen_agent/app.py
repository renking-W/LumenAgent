"""FastAPI 入口：`create_app` 装配中间件与路由；`app` 供 uvicorn；`main` 供 `python -m`。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from lumen_agent.api.routers import chat as chat_router
from lumen_agent.api.routers import sessions as sessions_router
from lumen_agent.config import get_settings, log_config


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期钩子（启动/关闭前后可扩展连接池等）。"""
    yield


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
    return application


app = create_app()


def main() -> None:
    """命令行入口：配置日志后以 uvicorn 启动 ASGI 应用。"""
    import uvicorn
    # 日志配置
    log_config()
    settings = get_settings()
    logging.info("流明Agent已经启动，配置读取完毕")
    uvicorn.run(
        "lumen_agent.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )


if __name__ == "__main__":
    main()
