# 流明 Agent (LumenAgent)

> 一个基于大模型的多轮对话 Agent 系统 — 搭载**远程虚拟机操控**、**MCP 协议扩展**、**AI 自动定时任务**、**可插拔技能**、**RAG 知识库**、**双模记忆系统**、**工具审批流**等完整的企业级功能模块。

![Tech Stack](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=fff)
![Framework](https://img.shields.io/badge/FastAPI-0.136+-009688?logo=fastapi&logoColor=fff)
![Frontend](https://img.shields.io/badge/Vue_3-4FC08D?logo=vue.js&logoColor=fff)
![LLM](https://img.shields.io/badge/DeepSeek-4F5B66?logo=data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjQiIGhlaWdodD0iNjQiIHZpZXdCb3g9IjAgMCA2NCA2NCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48Y2lyY2xlIGN4PSIzMiIgY3k9IjMyIiByPSIzMiIgZmlsbD0iIzRGNUI2NiIvPjwvc3ZnPg==)

---


## ✨ 亮点功能

| 维度 | LumenAgent |
|------|-----------|
| **远程 VM 操控** | Agent **直接通过 SSH 操控远程虚拟机**，执行命令、查看状态，支持 WebSocket 实时回显 |
| **工具审批流** | 三档审批模式（无/全部/按危险度）+ **前端弹窗实时审批**，超时自动拒绝 |
| **MCP 协议支持** | 支持加载**外部 MCP Server** 作为扩展工具池，前端可选择性启用 |
| **AI 定时任务** | Agent **在对话中即可创建/管理定时任务**（cron/interval/date），任务触发时自动执行工具循环 |
| **双模记忆** | **每日记忆**（自动摘要）+ **长期记忆**（自动压缩）+ 双重向量检索（ChromaDB + 语义搜索） |
| **滑动窗口摘要** | 动态压缩策略：N 轮触发一次，压缩前 M 轮为摘要，保留后 K 轮原文 |
| **热更新配置** | Agent 可通过 `env_editor` 工具**运行时修改自身配置**，无需重启服务 |
| **双入口 + API Key** | 同时运行 CLI 和 Web UI，**API Key 认证**保护所有端点 |
| **管理前端** | **13 个视图组件**覆盖工具/技能/记忆/知识库/虚拟机/定时任务/MCP/系统配置/日志/API Key 全管理场景 |

---

## 📋 功能总览

| 模块 | 功能 | 说明 |
|------|------|------|
| **💬 对话** | 流式聊天 | SSE 实时推送，支持思考链、工具调用、正文的端到端流式渲染 |
| **🤖 Agent 模式** | 多轮工具循环 | LLM 自动推理 → 调用工具 → 观察结果 → 继续推理，支持最多 20 轮 |
| **🛠 工具系统** | 11 个内置工具 | Read / Write / Bash / WebSearch / WebFetch / KnowledgeSearch / KnowledgeInsert / MemorySearch / EnvEditor / TaskScheduler / VirtualMachineOperation |
| **🖥 远程虚拟机** | SSH 操控 | Agent 直接连接远程服务器执行命令、查看状态，带 WebSocket 实时回显 |
| **👮 工具审批流** | 三档审批 | 无审批 / 全量审批 / 按危险度审批，前端弹窗实时决策 |
| **🔌 MCP 协议** | 外部工具扩展 | 加载任意 MCP Server 的工具，前端可选择性启用 |
| **⏰ AI 定时任务** | 自动调度 | Agent 对话中创建 cron/interval/date 定时任务，触发时自动执行工具循环 |
| **🧠 知识库** | RAG 向量检索 | 文本切分 → Embedding → ChromaDB 检索，支持入库、删除、重建 |
| **💾 记忆系统** | 自动摘要 + 向量检索 | 每日对话自动摘要落盘，长期记忆自动整理，双重向量语义检索 |
| **📜 会话管理** | 滑动窗口摘要 | SQLite 持久化，游标分页，自动标题生成 |
| **🔌 技能系统** | 可插拔扩展 | SKILL.md 驱动，环境依赖校验，兼容 clawhub 生态 |
| **⚙️ 配置管理** | 热更新 | Agent 调用 `env_editor` 工具随时读/写配置，无需重启服务 |
| **🔑 API 安全** | API Key 认证 | 完整的 Key 创建/列表/启用/禁用管理，首次启动自动生成默认 Key |
| **🌐 双入口** | Web UI + CLI | Vue 3 管理控制台；CLI 命令行模式，支持斜杠命令 |

---

## 🗂 项目结构

```
LumenAgent/
├── lumen_agent/                              # 后端 Python 包（~7000 行）
│   ├── agent/                                # Agent 核心引擎
│   │   ├── agent.py                          # AgentStreamExecutor — 多轮工具循环引擎
│   │   ├── context.py                        # 上下文管理、防循环守卫
│   │   ├── memory/
│   │   │   └── memory_utils.py               # 记忆文件操作工具
│   │   ├── prompts/
│   │   │   ├── builder.py                    # System Prompt 构造器
│   │   │   └── docs/                         # Prompt 模板
│   │   ├── skills/
│   │   │   ├── loader.py                     # 技能加载器
│   │   │   └── meta.py                       # 技能元数据模型
│   │   ├── tokens/
│   │   │   ├── char_counter.py               # 字符计数
│   │   │   └── tiktoken_counter.py           # tiktoken 计数
│   │   └── tools/                            # 11 个工具实现
│   │       ├── base.py                       # BaseTool + ToolResult 基类
│   │       ├── registry.py                   # 工具注册表（装饰器驱动）
│   │       ├── read.py / write.py / bash.py  # 文件/命令操作
│   │       ├── web_search.py / web_fetch.py  # 网络工具
│   │       ├── knowledge.py                  # 知识库检索与入库
│   │       ├── memory_search.py              # 记忆向量检索
│   │       ├── env_editor.py                 # .env 配置编辑（热更新）
│   │       ├── task_scheduler.py             # ⌚ 定时任务创建与管理
│   │       ├── vm_operation.py               # 🖥 虚拟机 SSH 操作
│   │       └── mcp_bridge.py                 # 🔌 MCP 工具桥接
│   ├── api/                                  # FastAPI 路由层（28+ 端点）
│   │   ├── routers/
│   │   │   ├── chat.py                       # 对话：POST + SSE 流式 + 中断 + 审批
│   │   │   ├── sessions.py                   # 会话 CRUD + 游标分页
│   │   │   ├── vm.py                         # 🖥 虚拟机注册/更新/删除/列表/执行
│   │   │   ├── vm_ws.py                      # 🖥 WebSocket 实时回显
│   │   │   ├── scheduler_router.py           # ⏰ 定时任务 CRUD + 执行记录
│   │   │   ├── mcp_servers.py                # 🔌 MCP Server 配置管理
│   │   │   ├── api_keys.py                   # 🔑 API Key 管理
│   │   │   ├── knowledge.py                  # 📚 知识库管理
│   │   │   ├── configs.py / logs_router.py   # ⚙️ 配置 / 📋 日志
│   │   │   ├── tools.py / skills.py          # 🛠 工具/技能列表
│   │   │   └── memories.py                   # 🧠 记忆文件浏览
│   │   └── schemas/                          # Pydantic DTO + SSE 事件
│   ├── application/                          # 应用服务层（~2500 行）
│   │   ├── service/
│   │   │   ├── chat_service.py               # 对话编排（单轮/流式/Agent）
│   │   │   ├── vm_connection_service.py      # 🖥 SSH 连接池 + 流式命令执行
│   │   │   ├── scheduler_task_service.py     # ⏰ 定时任务服务
│   │   │   ├── mcp_server_service.py         # 🔌 MCP 服务
│   │   │   ├── summary_service.py            # 📝 滑动窗口摘要 + 长期记忆整理
│   │   │   ├── rag_service.py                # 📚 知识库 RAG 服务
│   │   │   ├── memory_rag_service.py         # 🧠 记忆向量检索服务
│   │   │   ├── config_service.py             # ⚙️ 配置管理服务
│   │   │   ├── api_key_service.py            # 🔑 API Key 服务
│   │   │   ├── memory_file_service.py        # 🧠 记忆文件浏览服务
│   │   │   ├── log_service.py                # 📋 日志服务
│   │   │   └── title_service.py              # 🏷 会话标题自动生成
│   │   └── utils/
│   │       ├── context_assembly.py           # 上下文组装 + Token 预算检查
│   │       ├── text_splitter.py              # 文本切分
│   │       └── llm_error_policy.py           # LLM 链路错误映射
│   ├── infrastructure/                       # 基础设施层
│   │   ├── startup/                          # 启动引导
│   │   │   ├── workspace.py                  # 工作区初始化
│   │   │   ├── uvicorn_runner.py             # uvicorn 启动
│   │   │   └── flask_proxy.py               # Flask 静态 + API 代理
│   │   ├── data_base/                        # SQLite 仓储
│   │   │   ├── sqlite_conversation.py        # 会话仓储
│   │   │   ├── sqlite_knowledge.py           # 知识库仓储
│   │   │   ├── sqlite_scheduler.py           # 定时任务仓储
│   │   │   ├── sqlite_mcp.py                 # MCP 配置仓储
│   │   │   ├── sqlite_api_key.py             # API Key 仓储
│   │   │   └── sqlite_vm_config.py           # VM 配置仓储
│   │   ├── client/
│   │   │   ├── deepseek_client.py            # DeepSeek HTTP 客户端
│   │   │   ├── embedding_client.py           # 阿里云 Embedding 客户端
│   │   │   ├── chroma_client.py              # Chroma 向量存储封装
│   │   │   └── mcp_client.py                 # MCP SSE 客户端管理器
│   │   ├── scheduler/
│   │   │   ├── scheduler_service.py          # APScheduler 封装（单例）
│   │   │   └── tasks.py                      # 预定义系统任务
│   │   ├── virtual_machine/
│   │   │   └── virtual_machine_registry.py   # VM 注册中心
│   │   ├── approval_registry.py              # 👮 工具审批注册表
│   │   ├── vm_event_bus.py                   # 🖥 VM 事件总线
│   │   ├── websocket_manager.py              # 🖥 WebSocket 连接管理器
│   │   ├── sse_registry.py                   # SSE 中断注册表
│   │   └── http_pool.py                      # 共享 HTTP 连接池
│   ├── model_adapters/                       # 模型适配层
│   │   ├── base.py                           # ModelAdapter 抽象接口
│   │   └── deepseek.py                       # DeepSeek 适配器实现
├── webChannel/                               # 前端 Vue 3 + TypeScript（~8800 行）
│   └── src/
│       ├── App.vue                           # 主布局（侧栏导航 + 顶栏 + 内容区 + 输入区）
│       ├── components/                       # 13 个视图组件
│       │   ├── ChatView.vue                  # 对话面板
│       │   ├── ChatMessage.vue               # 消息渲染（Markdown/思考链/工具/审批）
│       │   ├── SessionList.vue               # 会话列表
│       │   ├── VMView.vue (1366 行)          # 🖥 虚拟机管理 + 终端
│       │   ├── SchedulerView.vue             # ⏰ 定时任务管理
│       │   ├── MCPServerView.vue             # 🔌 MCP 配置
│       │   ├── KnowledgeView.vue             # 📚 知识库管理
│       │   ├── ConfigView.vue                # ⚙️ 系统配置编辑
│       │   ├── LogView.vue                   # 📋 日志实时监控
│       │   ├── MemoryView.vue / ToolView.vue / SkillView.vue / ApiKeyManager.vue
│       │   └── MiniChatPanel.vue             # 浮动聊天面板
│       ├── composables/
│       │   ├── useChatStream.ts              # SSE 流式消息管理
│       │   └── useVMWebSocket.ts             # 🖥 VM WebSocket 连接管理
│       ├── types.ts                          # TypeScript 类型定义
│       └── utils/markdown.ts                 # Markdown + 代码高亮渲染
├── work_space/                               # 工作空间
│   ├── memory/                               # 每日记忆文件 YYYY-MM-DD.md
│   ├── MEMORY.md                             # 长期记忆
│   ├── ME.md / USER.md / RULE.md             # 项目/用户/规则上下文
│   └── skills/                               # 可插拔技能包
├── pyproject.toml                            # Python 包配置
├── package.json / start.js / install.js       # Node.js 启动/安装脚本
└── lumen_agent/.env / config.json             # 环境变量 + 默认配置
```

---

## 🚀 快速启动

### 0️⃣ 一行命令启动（推荐）

确保已安装 [Node.js ≥ 18](https://nodejs.org/) 和 [Python ≥ 3.13](https://www.python.org/) 后：

```bash
# 一键安装 + 启动（自动装 Python/Node 依赖、构建前端、启动服务）
npx lumen-start
```

首次运行会自动完成：Python 依赖安装 → 前端依赖安装 → 前端构建 → 服务启动。

然后只需配置 `lumen_agent/.env` 中的 `LLM_API_KEY`，重启即可。

> **国内用户**：npm 和 pip 下载慢时可配置镜像加速：
> ```bash
> npm config set registry https://registry.npmmirror.com
> pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
> ```

---

### 1️⃣ 环境要求

- Python ≥ 3.13
- Node.js ≥ 18
- 一个 **DeepSeek API Key**（或其他兼容的 OpenAI API）
- 一个 **阿里云 DashScope API Key**（仅知识库 RAG + 记忆向量检索需要，纯对话可不配）

### 2️⃣ 配置环境变量

编辑 `lumen_agent/.env`：

```env
# ── LLM 配置 ──
LLM_API_KEY=sk-your-deepseek-api-key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash

# ── 阿里云 Embedding（可选，RAG/记忆需要）──
EMBEDDING_API_KEY=sk-your-dashscope-api-key
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings
EMBEDDING_MODEL=text-embedding-v4

# ── 服务端口 ──
HOST=127.0.0.1
PORT=21675
```

全部可配置项详见 `config.json`（同名 `.env` 变量覆盖）。

### 3️⃣ 全局安装后启动（或手动分步）

```bash
# 方式一：全局安装
npm install -g lumen-agent
lumen-start

# 方式二：克隆仓库手动分步
git clone https://github.com/renking-W/LumenAgent.git
cd LumenAgent
npm install     # 自动安装 Python + Node 依赖
npm start       # 构建前端 + 启动服务
```

### 4️⃣ 传统方式：纯 Python 启动后端

```bash
pip install -r lumen_agent/requirements.txt
python -m lumen_agent.app
```

后端默认运行在 `http://127.0.0.1:21675`。

> 首次启动会自动创建默认 API Key 并打印到日志，请妥善保管。

- Swagger 文档：`http://127.0.0.1:21675/docs`
- 健康检查：`http://127.0.0.1:21675/health`

### 4️⃣ 启动前端（开发模式）

```bash
cd webChannel
npm install
npm run dev
```

前端默认运行在 `http://127.0.0.1:5173`，已配置代理转发 API 请求到后端 `21675` 端口。

### 5️⃣ 构建生产版本

```bash
cd webChannel
npm run build
```

构建产物输出到 `webChannel/dist/`，后端启动时自动通过 Flask 提供静态文件服务，访问 `http://127.0.0.1:21675` 即可。

### 6️⃣ CLI 模式（可选）

```bash
# 自动同时启动 HTTP 服务
lumen-cli

# 或
python -m lumen_agent.application.common.chat_in_cli
```

CLI 支持斜杠命令：`/exit` `/new` `/knowledge`

---

## 🖥 管理控制台界面

### 导航面板

左侧栏包含 **10 个管理视图**，按功能分组：

**核心**

| 视图 | 说明 |
|------|------|
| 💬 对话 | 实时流式对话面板 |
| 🛠️ 工具 | 浏览 Agent 的全部可用工具及其参数 |
| 🎯 技能 | 展示可插拔技能的状态（可用/缺失环境） |
| 🧠 记忆 | 浏览每日记忆 + 长期记忆文件 |

**功能**

| 视图 | 说明 |
|------|------|
| 🔌 MCP | 管理 MCP Server 配置（CRUD + 测试连接） |
| 🖥 虚拟机 | 注册/管理远程虚拟机，实时终端回显 |
| 📚 知识库 | 知识文档入库、检索、Chunk 详情查看 |
| ⏰ 定时任务 | 查看 AI 创建的定时任务及执行记录 |

**其它**

| 视图 | 说明 |
|------|------|
| ⚙️ 系统配置 | 编辑系统运行参数 |
| 📋 日志 | 实时查看/下载日志文件 |

---

### 1️⃣ 对话视图

**会话列表**
- 所有历史会话按更新时间排序
- 相对时间显示（"3 分钟前"）
- 支持新建/切换/删除（带确认弹窗）
- 可折叠收起

**消息区域** — 每条助手消息按区块渲染：

| 区块 | 渲染方式 | 说明 |
|------|---------|------|
| 💭 思考链 | 可折叠 `<details>` | DeepSeek reasoning_content，默认收起 |
| 📝 正文 | GFM Markdown | 代码高亮 + 表格 + 链接 + 复制按钮 |
| 🛠 工具调用 | 可折叠 details | 工具名 + 参数 + 耗时 + 结果 |
| 👮 审批等待 | 弹窗按钮 | 批准/拒绝当前工具调用（按审批模式） |
| ⚠️ 错误 | 可折叠 details | 错误详情 + 「重试」按钮 |

**模式切换**
- **Simple 模式** — 单轮对话，LLM 直接回复
- **Agent 模式**（默认）— 多轮工具循环，LLM 可调用 11 个工具

**输入区**
- 多行文本框（自动调整高度 4–10 行）
- `Enter` 发送，`Ctrl+Enter` 换行
- 发送中可随时中断流式回复
- 支持选择 MCP Server 挂载到当前对话

---

### 2️⃣ 🖥 虚拟机管理视图

> **这是项目的核心特色功能之一**，提供完整的远程服务器管理体验。

- **注册 VM**：填写 IP、端口、用户名、密码
- **状态面板**：查看所有已注册 VM 的连接状态
- **内置终端**：通过 WebSocket 实时回显，支持命令执行、流式输出、退出码显示
- **一键操作**：连接/断开/删除，操作结果实时反馈
- **Agent 联动**：Agent 可在对话中自动连接 VM 执行任务，用户通过 Web 界面实时观察执行过程

---

### 3️⃣ ⏰ AI 定时任务视图

- 展示所有 AI 创建的定时任务
- 显示触发器类型（cron/interval/date）、表达式、下次执行时间
- 查看每次触发的执行记录 + 输出内容
- 支持暂停/恢复/删除

---

### 4️⃣ 🔌 MCP Server 管理

- 添加/编辑/删除 MCP Server 配置
- 测试连接并查看暴露的工具列表
- 对话时通过下拉选择框选择性挂载 MCP 工具

---

## 🧠 核心架构解读

### Agent 工具循环

```
用户输入
    │
    ▼
┌─────────────────────────────────┐
│  1. 上下文组装                   │
│     (摘要 + 历史 + 本轮消息       │
│      + Token 预算检查)           │
└──────────┬──────────────────────┘
           ▼
┌─────────────────────────────────┐
│  2. LLM 推理（流式 SSE）         │
│     输出: text + thinking        │
│     或发起: tool_use             │
└──────┬──────────────────────────┘
       │
       ├── 无工具调用 → yield "done" → 落库 + 摘要触发
       │
       └── 有工具调用
               │
               ▼
       ┌───────────────────┐
       │ 3. 审批检查        │
       │ (选: 无/全部/危险) │
       └──────┬────────────┘
              │ 通过
              ▼
       ┌───────────────────┐
       │ 4. 执行工具         │
       │ (逐个流式执行)      │
       └──────┬────────────┘
              │
              ▼
       ┌───────────────────┐
       │ 5. 结果返回 LLM    │
       │ → 回到步骤 2       │
       │ (最多 20 轮)       │
       └───────────────────┘
```

### 滑动窗口摘要

```
轮次:  1  2  3  4  5  6  │  7  8  9 ...
                        │
                        ▼
                    ┌───────────┐
                    │ 触发摘要   │
                    │ (阈值=6)   │
                    └───────────┘
                          │
                    压缩前 4 轮为摘要
                    保留后 2 轮为原文
                    count → 2
```

- `summary_threshold_turns=6`：每 6 轮触发一次摘要
- `summary_compress_turns=4`：前 4 轮压缩为摘要
- `summary_keep_turns=2`：后 2 轮保留原文
- 摘要结果同时写入每日记忆文件（YYYY-MM-DD.md）+ ChromaDB 向量库

### SSE 事件流

```
Agent 模式下完整的 SSE 事件序列：

event: reasoning_update    ← 思考链增量
event: message_update      ← 正文增量
event: tool_calls          ← 本轮工具调用列表
event: awaiting_approval   ← 等待用户审批（含工具 ID/名称/参数）
event: tool_execution_start← 单个工具开始执行
event: tool_execution_end  ← 单个工具执行完毕（含耗时）
event: reasoning_update    ← 工具结果返回后继续推理
event: message_update      ← 最终回复
event: assistant_done      ← 本轮完成
event: error               ← 错误（可选）
[DONE]                     ← 流结束标记
```

---

## 🛠 工具系统详解

### 11 个内置工具

| 工具名 | 用途 | 需审批 | 说明 |
|--------|------|--------|------|
| `read` | 读取文件 | 否 | offset/limit 分块，单次 2000 行 / 50KB |
| `write` | 写入/追加/替换 | 否 | 三种写入模式 |
| `bash` | 执行 Shell 命令 | 否 | 自动适配 Win/Unix，30s 超时 |
| `web_search` | 网页搜索 | 否 | DuckDuckGo，无需额外 API Key |
| `web_fetch` | 网页抓取 | 否 | HTML → Markdown，支持文件下载 |
| `knowledge_search` | RAG 知识检索 | 否 | 从 ChromaDB 检索相关 chunk |
| `knowledge_insert` | 知识入库 | 否 | 文本/文件入库到知识库 |
| `memory_search` | 记忆检索 | 否 | 语义检索历史对话记忆 |
| `env_editor` | 配置编辑 | 否 | 运行时读写 .env，热更新 |
| `task_scheduler` | 定时任务管理 | ✅ 是 | 创建/列表/删除/暂停/恢复定时任务 |
| `virtual_machine_operation` | 虚拟机操作 | ✅ 是 | SSH 执行命令/连接/断开/查看状态 |

### 工具审批系统

三种审批模式可在对话时动态切换：

| 模式 | 行为 | 适用场景 |
|------|------|---------|
| `none` | 不审批，直接执行 | 调试/可信环境 |
| `dangerous`（默认） | 仅审批标记 `requires_approval=True` 的工具 | 日常使用 |
| `all` | 全部工具调用都需审批 | 高安全要求 |

审批流程：
1. LLM 发起工具调用 → 进入审批挂起状态
2. 前端弹出审批对话框，展示工具名称 + 参数
3. 用户逐一点击批准/拒绝（或超时自动全部拒绝）
4. 拒绝的工具注入 `"用户已拒绝该工具调用"` 错误结果
5. Agent 根据结果继续推理

### MCP 工具扩展

支持加载任意 MCP Server 作为工具源：
- 前端管理面板配置 MCP Server URL + API Key
- 启动时自动连接所有 enabled 的 Server
- 对话时通过下拉选择框选择性挂载
- 挂载后 MCP Server 暴露的工具自动注入 Agent 工具池

---

## 🖥 虚拟机模块架构

```
┌────────────────────────────────────────────────────────┐
│  Agent (VirtualMachineOperation 工具)                   │
│  - exec_command / connect / disconnect / get_status    │
│  - list_vms                                            │
└──────────┬─────────────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────────────────────┐
│  VMConnectionService (SSH 连接池)                       │
│  - asyncssh 驱动，支持连接复用                           │
│  - 流式命令执行 (async for kind, data in ...)          │
└────┬──────────────┬──────────────────┬─────────────────┘
     │              │                  │
     ▼              ▼                  ▼
┌──────────┐ ┌──────────────┐ ┌──────────────────┐
│ SQLite   │ │ WebSocket    │ │ VMEventBus       │
│ VM 配置   │ │ 连接管理器    │ │ (事件发布/订阅)    │
│ 仓储     │ │ (前端实时)    │ │                   │
└──────────┘ └──────────────┘ └──────────────────┘

前端 VMView.vue：
- 注册/管理 VM 配置
- 通过 WebSocket 实时订阅命令执行输出
- 内置终端面板
- 与 Agent 对话中的 VM 操作联动
```

---

## ⏰ AI 定时任务系统

Agent 通过 `task_scheduler` 工具可在对话中直接创建定时任务：

```
用户: "每天早上9点帮我查一下AI的最新资讯"

Agent → 调用 task_scheduler (action=create, trigger_type=cron,
                            trigger_expr="0 9 * * *", ...)

系统：
  ┌─ 向用户确认任务步骤 + 产物格式
  ├─ 注册到 APScheduler
  ├─ 持久化到 scheduled_tasks 表
  └─ 返回任务 ID

到达触发时间：
  ┌─ 使用独立 session (__scheduled__{id})
  ├─ 执行一轮完整的 Agent 工具循环
  ├─ 结果落库到 scheduled_executions 表
  └─ 可被前端 SchedulerView 查看
```

支持三种触发器：cron（`0 9 * * *`）/ interval（`1800`秒）/ date（`ISO 时间`）

---

## 📝 记忆系统

### 双层结构

```
记忆系统
├── 📅 每日记忆 (work_space/memory/YYYY-MM-DD.md)
│   ├── 每次摘要触发时自动追加
│   ├── 按 "---" + "## timestamp session=xxx" 分段
│   └── 自动向量化 → ChromaDB (memory_store)
│
└── 📌 长期记忆 (work_space/memory/MEMORY.md)
    ├── 超过 150KB 时自动 LLM 压缩整理
    ├── 保持内容精炼
    └── 启动时全量索引 → ChromaDB
```

### 检索方式

- **Agent 语义检索**：`memory_search` 工具 → ChromaDB 向量搜索
- **前端浏览**：记忆面板查看全部文件内容 + 类型区分

---

## 📚 知识库 (RAG)

| 步骤 | 技术栈 | 说明 |
|------|--------|------|
| 文本切分 | 自定义 TextSplitter | 按 chunk_size=500, overlap=150 切分 |
| 向量化 | 阿里云 DashScope Embedding | text-embedding-v4 |
| 存储 | ChromaDB | collection: knowledge_base |
| 检索 | 余弦相似度 | top_k=5, threshold=0.2 |

向量模型可以自定义，只需要修改`config.json`中的EMBEDDING_BASE_URL、EMBEDDING_MODEL 即可

---

## 🔧 技能扩展

技能是预定义的可复用指令包，兼容 **clawhub** 生态。

```
work_space/skills/
└── skill-creator-0.1.0/
    ├── SKILL.md          # YAML frontmatter + Markdown 指令
    ├── _meta.json        # 元数据
    └── scripts/          # 配套脚本
```

SKILL.md frontmatter：

```yaml
---
name: skill-name
description: 简要描述
requires:
  env: [API_KEY_NAME]    # 可选：依赖的环境变量
primaryEnv: API_KEY_NAME # 可选：主环境变量名
emoji: 🔧                # 可选：显示图标
---
```

通过 `load_skills()` 自动扫描加载，校验环境变量后标记为「可用/不可用」。

---

## 📡 API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `POST` | `/v1/chat` | 整段对话（非流式） |
| `POST` | `/v1/chat/stream` | SSE 流式对话 |
| `POST` | `/v1/chat/stream/interrupt` | 中断流式对话 |
| `POST` | `/v1/chat/stream/approve` | 提交工具审批决策 |
| `GET` | `/v1/sessions` | 会话列表（分页） |
| `GET` | `/v1/sessions/{id}/messages` | 会话消息（游标分页） |
| `POST` | `/v1/sessions/{id}/messages` | 追加消息 |
| `PUT` | `/v1/sessions/{id}/title` | 修改标题 |
| `DELETE` | `/v1/sessions/{id}` | 删除会话 |
| `GET` | `/v1/tools` | 工具列表 |
| `GET` | `/v1/skills` | 技能列表 |
| `GET` | `/v1/memories` | 记忆文件列表 |
| `POST` | `/v1/knowledge/ingest` | 知识入库 |
| `POST` | `/v1/knowledge/search` | 知识检索 |
| `GET` | `/v1/knowledge/collections` | 知识库集合列表 |
| `GET` | `/v1/knowledge/documents` | 知识文档列表 |
| `GET` | `/v1/mcp-servers` | MCP Server 列表 |
| `POST` | `/v1/mcp-servers` | 创建 MCP Server |
| `PUT` | `/v1/mcp-servers/{id}` | 更新 MCP Server |
| `DELETE` | `/v1/mcp-servers/{id}` | 删除 MCP Server |
| `POST` | `/v1/mcp-servers/{id}/test` | 测试 MCP Server 连接 |
| `GET` | `/v1/scheduled-tasks` | 定时任务列表 |
| `POST` | `/v1/scheduled-tasks` | 创建定时任务 |
| `DELETE` | `/v1/scheduled-tasks/{task_id}` | 删除定时任务 |
| `GET` | `/v1/scheduled-tasks/{task_id}/executions` | 任务执行记录 |
| `GET` | `/v1/api-keys` | API Key 列表 |
| `POST` | `/v1/api-keys` | 创建 API Key |
| `DELETE` | `/v1/api-keys/{key_id}` | 删除 API Key |
| `PATCH` | `/v1/api-keys/{key_id}` | 启用/禁用 API Key |
| `GET` | `/v1/config` | 获取配置列表 |
| `PUT` | `/v1/config` | 更新配置项 |
| `GET` | `/v1/logs` | 日志文件列表 |
| `GET` | `/v1/logs/{filename}` | 日志文件内容 |
| `GET` | `/v1/vm` | VM 列表 |
| `POST` | `/v1/vm/register` | 注册 VM |
| `PUT` | `/v1/vm/{vm_id}` | 更新 VM 配置 |
| `POST` | `/v1/vm/execute` | 流式执行命令 |
| `DELETE` | `/v1/vm/{vm_id}` | 删除 VM |
| `WS` | `/v1/vm/ws` | VM 实时事件 WebSocket |

---

## ⚙️ 完整配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `LLM_API_KEY` | (必填) | DeepSeek API 密钥 |
| `LLM_BASE_URL` | `https://api.deepseek.com` | API 地址 |
| `LLM_MODEL` | `deepseek-v4-flash` | 模型标识 |
| `LLM_TEMPERATURE` | null | 温度参数 |
| `LLM_MAX_TOKENS` | null | 最大输出 Token |
| `LLM_ENABLE_THINKING` | true | 是否启用思考链 |
| `EMBEDDING_API_KEY` | (可选) | 阿里云 Embedding API |
| `EMBEDDING_MODEL` | `text-embedding-v4` | Embedding 模型 |
| `HOST` / `PORT` | `127.0.0.1:21675` | 服务监听地址 |
| `CORS_ORIGINS` | `http://127.0.0.1:5173` | 允许的跨域源 |
| `AGENT_MAX_TURNS` | 20 | 工具循环最大轮次 |
| `TOOL_APPROVAL_MODE` | `dangerous` | 审批模式 |
| `TOOL_APPROVAL_TIMEOUT` | 300 | 审批超时（秒） |
| `CONVERSATION_MAX_CONTEXT_MESSAGES` | 5 | 取最近 N 条消息 |
| `SUMMARY_THRESHOLD_TURNS` | 6 | 摘要触发轮次 |
| `SUMMARY_COMPRESS_TURNS` | 4 | 压缩轮次数 |
| `SUMMARY_KEEP_TURNS` | 2 | 保留原文轮次数 |
| `RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP` | 500 / 150 | 文本切分 |
| `RAG_TOP_K` / `RAG_SIMILARITY_THRESHOLD` | 5 / 0.2 | 检索参数 |
| `SCHEDULER_TIMEZONE` | `Asia/Shanghai` | 时区 |
| `VM_SSH_TIMEOUT` | 60 | SSH 连接超时 |
| `VM_SSH_KEEPALIVE` | 40 | SSH 心跳间隔 |
| `VM_EXECUTE_TIMEOUT` | 30 | 命令执行超时 |
| `VM_DANGEROUS_COMMANDS` | `rm -rf,shutdown...` | 危险命令列表 |

> Agent 可通过 `env_editor` 工具运行时查看和修改配置，无需重启。

---

## 🧪 技术栈

| 层 | 技术 | 版本 |
|---|------|------|
| 语言 | Python | ≥ 3.13 |
| Web 框架 | FastAPI | ≥ 0.136 |
| 模型适配 | DeepSeek API / OpenAI 兼容 | - |
| 向量存储 | ChromaDB | ≥ 1.5.9 |
| Embedding | 阿里云 DashScope / 阿里灵积 | - |
| 调度器 | APScheduler | ≥ 3.10 |
| SSH | asyncssh | (VM 模块) |
| MCP | Python MCP SDK | ≥ 1.0 |
| 数据库 | SQLite (aiosqlite) | - |
| 前端框架 | Vue 3 + TypeScript | ≥ 3.5 |
| UI 库 | Element Plus | ≥ 2.10 |
| 前端构建 | Vite | ≥ 7.1 |

---

## 📦 依赖安装

```bash
# Python 依赖
pip install -r lumen_agent/requirements.txt

# 前端依赖
cd webChannel && npm install
```

---

## 💡 设计原则

1. **模型无关**：通过 `ModelAdapter` 抽象层，理论上可切换任意 LLM（当前适配 DeepSeek）
2. **全局单例模式**：HTTP 连接池 / MCP 管理器 / 审批注册表 / SSE 注册表 / VM 连接服务 均为全局单例
3. **热配置**：Agent 可在运行时修改自身配置，无需重启
4. **双入口**：CLI 模式自动启动后台 HTTP 服务
5. **最小依赖**：核心 Python 依赖仅 10 个，前端仅 8 个

---

## The End

项目持续开发中，欢迎贡献！

联系方式：3194676188@qq.com

<sub>如果觉得本项目有帮助，欢迎给一个 ⭐ Star！</sub>
