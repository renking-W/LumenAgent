"""`api` 包：HTTP 边界（路由、DTO、依赖装配）。

分层约定（与 `application/`、`domain/`、`infrastructure/` 配合）：
- **schemas**：请求/响应 JSON 形状（Pydantic）。
- **routers**：路径、依赖注入、HTTP 状态码映射。
- **dependency**：`Depends(...)` 工厂函数集合（装配基础设施实现，见 `dependency.py`）。

不要把重业务逻辑写在本包；编排请放 `application/`。
"""
