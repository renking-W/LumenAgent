"""对话接口的 Pydantic DTO（Data Transfer Object）。

这些模型同时承担三件事：
1. **运行时校验**：例如 `message` 最短长度，避免空字符串打到模型。
2. **OpenAPI 文档**：字段描述会出现在 `/docs`，便于前端对齐契约。
3. **（可选）代码生成**：前端可用 openapi-typescript / Orval 从 `/openapi.json` 生成类型与客户端。

与 `domain` 的区别：
- `schemas` 面向 **HTTP JSON**（外部契约），字段命名更偏 API 习惯。
- `domain` 面向 **内部业务概念**（更稳定）；当 API 演进时，domain 不一定跟着变。

后续演进建议：
- `ChatRequest` 增加 `temperature`、`max_tokens` 等参数时，务必给默认值并谨慎兼容旧客户端。
- `ChatResponse` 可增加 `usage`、`model`、`id` 等字段用于排障与计费（同样注意兼容性）。
"""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """POST /v1/chat 请求体。"""

    message: str = Field(..., min_length=1, description="用户输入（单轮最小接口）")
    session_id: str | None = Field(
        default=None,
        description="会话 id：当前版本仅占位，后续接入 SQLite/Postgres 会话表后会真正使用",
    )


class ChatResponse(BaseModel):
    """POST /v1/chat 响应体。"""

    content: str = Field(..., description="模型回复正文（纯文本）")
