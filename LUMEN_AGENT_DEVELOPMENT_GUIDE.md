# Lumen（流明）Agent 开发与上线指南

**工程名**：Python 包 / 仓库根目录建议 **`lumen_agent`**（下划线便于 `import lumen_agent`）；Git 远程仓库可用 **`lumen-agent`**（连字符常见于 GitHub）。

面向：在 cowAgent 思路上做一个**只保留 HTTP API（对接你自研的前端）、只接 DeepSeek**，但**记忆、知识库等核心能力齐全**的**精简专注、可上线**的 Agent 后端（麻雀虽小，五脏俱全）。**前端可单独仓库开发**，后端只暴露 REST / SSE（或 WebSocket）与稳定 JSON 契约。

---

## 0. 总览原则

- **先竖切，再横向加功能**：第一刀先做一条 **「HTTP → Agent → DeepSeek → HTTP」** 的最小回路，再往里塞工具、记忆、知识库。
- **始终保持「能跑」**：每个阶段结束都能跑出可演示的东西，不要憋一个大爆炸。
- **模仿 cowAgent 的分层 + 适配思路**：哪怕只支持 DeepSeek，也把 **LLM 客户端 / 存储 / 检索** 等实现放在「适配层」背后，用 **端口（Protocol）** 描述依赖，将来要换模型或换库只换实现类。
- **协议**：DeepSeek 使用 **OpenAI Chat Completions 兼容** 格式（`/v1/chat/completions`），工具为 **`tool_calls`**（非 Claude 的 `tool_use`），因此不必实现 cowAgent 里那套 Claude 消息消毒器，复杂度会小很多。
- **前后端契约**：用 **Pydantic + OpenAPI** 固定请求/响应与 SSE 事件 JSON 形状；独立前端可用同一 OpenAPI 生成 TypeScript 类型或 Orval 客户端。
- **后端可「面向接口」**：见下文 **§0.1**，用 `typing.Protocol` / `abc.ABC` + FastAPI `Depends` 做依赖注入，路由与用例不直接依赖具体存储或 HTTP 客户端。

### 0.1 后端「面向接口」怎么做（类比 Java，Python 写法）

Python 没有 `interface` 关键字，但可以做到 **依赖抽象、便于单测与替换实现**：

| 手段 | 用途 |
|------|------|
| **`typing.Protocol`** | 结构子类型：类只要实现了约定方法即「符合接口」，不必写 `implements`。适合 `LLMClient`、`ConversationRepository`、`VectorMemoryPort`、`KnowledgeSearchPort`。 |
| **`abc.ABC` + `@abstractmethod`** | 显式抽象基类：子类必须实现抽象方法，更接近「抽象类」。 |
| **FastAPI `Depends()`** | 在路由或 `Service` 构造里注入 `Protocol` 的具体实现，类似 Spring 按接口注入 Bean；换 SQLite → Postgres 只改 `get_conversation_repo()`。 |
| **Pydantic 模型 + OpenAPI** | **前后端分离时的「对外接口」**往往是 HTTP + JSON Schema；用 Pydantic 定义 DTO，文档即契约，前端可 codegen。 |

**推荐分层（六边形 / 整洁架构思路）**：

1. **`api/`**：路由只做鉴权、解析 body、返回 DTO；不写业务分支。  
2. **`application/`**（或 `services/`）：`ChatApplicationService` 编排「加载会话 → 调 Agent → 持久化」。  
3. **`domain/ports.py`**（或分散在各包）：`Protocol` 定义端口。  
4. **`infrastructure/`**：`DeepSeekHttpClient`、`SqliteConversationStore`、`LocalEmbedding` 等实现端口。

**CORS**：独立前端开发时，在 FastAPI 中对前端 origin 开启 `CORSMiddleware`；生产环境收紧 `allow_origins`。

---

## 推荐项目骨架

```
lumen_agent/                         # 后端仓库根目录（或 Git 名 lumen-agent）
├─ app.py                            # FastAPI 应用工厂 + 挂载路由 + CORS
├─ config.py                         # pydantic-settings：KEY、BASE_URL、模型名
├─ api/                              # HTTP 边界（对外「接口」= OpenAPI）
│   ├─ dependency.py                 # Depends：注入 LLMClient、Repos、AgentService
│   ├─ routers/
│   │   ├─ chat.py                   # POST /v1/chat、POST /v1/chat/stream (SSE)
│   │   ├─ sessions.py               # 会话 CRUD（若需要）
│   │   └─ knowledge.py              # 上传/删除文档、触发 ingest
│   └─ schemas/                      # Pydantic：ChatRequest、stream_events（SSE 事件）…
├─ application/                      # 用例编排（依赖 ports，不依赖具体 HTTP/SQL）
│   ├─ chat_service.py
│   └─ llm_error_policy.py           # LLM 链异常 → detail（POST /chat 与 SSE 共用）
├─ domain/                           # 可选：纯领域类型 + ports（Protocol）
│   └─ ports.py                      # LLMClientPort, ConversationRepository, …
├─ infrastructure/                   # 适配器实现
│   ├─ deepseek_client.py            # 实现 LLMClientPort（同步/流式）
│   ├─ sqlite_conversation.py        # 实现 ConversationRepository
│   └─ embedding_openai_compat.py    # 或其它 Embedding 后端
├─ agent/                            # 核心循环（可视为 domain 内聚模块）
│   ├─ agent.py                      # 多轮 + tool 循环（只依赖 ports）
│   ├─ prompt.py
│   ├─ tools/
│   │   ├─ base.py
│   │   ├─ read.py / write.py / bash.py / web_fetch.py
│   │   └─ kb_search.py / memory_search.py
│   ├─ memory/
│   │   ├─ conversation_store.py     # 也可挪到 infrastructure 并实现 port
│   │   ├─ vector_store.py
│   │   └─ summarizer.py
│   └─ knowledge/
│       ├─ ingest.py
│       └─ search.py
├─ data/                             # 本地数据目录（.gitignore）
│   ├─ conversations.db
│   ├─ memory.db
│   └─ kb.db
└─ requirements.txt
```

**说明**：若坚持极简单包结构，也可把 `api/`、`application/`、`infrastructure/` 合并为扁平目录，但 **仍建议** 保留 `dependency.py` + `Protocol`，避免路由文件里直接 `new SqliteStore()`。

依赖建议（先少后多）：`fastapi`、`uvicorn`、`httpx` 或 `requests`、`pydantic`、`pydantic-settings`；`sqlite3`（内置）；向量可用 `numpy` 自算余弦，或 `chroma` / `lancedb`；Embedding 若不用云端，可用 `sentence-transformers`（BGE/m3e 等）。类型检查可选：`mypy` 或 IDE 内置 Pyright。

---

## 阶段 1（约半天）—— 最小可跑回路（无流式、无工具）

**目标**：前端（任意技术栈）`POST` 一句话 → 后端调 DeepSeek → 返回 JSON 整段回复。

**步骤**：

1. `config.py`：读取 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`（如 `https://api.deepseek.com`）、模型名 `deepseek-chat`（建议 `pydantic-settings`）。
2. `infrastructure/deepseek_client.py`（实现 `LLMClientPort`）：`chat(messages, tools=None, stream=False)`，POST `/v1/chat/completions`，解析返回 `dict`。
3. `agent/agent.py` 或 `application/chat_service.py`：`reply(session_id, query)`：构造 messages → 通过注入的 `LLMClientPort` 调用 → 取 `choices[0].message.content`。
4. `api/routers/chat.py`：`POST /v1/chat`，body 用 Pydantic（如 `message: str`, `session_id: str | None`），返回 `{"content": str}`；挂载 `CORSMiddleware` 指向本地前端 dev server。
5. **前端仓库**：`fetch(baseURL + '/v1/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({...}) })`。

**验收**：前端或 curl 调 `POST /v1/chat` → 响应体里得到 DeepSeek 中文回复；浏览器打开 Swagger `/docs` 可手测。

---

## 阶段 2（约半天）—— 流式输出 + SSE

**目标**：前端用 **SSE（或 WebSocket）** 逐 token / 逐事件更新 UI。

**步骤**：

1. `deepseek_client.chat_stream(...)`：`httpx` POST `stream: true`，解析上游 SSE `data:` 行，`yield` 每个 `delta.content`（后续再接 `tool_calls` delta）。
2. `application/chat_service.reply_single_turn_stream` + `api/schemas/stream_events.py`：统一事件形如 `{"type":"message_update","data":{"delta":...}}`；`application/llm_error_policy.py` 与 `POST /v1/chat` 共享 502 `detail` / SSE `error.data.message` 文案。
3. `POST /v1/chat/stream`：`StreamingResponse(media_type="text/event-stream")`，每行 `data: {json}\n\n`，结束 `data: [DONE]`；响应头含 `Cache-Control: no-cache`、`X-Accel-Buffering: no`（nginx 反代时减轻缓冲）。
4. **前端仓库**：`fetch` + `ReadableStream`（或兼容封装）解析 SSE；**事件类型**与 `stream_events` 对齐，便于 codegen。

**验收**：前端控制台或页面看到流式增量；断线重连策略可放到阶段 8。

---

## 阶段 3（约 1–2 天）—— 工具调用循环

**目标**：模型可多次调用工具，直到不再返回 `tool_calls`。

**步骤**：

1. `agent/tools/base.py`：`BaseTool`：`name`、`description`、`params`（JSON Schema）、`execute(args) -> {status, result}`。
2. 先实现少量工具：`read`（读工作区内文件）、`web_fetch`（HTTP 拉正文，限大小与超时）；后续再加 `bash`、`write` 等。
3. `Agent.run_stream` 主循环（思路对齐 `AgentStreamExecutor`）：
   - 请求携带 `tools`（OpenAI 风格 `function`）；
   - 若响应含 `tool_calls`，逐个执行，将结果以 **`role: "tool"`** + `tool_call_id` 写回 `messages`；
   - 再次请求模型，直到无 `tool_calls` 或达到 `max_steps`。
4. 事件：`tool_execution_start` / `tool_execution_end`，前端可折叠卡片展示。

**验收**：「读某文件并总结」→ 出现工具卡片 → 得到总结。

**注意**：流式下 `tool_calls` 常按 **`index`** 分块到达，需用 buffer 拼接 `name` 与 `arguments` JSON 字符串（可参考 cowAgent `agent_stream.py` 中 `tool_calls_buffer` 逻辑）。

---

## 阶段 4（约 1 天）—— 短期会话持久化

**目标**：刷新页面或重启服务后，同一会话历史仍在。

**步骤**：

1. `memory/conversation_store.py`：SQLite 表：`sessions`、`messages`（及可选 `tool_calls` 元数据）。
2. 每次运行前按 `session_id` 加载；运行后追加新消息。
3. 简单裁剪：超过条数或估算 token 时，按「最近 K 轮」删除（可先实现「保留最后 N 条消息」再升级为按轮，参考 cowAgent `_identify_complete_turns` 思想）。
4. **前端**：请求头或 body 带 `session_id`；侧边会话列表由前端状态 + 后端 `GET /v1/sessions`（可选）配合。

**验收**：换 `session_id` 隔离；刷新前端后同一 `session_id` 仍能拉历史（若你实现了 `GET /v1/sessions/{id}/messages`）。

---

## 阶段 5（约 1–2 天）—— 长期记忆（向量检索）

**目标**：旧对话被摘要/切块入库后，新会话仍能检索到重要事实。

**步骤**：

1. **Embedding**：DeepSeek 当前不提供 embedding，可选：
   - 单独 OpenAI 兼容 embedding（如 `text-embedding-3-small`），或
   - 本地 `sentence-transformers`（BGE、m3e 等）。
2. `memory/vector_store.py`：小数据可用 SQLite 存向量 + Python 算余弦；规模大再换专用向量库。
3. `memory/summarizer.py`：上下文超长或按策略触发 `flush`，用 DeepSeek 把丢弃轮次摘要成条目，逐条 embed 写入。
4. `tools/memory_search.py`：模型主动检索；可选在每次用户提问后先做 top-k 拼进 system 或单独一轮检索消息。

**验收**：先声明偏好/身份 → 新开 session → 仍能答对检索类问题。

---

## 阶段 6（约 2–3 天）—— 知识库 / RAG

**目标**：上传文档后，回答可引用片段。

**步骤**：

1. `knowledge/ingest.py`：解析 PDF/Markdown/HTML → 切片（长度 + 重叠）→ embed → 表 `kb_chunks`。
2. `knowledge/search.py`：`search(query, top_k)`。
3. `tools/kb_search.py`：注册为工具；在 system prompt 中说明「需要查资料时先调用」。
4. **知识库管理 API**：`POST /v1/knowledge/documents`（multipart 上传）、`GET/DELETE` 列表与删除；ingest 可同步或后台任务（`BackgroundTasks` / 队列）。
5. 回答中要求模型标注来源（`doc_id`、标题、页码等 meta）；前端用返回的 meta 做引用链接。

**验收**：上传手册后，问专业问题能引用正确段落。

---

## 阶段 7（约 1 天）—— Prompt 模块化 + 上下文管理

**目标**：system prompt 可维护、可扩展；长对话不爆上下文。

**步骤**：

1. `agent/prompt.py`：模块化拼接（人格、时间、工具说明、记忆/知识库使用规范、工作目录约定），风格可参考 `agent/prompt/builder.py`。
2. Token 估算（中英文混合粗估即可）+ 按轮或按条裁剪 + 一次 aggressive 截断 + 必要时清空并提示用户（对齐 cowAgent 溢出处理思路，但实现可简化）。

**验收**：长对话 + 多轮工具仍稳定。

---

## 阶段 8（持续）—— 前端体验与工程化

**后端侧**

- OpenAPI 导出与版本号（`/openapi.json`）；重大变更走 `/v2` 或 `Accept-Version`。
- API 429 / 网络错误：对 DeepSeek 客户端做退避重试；超时与 `idempotency-key`（可选）文档化。
- 结构化日志（request_id、`session_id`）；健康检查 `GET /health`。
- 配置：环境变量 + `.env`，`pydantic-settings` 校验缺失项启动失败。
- 测试：`httpx` mock 或 VCR 录制流式响应；对 `application` 层做单元测试（注入 fake ports）。

**前端侧（独立仓库）**

- Markdown 流式渲染、代码高亮；工具卡片折叠与耗时展示（与 SSE `tool_execution_*` 事件对齐）。
- 从后端 `openapi.json` 生成 API 客户端与类型（Orval、openapi-typescript 等）。
- 鉴权：若上生产，`Authorization: Bearer` + 后端校验；开发期可关闭。

---

## 时间预算参考

| 阶段 | 个人集中工时（量级） | 关键产出 |
|------|----------------------|----------|
| 1 | 约半天 | 单轮 chat 跑通 |
| 2 | 约半天 | SSE 流式 |
| 3 | 1–2 天 | 工具循环 |
| 4 | 约 1 天 | 会话持久化 |
| 5 | 1–2 天 | 长期记忆 |
| 6 | 2–3 天 | 知识库 RAG |
| 7 | 约 1 天 | Prompt + 裁剪 |
| 8 | 持续 | 体验与工程化 |

合计约 **5–10 个工作日** 可到「五脏俱全」的 demo 量级。

---

## 入手第一步（建议今天就做）

1. 新建仓库与上述目录骨架（可先只建 `api/`、`infrastructure/`、`app.py` 三处最小集合）。
2. 实现 `config.py` + `infrastructure/deepseek_client.py`（**同步** `chat`，实现 `LLMClientPort`）。
3. 命令行或 `pytest` 测通：打印 `choices[0].message.content`。
4. 再起 FastAPI：`POST /v1/chat` 用 curl / Swagger 调通；前端仓库连本地 `VITE_API_BASE=http://127.0.0.1:8000`。

**先保证最小回路可运行**，再进入阶段 2。

---

## 踩坑提示

1. **Embedding 需单独方案**：DeepSeek 对话 API 与 embedding 分离选型。
2. **流式 `tool_calls`**：按 `index` 累积 `id` / `name` / `arguments` 片段，再 `json.loads(arguments)`。
3. **SSE 被反向代理缓冲**：设置 `Cache-Control: no-cache`、`X-Accel-Buffering: no`，或改用 WebSocket。
4. **一开始就引入 `session_id`**：结构为 `session_id -> Agent 状态`（对齐 cowAgent `AgentBridge` 按会话管理 Agent）。
5. **耗时工具勿阻塞 SSE 线程**：用线程池/异步，并先发 `tool_execution_start`。
6. **安全**：`bash`/`read`/`write` 限制在工作目录；`web_fetch` 限制超时与响应体大小。
7. **独立前端 + CORS**：浏览器跨域请求会先发 `OPTIONS`；确保 FastAPI `CORSMiddleware` 包含前端的 `origin`，且对 `POST`/`GET`（含 SSE）放行所需 `headers`（如 `Authorization`、`Content-Type`）。生产环境勿使用 `allow_origins=["*"]` 搭配 `allow_credentials=True`。
8. **品牌与仓库**：对外展示用 **Lumen / 流明**；代码与 PyPI 若发布子包，注意与已有 `lumen` 相关包名冲突，可先查 [pypi.org](https://pypi.org) 再定最终包名。

---

## 与 cowAgent 的对应关系（便于对照源码）

| Lumen 项目概念 | cowAgent 参考位置 |
|-----------------|-------------------|
| HTTP API + SSE（或独立前端） | 参考 `channel/web/web_channel.py` 的队列/SSE 模式；前端逻辑对应 `channel/web/static/js/console.js`（可只借鉴事件协议） |
| Bridge 入口 | `bridge/bridge.py`、`bridge/agent_bridge.py` |
| 流式 + 工具循环 | `agent/protocol/agent_stream.py` |
| 事件回调 | `_emit_event`、`on_event`、`AgentEventHandler` |
| OpenAI 兼容工具 | `models/openai_compatible_bot.py` |
| 会话 SQLite | `agent/memory/conversation_store.py` |
| 长期记忆 | `agent/memory/manager.py`、`storage.py`、`summarizer.py` |
| 知识库（若走服务形态） | `agent/knowledge/service.py` |
| Prompt 拼装 | `agent/prompt/builder.py` |

---

*本文档原名 `MINI_AGENT_DEVELOPMENT_GUIDE.md`，已更名为 **Lumen** 并更新为 `LUMEN_AGENT_DEVELOPMENT_GUIDE.md`；内容含「独立前端 + 后端面向接口/契约」与产品命名说明。*
