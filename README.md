# 流明 Agent (LumenAgent)

> 一个基于大模型的多轮对话 Agent 系统 — 搭载**远程虚拟机操控**、**MCP 协议扩展**、**AI 自动定时任务**、**可插拔技能**、**RAG 知识库**、**双模记忆系统**、**工具审批流**等完整的企业级功能模块。

![Tech Stack](https://img.shields.io/badge/Python-3.10--3.12-3776AB?logo=python&logoColor=fff)
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
| **双认证入口** | Web UI 使用 **JWT 登录认证**，旧 `/v1/chat` 等第三方调用接口继续支持 API Key |
| **用户隔离** | Session 与定时任务按用户归属，普通用户只能访问自己的持久化会话和任务 |
| **断线续订** | 对话生成由后台 ChatRun 托管，切换页面或刷新不会中断，重新订阅后按事件游标补放 |
| **文档读取** | 文件上传最大 100 MB，CSV / Office / PDF 可通过 MarkItDown 转为 Markdown 供 Agent 读取 |
| **管理后台** | 独立 `/admin` 后台支持用户、角色、状态、密码、每日额度及用户会话管理 |

---

## 📋 功能总览

| 模块 | 功能 | 说明 |
|------|------|------|
| **💬 对话** | 流式聊天 | SSE 实时推送，支持思考链、工具调用、正文的端到端流式渲染 |
| **🤖 Agent 模式** | 多轮工具循环 | LLM 自动推理 → 调用工具 → 观察结果 → 继续推理，支持最多 20 轮 |
| **🛠 工具系统** | 内置工具 + MCP 扩展 | 文件读写、MarkItDown 文档解析、命令、网页、知识库、记忆、配置、定时任务、虚拟机和 MCP 工具检索/调用 |
| **🖥 远程虚拟机** | SSH 操控 | Agent 直接连接远程服务器执行命令、查看状态，带 WebSocket 实时回显 |
| **👮 工具审批流** | 三档审批 | 无审批 / 全量审批 / 按危险度审批，前端弹窗实时决策 |
| **🔌 MCP 协议** | 外部工具扩展 | 加载任意 MCP Server 的工具，前端可选择性启用 |
| **⏰ AI 定时任务** | 自动调度 | Agent 对话中创建 cron/interval/date 定时任务，触发时自动执行工具循环 |
| **🧠 知识库** | RAG 向量检索 | 文本切分 → Embedding → ChromaDB 检索，支持入库、删除、重建 |
| **💾 记忆系统** | 自动摘要 + 向量检索 | 每日对话自动摘要落盘，长期记忆自动整理，双重向量语义检索 |
| **📜 会话管理** | 后台运行 + 滑动窗口摘要 | SQLite 持久化，ChatRun 断线续订，游标分页，自动标题生成与串行摘要压缩 |
| **🔌 技能系统** | 可插拔扩展 | SKILL.md 驱动，环境依赖校验，兼容 clawhub 生态 |
| **⚙️ 配置管理** | 热更新 | Agent 调用 `env_editor` 工具随时读/写配置，无需重启服务 |
| **🔐 用户认证** | JWT + 角色与额度 | 登录/刷新/当前用户，管理员与普通用户权限，每日对话额度控制 |
| **🔑 API 安全** | API Key 兼容 | 为旧对话接口和第三方集成保留 Key 创建/列表/启用/禁用管理 |
| **📎 文件处理** | 上传 + 文档转换 | 任意文件类型可上传至工作区，单文件最大 100 MB；常见文档可转 Markdown 读取 |
| **🌐 双入口** | Web UI + CLI | Vue 3 管理控制台；CLI 命令行模式，支持斜杠命令 |

---

## 🗂 项目结构

```text
LumenAgent/
├── lumen_agent/                              # 后端 Python 包
│   ├── agent/                                # Agent 引擎、Prompt、技能、Token 与工具
│   │   └── tools/                            # 文件、MarkItDown、命令、知识库、MCP、VM 等工具
│   ├── api/
│   │   ├── middleware/authentication.py      # JWT / API Key 认证中间件
│   │   ├── routers/                          # 认证、ChatRun、会话、上传、管理后台等路由
│   │   └── schemas/                          # Pydantic DTO 与流事件模型
│   ├── application/service/
│   │   ├── auth/                             # 登录、用户管理与每日额度
│   │   ├── chat/                             # 对话、会话、摘要与标题服务
│   │   ├── embedding/                        # 知识库与记忆向量服务
│   │   └── mcp/                              # MCP Server 与工具检索服务
│   ├── infrastructure/
│   │   ├── chat_run_manager.py               # 后台对话运行、事件缓存与订阅
│   │   ├── data_base/                        # 会话、用户、额度、任务等 SQLite 仓储
│   │   ├── scheduler/                        # APScheduler 与系统任务
│   │   └── start_need/                       # 配置加载、工作区与服务启动
│   └── model_adapters/                       # DeepSeek / OpenAI 协议适配
├── webChannel/                               # Vue 3 + TypeScript 前端
│   └── src/
│       ├── RootApp.vue                       # 登录态与主应用挂载入口
│       ├── App.vue                           # 用户端主应用
│       ├── admin/                            # `/admin` 管理员后台
│       ├── components/                       # 对话与各功能视图
│       ├── composables/                      # ChatRun SSE 与 VM WebSocket
│       └── services/                         # 认证、管理员与会话状态服务
├── work_space/                               # 文件、记忆、规则与技能工作区
├── pyproject.toml                            # Python 包与依赖配置
├── package.json / start.js / install.js      # Node.js 启动/安装脚本
└── lumen_agent/.env / config.json            # 密钥、环境变量与运行配置
```

---

## 🚀 快速启动

### 0️⃣ 一行命令启动（推荐）

确保已安装 [Node.js ≥ 18](https://nodejs.org/) 和 [Python 3.10–3.12](https://www.python.org/) 后：

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

- Python ≥ 3.10 且 < 3.13
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

# ── Web JWT 认证（可选）──
AUTH_ENABLED=true
AUTH_INITIAL_ADMIN_USERNAME=admin
AUTH_INITIAL_ADMIN_PASSWORD=change-me
```

全部可配置项详见 `config.json`（同名 `.env` 变量覆盖）。首次创建 `config.json` 时会用 `secrets.token_urlsafe(48)` 生成 `AUTH_JWT_SECRET`；已有配置文件不会自动补写 Secret，部署时请妥善备份并限制访问权限。

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

> 首次创建 `lumen_agent/config.json` 时会自动生成随机 `AUTH_JWT_SECRET`。如需启用 Web 登录，请配置 `AUTH_ENABLED=true` 和初始管理员密码；API Key 仅用于兼容旧对话接口及第三方调用。

- Swagger 文档：`http://127.0.0.1:21675/docs`
- 健康检查：`http://127.0.0.1:21675/health`

### 5️⃣ 启动前端（开发模式）

```bash
cd webChannel
npm install
npm run dev
```

前端默认运行在 `http://127.0.0.1:5173`，已配置代理转发 API 请求到后端 `21675` 端口。

### 6️⃣ 构建生产版本

```bash
cd webChannel
npm run build
```

构建产物输出到 `webChannel/dist/`，FastAPI 启动后通过唯一前端路由提供静态文件和页面回退，访问 `http://127.0.0.1:21675` 即可。

### 7️⃣ Docker 部署

Docker 镜像只运行一个 FastAPI/Uvicorn 服务，不需要 Compose 或容器内 Nginx：

```bash
docker build -t lumen-agent:latest .

docker run -d \
  --name lumen-agent \
  --restart unless-stopped \
  -p 1675:1675 \
  -e LLM_API_KEY=replace-with-your-api-key \
  -e AUTH_ENABLED=true \
  -e AUTH_JWT_SECRET=replace-with-a-long-random-secret \
  -e AUTH_INITIAL_ADMIN_USERNAME=admin \
  -e AUTH_INITIAL_ADMIN_PASSWORD=replace-with-a-strong-password \
  -v lumen-agent-data:/app/lumen_agent/data \
  -v lumen-agent-workspace:/app/work_space \
  -v lumen-agent-logs:/app/log \
  lumen-agent:latest
```

Dockerfile 默认设置 `HOST=0.0.0.0`、`PORT=1675`，部署后访问 `http://服务器IP:1675`。数据库、向量索引、工作区和日志通过命名卷持久化；SQLite 与进程内 Chroma 只适合运行一个后端容器副本。

| 运行方式 | 访问地址 | 说明 |
|----------|----------|------|
| 本机生产模式 | `http://127.0.0.1:21675` | FastAPI 同时提供前端和后端 |
| 前端开发模式 | `http://127.0.0.1:5173` | Vite 将 `/v1` 和 WebSocket 代理到 `21675` |
| Docker 部署 | `http://服务器IP:1675` | 容器对外只开放一个 FastAPI 端口 |

### 8️⃣ CLI 模式（可选）

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

用户通过 JWT 登录后进入主控制台。左侧栏按功能分组展示对话、工具、技能、记忆、MCP、虚拟机、知识库、定时任务、配置和日志等视图；切换登录用户时会重建前端应用状态，避免复用上一用户的会话缓存。

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

### 管理员后台

管理员可访问独立的 `/admin` 页面：

- 创建用户并设置 `user` / `admin` 角色
- 启用或停用账号、重置密码
- 配置每日对话额度或无限额度
- 查看额度使用量、会话数量、最后登录时间和指定用户的会话
- 普通用户访问管理页时显示无权限状态

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
- **Agent 模式**（默认）— 多轮工具循环，LLM 可调用内置工具及当前会话挂载的 MCP 工具

**输入区**
- 多行文本框（自动调整高度 4–10 行）
- `Enter` 发送，`Ctrl+Enter` 换行
- 发送中可随时中断流式回复
- 支持选择 MCP Server 挂载到当前对话
- 支持图片和任意类型文件上传，单文件最大 100 MB

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

```text
会话消息落库
    │
    ├── 未达到阈值 → 继续保留原始上下文
    │
    └── 达到阈值 → 获取会话级压缩锁
                       │
                       ├── 按 summary_cursor_seq 选择尚未压缩的消息
                       ├── 串行生成并写入摘要
                       ├── 更新摘要游标和轮次计数
                       └── 每日记忆落盘并增量更新向量索引
```

- `SUMMARY_THRESHOLD_TURNS`：累计到指定轮次后触发摘要
- `SUMMARY_COMPRESS_TURNS`：每次压缩的历史轮数
- `SUMMARY_KEEP_TURNS`：保留为原文的最近轮数
- 会话表通过 `compaction_in_progress`、`compaction_started_at` 和 `summary_cursor_seq` 协调摘要任务，避免并发重复压缩
- 上下文组装只引入摘要游标之后的原始消息，避免同一内容以“摘要 + 原文”重复发送给模型
- 摘要结果同时写入每日记忆文件（`YYYY-MM-DD.md`）和 ChromaDB 向量库

### ChatRun 与 SSE 事件流

前端发送消息时先创建后台 ChatRun，再单独订阅事件流：

```text
POST /v1/chat/runs
    │  立即返回 run_id / session_id
    ▼
ChatRunManager 后台执行 Agent
    │
    ├── 缓存带 seq 游标的事件
    ├── Condition 唤醒当前订阅者
    └── 与浏览器连接生命周期解耦
             │
             ▼
GET /v1/chat/runs/{run_id}/events?after={seq}
    ├── 先补放游标之后的存量事件
    └── 再等待并推送新增事件
```

- 切换会话、刷新页面或 SSE 断开只会结束当前订阅，不会取消后台模型任务
- 页面恢复后查询活跃 Run，并使用最后事件游标重新订阅，因此不会丢失已生成内容
- 多个 Session 可以各自维护独立 Run；同一 Session 同时只允许一个活跃 Run，保证消息顺序
- 只有显式调用 `POST /v1/chat/runs/{run_id}/interrupt` 才会请求中断生成
- 审批结果由前端提交一次，后端将 `approval_result` 作为 Run 事件缓存并按游标补放

Agent 模式的主要事件包括：

```text
reasoning_update → message_update → tool_calls → awaiting_approval
→ approval_result → tool_execution_start → tool_execution_end
→ message_update → assistant_done（异常时为 error）
```

---

## 🛠 工具系统详解

### 内置工具能力

| 工具名 | 用途 | 需审批 | 说明 |
|--------|------|--------|------|
| `read` | 读取普通文件 | 否 | 支持绝对路径，按 offset/limit 分块读取 |
| `read_by_markdown` | 读取特殊文档 | 否 | 将 CSV、DOCX、XLSX、DOC、PPTX、PPT、PDF 转为 Markdown |
| `write` | 写入/追加/替换 | 否 | 特殊文档只生成 Markdown 修改稿，并明确告知格式限制 |
| `bash` | 执行 Shell 命令 | 否 | 自动适配 Windows / Unix |
| `web_search` / `web_fetch` | 搜索与抓取网页 | 否 | 搜索网页、HTML 转 Markdown 和文件下载 |
| `knowledge_search` / `knowledge_insert` | 知识检索与入库 | 否 | 检索或写入 ChromaDB 知识库 |
| `memory_search` | 记忆检索 | 否 | 语义检索历史对话记忆 |
| `env_editor` | 配置编辑 | 否 | 运行时读写配置 |
| `mcp_search` / `mcp_call` | MCP 工具发现与调用 | 按目标工具 | 从已同步的 MCP 工具索引中检索并执行 |
| `task_scheduler` | 定时任务管理 | 是 | 创建、列表、删除、暂停和恢复用户定时任务 |
| `virtual_machine_operation` | 虚拟机操作 | 是 | SSH 执行命令、连接、断开和查看状态 |

> 上传接口只校验文件大小，单文件上限为 100 MB。Agent 遇到无法处理的格式时会直接说明不支持；Office、PDF 等特殊文档的修改结果统一输出为 Markdown，不伪造同源格式文件。

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

支持 HTTP 与 Stdio 两类 MCP Server：

- 前端管理 MCP Server 配置并测试连接
- Server 暴露的工具同步到本地索引，描述未变化时复用已有向量
- 对话时通过选择器限定当前会话可使用的 MCP Server
- Agent 先用 `mcp_search` 检索候选工具，再通过 `mcp_call` 执行目标工具

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
  ┌─ 每次执行创建独立 session (job-{uuid})
  ├─ 执行一轮完整的 Agent 工具循环
  ├─ 结果落库到 scheduled_task_executions 表
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

知识库上传与对话附件共用文档读取能力：上传接口不限制扩展名，只限制单文件最大 100 MB；CSV、DOCX、XLSX、DOC、PPTX、PPT、PDF 入库时会先通过 MarkItDown 提取为 Markdown，再进行切分和向量化。

向量模型可以自定义，只需要修改 `config.json` 中的 `EMBEDDING_BASE_URL`、`EMBEDDING_MODEL` 即可。已建立索引的知识和记忆会通过索引检查点复用，源文件变化后才重新向量化。

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

> Web UI 使用 JWT Bearer Token；旧 `/v1/chat`、`/v1/chat/stream` 等兼容接口仍可使用 API Key。开启认证后，普通用户接口会按当前用户过滤 Session 和定时任务。

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `GET` | `/v1/auth/status` | 查询认证是否启用 |
| `POST` | `/v1/auth/login` | 用户登录并签发 JWT |
| `POST` | `/v1/auth/refresh` | 刷新即将过期的 JWT |
| `GET` | `/v1/auth/me` | 获取当前用户 |
| `POST` | `/v1/chat/runs` | 创建后台 ChatRun，立即返回运行标识 |
| `GET` | `/v1/chat/runs` | 查询当前进程内的活跃 Run |
| `GET` | `/v1/chat/runs/{run_id}` | 查询 Run 状态与事件游标 |
| `GET` | `/v1/chat/runs/{run_id}/events?after={seq}` | 补放并实时订阅 Run 的 SSE 事件 |
| `POST` | `/v1/chat/runs/{run_id}/interrupt` | 显式中断后台 Run |
| `POST` | `/v1/chat/stream/approve` | 提交工具审批结果 |
| `POST` | `/v1/chat` | 旧非流式对话接口 |
| `POST` | `/v1/chat/stream` | 旧流式对话接口 |
| `GET` | `/v1/sessions` | 当前用户的会话列表 |
| `GET` | `/v1/sessions/{id}/messages` | 会话消息 |
| `POST` | `/v1/sessions/{id}/messages` | 追加消息 |
| `PUT` | `/v1/sessions/{id}/title` | 修改标题 |
| `DELETE` | `/v1/sessions/{id}` | 删除会话 |
| `POST` | `/v1/upload` | 上传任意类型文件，最大 100 MB |
| `GET` | `/v1/files/{filename}` | 获取已上传文件 |
| `GET` / `POST` | `/v1/configs` | 获取或更新配置 |
| `GET` | `/v1/tools` / `/v1/skills` / `/v1/memories` | 工具、技能与记忆 |
| `POST` | `/v1/knowledge/ingest` / `/v1/knowledge/search` | 知识入库与检索 |
| `GET` / `POST` | `/v1/mcp/http-servers` | HTTP MCP Server 管理 |
| `GET` / `POST` | `/v1/mcp/stdio-servers` | Stdio MCP Server 管理 |
| `POST` | `/v1/mcp/tools/search` | 检索已同步的 MCP 工具 |
| `GET` / `POST` | `/v1/scheduler/jobs` | 当前用户的定时任务 |
| `GET` / `POST` | `/v1/api-keys` | API Key 列表与创建 |
| `GET` / `POST` | `/v1/vm/...` | VM 配置、连接与命令执行 |
| `WS` | `/v1/vm/ws` | VM 实时事件 WebSocket |

管理员接口（仅 `admin` 角色）：

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` / `POST` | `/v1/admin/users` | 查询或创建用户 |
| `PATCH` | `/v1/admin/users/{user_id}` | 修改角色、启用状态和额度 |
| `PUT` | `/v1/admin/users/{user_id}/password` | 重置密码 |
| `GET` | `/v1/admin/users/{user_id}/sessions` | 查看指定用户的会话 |

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
| `AUTH_ENABLED` | false | 是否启用 Web JWT 登录认证 |
| `AUTH_JWT_SECRET` | 首次生成 | JWT 签名密钥，仅首次创建 config.json 时自动生成 |
| `AUTH_JWT_EXPIRE_HOURS` | 24 | JWT 有效期（小时） |
| `AUTH_JWT_REFRESH_BEFORE_HOURS` | 8 | 进入此时间窗口后允许刷新 JWT |
| `AUTH_DAILY_QUOTA_TIMEZONE` | `Asia/Shanghai` | 每日对话额度结算时区 |
| `AUTH_INITIAL_ADMIN_USERNAME` | `admin` | 首次初始化管理员用户名 |
| `AUTH_INITIAL_ADMIN_PASSWORD` | 空 | 首次初始化管理员密码；启用认证时必须配置 |
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
| 语言 | Python | ≥ 3.10 且 < 3.13 |
| Web 框架 | FastAPI | ≥ 0.136 |
| 模型适配 | DeepSeek / OpenAI Chat Completions / Responses API | - |
| 向量存储 | ChromaDB | ≥ 1.5.9 |
| Embedding | 阿里云 DashScope / 阿里灵积 | - |
| 调度器 | APScheduler | ≥ 3.10 |
| SSH | asyncssh | (VM 模块) |
| MCP | Python MCP SDK | ≥ 1.0 |
| 文档转换 | MarkItDown | ≥ 0.1.6 |
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

1. **模型无关**：通过 `ModelAdapter` 抽象层统一 DeepSeek、OpenAI Chat Completions 与 Responses API 的流事件
2. **后台运行解耦**：ChatRunManager 持有生成任务和事件缓存，SSE 订阅断开不影响 Agent 执行
3. **热配置**：Agent 可在运行时修改自身配置，无需重启
4. **双入口**：CLI 模式自动启动后台 HTTP 服务
5. **用户边界**：Session 和定时任务携带用户归属，管理员可通过专用接口查看用户会话

---

## The End

项目持续开发中，欢迎贡献！

联系方式：3194676188@qq.com

<sub>如果觉得本项目有帮助，欢迎给一个 ⭐ Star！</sub>
