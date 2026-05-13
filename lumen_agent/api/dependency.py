"""FastAPI 依赖注入（Dependency Injection）装配入口。

你可以把它类比为 Spring 的 `@Configuration` + `@Bean` 方法集合：集中描述
「路由函数参数如何从容器/工厂获取」，而不是在 `routers/*.py` 里到处 `new`。

FastAPI `Depends` 的核心价值：
- **参数即依赖**：路由函数签名里写 `Depends(get_xxx)`，框架负责调用与缓存（按作用域）。
- **依赖链**：`get_llm_client` 依赖 `get_settings`，框架会按拓扑解析。
- **可覆盖**：测试里 `app.dependency_overrides[get_llm_client] = ...` 可替换实现。

本文件应保持“薄”：
- 不放业务分支（例如计费、权限策略），那些应放在 `application/` 或独立中间件。
- 不放长生命周期资源创建逻辑（除非配合 `yield` 做 cleanup）；复杂资源优先放 `lifespan`。
"""

from typing import Annotated

from fastapi import Depends

from lumen_agent.config import Settings, get_settings
from lumen_agent.infrastructure.deepseek_client import DeepSeekHttpClient


def get_llm_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> DeepSeekHttpClient:
    """构造 `DeepSeekHttpClient`（每个请求一个新实例）。

    说明：
    - 目前 `DeepSeekHttpClient` 很轻量（只保存 settings），因此 **per-request** 构造成本很低。
    - 若未来 client 需要连接池/共享 session，可改为：
        - 在 `lifespan` 创建全局资源挂到 `app.state`
        - 或把本函数改成 `async def` + `yield` 的资源管理模式

    Args:
        settings: 由 FastAPI 注入的全局配置单例。

    Returns:
        可用于调用 DeepSeek API 的客户端实例。
    """
    return DeepSeekHttpClient(settings)
