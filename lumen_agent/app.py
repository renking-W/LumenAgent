"""FastAPI 应用入口（ASGI 应用组装与可选的内嵌启动）。

本文件承担三类职责（从「进程启动」到「对外提供 HTTP」）：

1. **应用工厂 `create_app()`**
   - 创建 `FastAPI` 实例（OpenAPI 文档、路由表、中间件栈、lifespan 钩子等都在此装配）。
   - 这是推荐的结构：测试代码可以 `create_app()` 得到干净实例；生产可用
     `uvicorn lumen_agent.app:app` 指向模块级 `app` 变量。

2. **模块级 `app`**
   - `uvicorn lumen_agent.app:app` 中的第二个 `app` 即此对象。
   - 在 import 本模块时执行一次 `create_app()`，因此「初始化」发生在 worker 进程加载代码阶段。

3. **`main()` + `if __name__ == "__main__"`**
   - 便于本地一条命令启动：`python -m lumen_agent.app`。
   - 注意：生产环境更常见的是由进程管理器/容器直接调用 `uvicorn` CLI，而不是依赖 `main()`。

分层提醒（与仓库其它目录配合）：
- `api/`：HTTP 边界（路由、DTO、依赖注入装配入口 `dependency.py`）。
- `application/`：用例编排（不直接关心 HTTP 细节）。
- `domain/`：端口（Protocol）与纯领域概念。
- `infrastructure/`：端口实现（例如 DeepSeek HTTP 客户端）。

本文件刻意保持「薄」：不写业务分支，只做装配与启动参数读取。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lumen_agent.api.routers import chat as chat_router
from lumen_agent.config import get_settings


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用级异步生命周期（startup/shutdown）。

    FastAPI 0.93+ 推荐使用 `lifespan` 取代 `@app.on_event("startup")` 风格。

    执行顺序（概念上）：
    - `yield` **之前**：服务开始接受请求前运行（适合做连接池初始化、后台任务注册等）。
    - `yield` **之后**：服务关闭阶段运行（适合 flush、关闭连接、取消后台任务等）。

    参数 `_app`：当前 FastAPI 实例；若暂不使用，以下划线命名避免静态检查告警。

    当前项目尚处早期阶段，因此这里仅占位；后续可在此创建全局 `httpx.AsyncClient`
    或数据库引擎，并通过 `app.state` 暴露给依赖函数使用。
    """
    # 预留：启动时连接池、关闭时 flush 等
    yield


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例（工厂函数）。

    为什么要有工厂函数而不是把所有东西写在模块顶层？
    - **可测试**：单测里可以多次 `create_app()`，或配合 dependency_overrides。
    - **可扩展**：未来若需要按环境返回不同中间件/路由组合，工厂是最自然的扩展点。

    Returns:
        已挂载中间件与路由、可交给 ASGI 服务器运行的 `FastAPI` 实例。
    """
    # 读取统一配置（环境变量 / .env）；此处不缓存引用到 app.state，避免与 get_settings 单例语义重复。
    settings = get_settings()

    # 元数据会出现在 OpenAPI（/docs、/openapi.json）里，便于前端/运维识别服务版本。
    application = FastAPI(
        title="Lumen Agent",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS：浏览器跨域访问时需要。独立前端（Vite/React 等）在另一个 origin 上开发时尤其常见。
    # 生产环境务必收紧 allow_origins（不要用 "*"，尤其当 allow_credentials=True 时）。
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 健康检查：负载均衡器/容器探针通常访问此端点；保持轻量，不要依赖外部系统。
    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # 将各 `APIRouter` 挂载到主应用。路由文件只定义相对路径，这里决定「是否加全局前缀」。
    # chat 路由在 `api/routers/session_dtos.py` 内已使用 prefix="/v1"，因此最终路径形如 POST /v1/chat。
    application.include_router(chat_router.router)

    return application


# ASGI 应用对象：uvicorn / hypercorn / gunicorn worker 都会 import 这个符号。
# 注意：import 本模块会立即执行 `create_app()`；因此避免在 `create_app()` 里做非常重的阻塞初始化。
app = create_app()


def main() -> None:
    """使用 uvicorn 启动内嵌开发服务器（可选入口）。

    典型用法（在仓库根目录）：
        python -m lumen_agent.app

    说明：
    - `uvicorn.run(..., "lumen_agent.app:app", ...)` 以 **导入字符串** 指定应用路径，
      这样 `reload=True` 时子进程能重新 import 模块，实现热重载。
    - 若你用命令行 `uvicorn lumen_agent.app:app`，通常不会走到 `main()`。
    """
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "lumen_agent.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )


if __name__ == "__main__":
    main()
