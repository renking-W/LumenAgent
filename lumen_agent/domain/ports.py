"""领域层「端口」：用 `typing.Protocol` 描述依赖抽象（面向接口编程）。

为什么用 Protocol 而不是 ABC？
- **结构子类型（structural subtyping）**：实现类只要提供同名同签名的方法，就视为满足协议，
  不需要显式 `implements`（Python 没有这种关键字），更贴近「鸭子类型 + 静态检查」。
- **依赖方向**：`domain` 不引用 `infrastructure`；反过来 `infrastructure` 里的实现类只要方法匹配，
  路由/应用层即可把实现当作 `LLMClientPort` 使用（配合类型检查器体验更好）。

`@runtime_checkable`：
- 允许运行时使用 `isinstance(x, LLMClientPort)` 做检查（有性能成本，不要放在热路径乱用）。
- 对 FastAPI 运行不是必须，但有助于调试/实验代码。

后续可在此继续添加：
- `ConversationRepository`（会话持久化）
- `VectorMemoryPort` / `KnowledgeSearchPort`（记忆与知识库）
"""

from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMClientPort(Protocol):
    """大模型对话客户端端口（对齐 OpenAI Chat Completions 的 messages 语义）。

    `messages` 元素形态（最小集）通常为：
        {"role": "system" | "user" | "assistant" | "tool", "content": "..."}

    当前仓库的最小实现只用到 user/assistant 文本；未来接入工具循环时，会扩展 tool 消息等。

    返回值：
    - 返回 **assistant 的纯文本**（`choices[0].message.content` 字符串形态），
      让 `application` 层保持与具体供应商响应 JSON 解耦。
    """

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
    ) -> str:
        """发送多轮 `messages`，返回助手文本。

        Args:
            messages: OpenAI 兼容 chat messages 列表。
            temperature: 采样温度；`None` 表示使用 `Settings.deepseek_temperature`；若配置也为 `None` 则不在 JSON 里传该字段。

        Returns:
            模型输出文本（非空字符串，具体由实现类保证/抛出异常）。

        Raises:
            由具体实现决定：网络错误、HTTP 4xx/5xx、JSON 结构不符合预期等。
        """
        ...

    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        """流式发送 `messages`，多次 yield 助手文本增量（纯文本片段）。

        约定：仅产出非空字符串片段；拼接顺序由调用方决定。传输层（SSE）不在此协议内。

        Args:
            messages: OpenAI 兼容 chat messages 列表。
            temperature: 同 `chat()`；`None` 表示使用 `Settings` 默认。

        Raises:
            与 `chat()` 类似；另可能在解析 SSE 行时抛出 `RuntimeError`（上游 error 字段等）。
        """
        ...
