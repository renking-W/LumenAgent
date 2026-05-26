# HTTP 连接池重构方案

## 一、现状与问题

### 当前架构

```
lumen_agent/
├── infrastructure/
│   ├── deepseek_client.py     → _http_client (模块级 httpx.AsyncClient 单例)
│   └── embedding_client.py    → _embedding_client (模块级 httpx.AsyncClient 单例)
└── agent/tools/
    └── web_fetch.py           → _web_client (模块级 httpx.AsyncClient 单例)
```

三个模块各自维护一个模块级 `httpx.AsyncClient` 单例，每个都有一套独立的 `_get_client()` + `close_xxx()` 模式。

### 核心 bug

DeepSeek 流式对话 (`chat_stream`) 中，`_producer` task 的 `response.aclose()` 调用链路经过 `httpcore → anyio`，anyio 的 cancel scope 绑定创建它的 task。当 task 被取消或 generator 跨 task 清理时，anyio 检测到 `host_task` 不匹配，抛出：

```
RuntimeError: Attempted to exit cancel scope in a different task than it was entered in
```

根本原因：**httpx 的 `AsyncClient` 使用 httpcore 连接池，httpcore 内部用 anyio 管理连接生命周期，anyio 的 cancel scope 与 task 绑定，跨 task 操作会触发保护性报错。**

---

## 二、重构目标

1. **统一连接池** — 整个应用只有一个 `HttpPool` 单例，替代三个独立的模块级 client
2. **操作自包含** — `init` / `connect` / `send` / `receive` / `close` 每个方法可独立运行，不依赖外部进程状态
3. **可靠关闭** — 即使进程异常终止，连接也能被正确回收（OS 级 TCP 关闭 + Python 级 cleanup）
4. **流式安全** — 流式响应的生命周期不跨 task，避免 anyio cancel scope 冲突

---

## 三、架构设计

### 总览

```
┌─────────────────────────────────────────────────────────────┐
│                      HttpPool (singleton)                    │
│                                                             │
│  ┌──────────────────────┐    ┌──────────────────────────┐   │
│  │  shared_client        │    │  pool_config              │   │
│  │  (httpx.AsyncClient)  │    │  (timeout, limits, ...)   │   │
│  └────────┬─────────────┘    └──────────────────────────┘   │
│           │                                                  │
│           ▼                                                  │
│  ┌──────────────────────────────────────────────────┐       │
│  │  Operations                                      │       │
│  │                                                  │       │
│  │  init()         → 初始化连接池                    │       │
│  │  send()         → 非流式请求（复用 shared_client） │       │
│  │  send_stream()  → 流式请求（返回 StreamHandle）    │       │
│  │  close_all()    → 关闭所有连接                    │       │
│  └──────────────────────────────────────────────────┘       │
│                                                             │
│  ┌──────────────────────────────────────────────────┐       │
│  │  Active Streams                                  │       │
│  │                                                  │       │
│  │  StreamHandle #1  ──→ 独立 httpx.AsyncClient      │       │
│  │  StreamHandle #2  ──→ 独立 httpx.AsyncClient      │       │
│  │  ...                                             │       │
│  └──────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### 核心思路

| 请求类型 | 使用方式 | 关闭方式 |
|---------|---------|---------|
| 非流式 (chat, embedding, web_fetch) | 复用 `shared_client` | `shared_client` 统一关闭 |
| 流式 (chat_stream) | 每个流独立 `httpx.AsyncClient` | 流结束时关闭独立 client |

**为什么流式要用独立 client？**

因为 httpx 在 `client.stream("POST", ...)` 或 `client.send(request, stream=True)` 后，`response.aclose()` 要经过 httpcore 连接池 → anyio。如果共享连接池，跨 task 关闭会触发 anyio 报错。

**每个流独享一个 client 能保证：**
- `connect()` 创建 client → `send_stream()` → `receive()` → `close()` 全在同一个 task 内完成
- 关闭时直接 `client.aclose()`，httpcore 连接池随 client 一起销毁，不会影响其他流
- 即使 task 异常终止，`StreamHandle.close()` 从外部调用也能正常关闭（因为 client 的连接池自包含）

---

## 四、接口设计

### 类: `HttpPool`

```python
class HttpPool:
    """应用全局 HTTP 连接池。单例使用。"""

    # ── 初始化 ──
    def init(self, settings: Settings) -> None
        """延迟初始化共享 client。幂等。"""

    # ── 非流式 ──
    async def send(
        self,
        method: str,
        url: str,
        *,
        headers: dict | None = None,
        json: dict | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> httpx.Response
        """通用请求。复用 shared_client。返回完整的响应。"""

    # ── 流式 ──
    def send_stream(
        self,
        method: str,
        url: str,
        *,
        headers: dict | None = None,
        json: dict | None = None,
    ) -> StreamHandle
        """流式请求。创建独立 client，返回 StreamHandle。"""

    # ── 生命周期 ──
    async def close_all(self) -> None
        """关闭共享 client + 所有活跃的流式 client。幂等。"""
```

### 类: `StreamHandle`

```python
class StreamHandle:
    """一次流式连接的生命周期句柄。可独立关闭。"""

    async def connect(self) -> None
        """发起请求，获取响应。必须最先调用一次。"""

    async def receive(self) -> tuple[str, str | dict] | None
        """读取下一个 SSE event。返回 (kind, data) 或 None（流结束）。"""

    async def close(self) -> None
        """关闭连接、销毁独立 client。可反复调用，幂等。"""
```

### 文件结构

```
lumen_agent/
└── infrastructure/
    └── http_pool.py            # ← 新建：HttpPool + StreamHandle
    ├── deepseek_client.py      # ← 改造：使用 HttpPool 而非自有 client
    ├── embedding_client.py     # ← 改造：使用 HttpPool 而非自有 client
    └── ...
```

删除的文件：
- `agent/tools/web_fetch.py` 中的 `_get_web_client()` / `close_web_client()` → 改用 `HttpPool.send()`
- `deepseek_client.py` 中的 `_get_client()` / `close_http_client()` → 改用 `HttpPool`
- `embedding_client.py` 中的 `_get_client()` / `close_embedding_client()` → 改用 `HttpPool`
- `app.py` 的 `lifespan` 中的三个 close 调用 → 改为 `HttpPool.close_all()`

---

## 五、StreamHandle 内部设计（关键）

### 状态机

```
[CREATED] → [CONNECTING] → [STREAMING] → [CLOSED]
                ↓               ↓
           [ERROR]          [ERROR]
```

### 自包含的关闭

`StreamHandle.close()` 的完整流程：

```
1. 检查 state，已 CLOSED → return
2. 标记 state = CLOSED
3. 尝试关闭 response（若存在）：
   a. try: await response.aclose()
   b. except Exception: pass    ← 捕获所有异常，包括 anyio 冲突
4. 尝试关闭独立 client（若存在）：
   a. try: await client.aclose()
   b. except Exception: pass
5. 清理引用：response = None, client = None
```

**关键保障**：每个 `StreamHandle` 拥有自己独立的 `httpx.AsyncClient`，`close()` 时关闭的是整个 client，而非仅 response。client 关闭时会连带销毁其内部的 httpcore 连接池，不留任何残留连接。

### 代码骨架

```python
class StreamHandle:
    def __init__(self, method: str, url: str, headers: dict, json: dict):
        self._method = method
        self._url = url
        self._headers = headers
        self._json = json
        self._client: httpx.AsyncClient | None = None
        self._response: httpx.Response | None = None
        self._state = "CREATED"

    async def connect(self) -> None:
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
        self._state = "CONNECTING"
        request = self._client.build_request(self._method, self._url, headers=self._headers, json=self._json)
        self._response = await self._client.send(request, stream=True)
        self._state = "STREAMING"

    async def receive(self):
        async for line in self._response.aiter_lines():
            ...  # SSE 解析，yield (kind, data)
        self._state = "CLOSED"

    async def close(self):
        if self._state == "CLOSED":
            return
        self._state = "CLOSED"
        # 关闭 response（忽略错误）
        if self._response is not None:
            try:
                await self._response.aclose()
            except Exception:
                pass
        # 关闭独立 client（彻底销毁连接池）
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:
                pass
        self._response = None
        self._client = None
```

---

## 六、重构步骤

### Step 1: 新建 `http_pool.py`

- 实现 `HttpPool` 单例类（线程安全 + asyncio safe）
- 实现 `StreamHandle` 类
- 提供 `get_http_pool()` 工厂函数

### Step 2: 改造 `deepseek_client.py`

- 删除模块级 `_http_client` / `_get_client()` / `close_http_client()`
- `DeepSeekHttpClient.chat()` → 改用 `HttpPool.send()`
- `DeepSeekHttpClient.chat_stream()` → 改用 `StreamHandle`（细节见下节）

### Step 3: 改造 `embedding_client.py`

- 删除模块级 `_embedding_client` / `_get_client()` / `close_embedding_client()`
- `AlibabaEmbeddingClient._post()` → 改用 `HttpPool.send()`

### Step 4: 改造 `web_fetch.py`

- 删除模块级 `_web_client` / `_get_web_client()` / `close_web_client()`
- `WebFetch.execute()` → 改用 `HttpPool.send()`

### Step 5: 改造 `app.py`

- `lifespan` 中删除三个独立的 `close_*()` 调用
- 改为 `HttpPool.close_all()`

---

## 七、chat_stream 重写方案（关键变动）

使用 `StreamHandle` 后，`chat_stream` 不再需要 `asyncio.Queue` + `asyncio.create_task`，直接使用 generator 即可：

```python
async def chat_stream(self, messages, ...) -> AsyncIterator[tuple[str, Any]]:
    handle = pool.send_stream("POST", url, headers=headers, json=payload)
    try:
        await handle.connect()
        async for kind, data in handle.receive():
            yield (kind, data)
    finally:
        # 即使 generator 被 GeneratorExit 中断，
        # StreamHandle.close() 也会正确关闭独立的 client
        await handle.close()
```

**为什么这样不再报错：**

| 场景 | 原代码问题 | 新方案 |
|------|-----------|--------|
| 正常流结束 | task.cancel + anyio cancel scope 冲突 | 直接 yield 完毕，finally 关闭独立 client |
| 客户端断连 | GeneratorExit 传播 → task.cancel → anyio 报错 | GeneratorExit → finally → close() 关闭独立 client |
| 事件循环关闭 | 残留连接被 GC → anyio 报错 | 独立 client 在 close() 时完全销毁 |

**结论**：`StreamHandle` 有自己的 `httpx.AsyncClient`，与 `HttpPool.shared_client` 无关。
`close()` 关闭的是整个 client，httpcore 连接池随 client 一起销毁，不涉及跨 task 操作。

---

## 八、与当前代码的对比

| 维度 | 当前代码 | 新方案 |
|------|---------|--------|
| 连接池数量 | 3 个独立模块级 client | 1 个 `HttpPool` 单例管理 |
| 流式连接生命周期 | Queue + task + cancel（跨 task） | StreamHandle（单 task） |
| 关闭方式 | lifespan 依次 close 三个 client | `HttpPool.close_all()` |
| 操作独立性 | `_get_client()` 依赖模块全局变量 | `init/send/close` 通过实例调用 |
| 进程终止安全 | 依赖 Python event loop 正常关闭 | 每个 StreamHandle 可独立关闭 |
