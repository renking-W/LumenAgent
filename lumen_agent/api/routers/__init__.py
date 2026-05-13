"""按业务域拆分的 FastAPI `APIRouter` 模块。

约定：
- 每个文件导出一个名为 `router` 的 `APIRouter` 实例，供 `app.py` `include_router`。
- 路径尽量语义化（例如 `/v1/chat`），版本前缀优先放在 router 的 `prefix` 上，便于未来 `/v2`。
"""
