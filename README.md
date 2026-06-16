# 流明 Agent (LumenAgent)

> 一个基于 DeepSeek 大模型的多轮对话 Agent 系统，搭载完整的工具调用框架、RAG 知识库、记忆系统和可插拔技能体系。

![Tech Stack](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=fff)
![Framework](https://img.shields.io/badge/FastAPI-0.136+-009688?logo=fastapi&logoColor=fff)
![Frontend](https://img.shields.io/badge/Vue_3-4FC08D?logo=vue.js&logoColor=fff)
![LLM](https://img.shields.io/badge/DeepSeek-4F5B66?logo=data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjQiIGhlaWdodD0iNjQiIHZpZXdCb3g9IjAgMCA2NCA2NCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48Y2lyY2xlIGN4PSIzMiIgY3k9IjMyIiByPSIzMiIgZmlsbD0iIzRGNUI2NiIvPjwvc3ZnPg==)

---

## 📋 功能总览

| 模块 | 功能 | 说明 |
|------|------|------|
| **💬 对话** | 流式聊天 | SSE 实时推送，支持思考链、工具调用、正文的端到端流式渲染 |
| **🤖 Agent 模式** | 多轮工具循环 | LLM 自动推理 → 调用工具 → 观察结果 → 继续推理，支持最多 20 轮 |
| **🛠 工具系统** | 9 个内置工具 | Read / Write / Bash / WebSearch / WebFetch / KnowledgeSearch / KnowledgeInsert / MemorySearch / EnvEditor |
| **🧠 知识库** | RAG 向量检索 | 文本切分 → Embedding → ChromaDB 检索，支持入库、删除、重建 |
| **💾 记忆系统** | 自动摘要 + 向量检索 | 每日对话自动摘要落盘，长期记忆整理，语义检索历史记忆 |
| **📜 会话管理** | 滑动窗口摘要 | SQLite 持久化，游标分页，自动标题生成 |
| **🔌 技能系统** | 可插拔扩展 | SKILL.md 驱动，环境依赖校验，可用/不可用状态明确 |
| **⚙️ 配置管理** | 热更新 .env | EnvEditor 工具随时读/写配置，无需重启服务 |
| **🌐 双入口** | Web UI + CLI | Vue 3 前端看板；CLI 命令行模式，支持斜杠命令 `/new` `/exit` |

---

## 🗂 项目结构

```
LumenAgent/
├── lumen_agent/                      # 后端 Python 包
│   ├── agent/
│   │   ├── agent.py                  # AgentStreamExecutor — 多轮工具循环引擎
│   │   ├── context.py                # 上下文管理、防循环守卫、消息压缩
│   │   ├── memory/                   # 记忆文件工具类
│   │   │   └── memory_utils.py
│   │   ├── prompts/                  # System Prompt 构造器
│   │   │   ├── builder.py
│   │   │   └── docs/                 # Prompt 模板（摘要、记忆整理）
│   │   ├── skills/                   # 技能加载器
│   │   │   ├── loader.py
│   │   │   └── meta.py
│   │   ├── tokens/                   # Token 计数
│   │   │   ├── char_counter.py
│   │   │   └── tiktoken_counter.py
│   │   └── tools/                    # 工具实现（9 个）
│   │       ├── base.py               # BaseTool + ToolResult 基类
│   │       ├── registry.py           # 工具注册表
│   │       ├── read.py               # 读取文件
│   │       ├── write.py              # 写入/替换文件
│   │       ├── bash.py               # 执行 Shell 命令
│   │       ├── web_search.py         # DuckDuckGo 搜索
│   │       ├── web_fetch.py          # 网页抓取
│   │       ├── knowledge.py          # 知识库检索与入库
│   │       ├── memory_search.py      # 记忆向量检索
│   │       └── env_editor.py         # .env 配置编辑
│   ├── api/
│   │   ├── routers/
│   │   │   ├── chat.py               # POST /v1/chat  + SSE /v1/chat/stream
│   │   │   ├── sessions.py           # 会话 CRUD + 游标分页
│   │   │   ├── tools.py              # 工具列表
│   │   │   ├── skills.py             # 技能列表
│   │   │   ├── knowledge.py          # 知识库 API
│   │   │   └── memories.py           # 记忆文件展示
│   │   └── schemas/                  # Pydantic DTO + SSE 事件定义
│   ├── application/
│   │   ├── service/
│   │   │   ├── chat_service.py       # 对话编排（单轮/流式/Agent）
│   │   │   ├── summary_service.py    # 滑动窗口摘要 + 长期记忆整理
│   │   │   ├── rag_service.py        # 知识库 RAG 服务
│   │   │   ├── memory_rag_service.py # 记忆向量检索服务
│   │   │   └── title_service.py      # 会话标题自动生成
│   │   ├── common/
│   │   │   ├── chat_in_cli.py        # CLI 对话入口
│   │   │   └── context_assembly.py   # 上下文组装 + Token 预算检查
│   │   └── utils/
│   │       ├── text_splitter.py      # 文本切分
│   │       └── llm_error_policy.py   # LLM 链路错误映射
│   ├── infrastructure/
│   │   ├── client/
│   │   │   ├── deepseek_client.py    # DeepSeek HTTP 客户端
│   │   │   ├── embedding_client.py   # 阿里云 Embedding 客户端
│   │   │   └── chroma_client.py      # Chroma 向量存储封装
│   │   ├── data_base/
│   │   │   ├── sqlite_conversation.py # 会话 SQLite 仓储
│   │   │   └── sqlite_knowledge.py   # 知识库 SQLite 仓储
│   │   ├── http_pool.py              # 共享 HTTP 连接池
│   │   └── sse_registry.py           # SSE 中断注册表
│   ├── model_adapters/               # 模型适配层
│   │   ├── base.py                   # ModelAdapter 抽象
│   │   └── deepseek.py               # DeepSeek 适配器
│   ├── domain/
│   │   ├── ports.py                  # 仓储接口（Protocol）
│   │   └── messages.py               # 消息格式化工具
│   ├── config.py                     # pydantic-settings 配置
│   └── app.py                        # FastAPI 应用工厂
│
├── webChannel/                       # 前端 Vue 3 + TypeScript
│   ├── src/
│   │   ├── App.vue                   # 主布局（侧边栏 + 顶栏 + 内容区 + 输入区）
│   │   ├── components/
│   │   │   ├── ChatView.vue          # 对话面板（消息列表 + 会话列表）
│   │   │   ├── ChatMessage.vue       # 单条消息渲染（Markdown / 思考链 / 工具调用）
│   │   │   ├── SessionList.vue       # 会话列表（新建/删除/切换）
│   │   │   ├── AppComposer.vue       # 底部输入区（发送/中断/模式切换）
│   │   │   ├── AppTopbar.vue         # 顶栏（页面标题 + 操作按钮）
│   │   │   ├── ToolView.vue          # 工具浏览面板
│   │   │   ├── SkillView.vue         # 技能浏览面板
│   │   │   └── MemoryView.vue        # 记忆文件浏览面板
│   │   ├── types.ts                  # TypeScript 类型定义
│   │   ├── utils/markdown.ts         # Markdown + 代码高亮渲染
│   │   └── styles.css                # 全局样式
│   └── vite.config.ts                # Vite 配置
│
├── work_space/                       # 工作空间
│   ├── memory/                       # 每日记忆文件（YYYY-MM-DD.md）
│   ├── skills/                       # 技能包目录
│   ├── ME.md                         # 项目上下文
│   ├── USER.md                       # 用户信息
│   ├── RULE.md                       # 工作规则
│   └── MEMORY.md                     # 长期记忆文件
│
├── pyproject.toml                    # Python 包配置
└── lumen_agent/.env                  # 环境变量配置
```

---

## 🚀 快速启动

### 1️⃣ 环境要求

- Python ≥ 3.13
- Node.js ≥ 18
- 一个 DeepSeek API Key
- 一个阿里云 DashScope API Key（仅知识库 RAG + 记忆向量检索需要，纯对话可不配）

### 2️⃣ 配置环境变量
>tips:项目中的`config.py`比较杂，大家还行先别看。。后续会优化掉的。目前项目只支持deepseek模型，后续会支持其它模型

创建 `lumen_agent/.env` 文件（项目内已包含模板）：

```env
# ── LLM 配置 ──
LLM_API_KEY=sk-your-deepseek-api-key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash

# ── 阿里云 Embedding（可选，知识库 RAG + 记忆向量检索需要，纯对话可不配）──
EMBEDDING_API_KEY=sk-your-dashscope-api-key
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings
EMBEDDING_MODEL=text-embedding-v4

# ── 服务端口 ──
HOST=127.0.0.1
PORT=8000
```

### 3️⃣ 启动后端

```bash
# 安装 Python 依赖
pip install -r lumen_agent/requirements.txt

# 启动服务
python -m lumen_agent.app
```

后端默认运行在 `http://127.0.0.1:8000`。
- API 文档（Swagger）：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`

### 4️⃣ 启动前端

```bash
cd webChannel

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build
```

前端开发服务器默认运行在 `http://127.0.0.1:5173`，已配置代理转发 API 请求到后端。

### 5️⃣ CLI 模式（可选）

```bash
# 纯 CLI 聊天（自动同时启动 HTTP 服务）
lumen-cli

# 或者
python -m lumen_agent.application.common.chat_in_cli
```

CLI 支持斜杠命令：
- `/exit` — 退出
- `/new` — 新建会话
- `/knowledge` — 进入知识库操作菜单

---

## 🖥 前端界面解说

### 主界面布局

```
┌─────────────────────────────────────────────────────────┐
│  ┌──────────┐  ┌──────────────────────────────────────┐ │
│  │ 品牌标识  │  │  AppTopbar 顶栏                     │ │
│  │          │  │  标题 + Agent/Simple 切换 + 操作按钮  │ │
│  ├──────────┤  ├──────────────────────────────────────┤ │
│  │ 导航菜单  │  │                                      │ │
│  │          │  │                                      │ │
│  │ ● 对话   │  │    主内容区                          │ │
│  │ ○ 工具   │  │    （ChatView / ToolView /            │ │
│  │ ○ 技能   │  │     SkillView / MemoryView）          │ │
│  │ ○ 记忆   │  │                                      │ │
│  │          │  │                                      │ │
│  └──────────┘  ├──────────────────────────────────────┤ │
│                │  AppComposer 输入区                   │ │
│                │  [多行输入框.............] [发送/中断] │ │
│                │  [○ Simple  ● Agent]                │ │
│                └──────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 1️⃣ 对话视图（Chat）

**会话列表（左侧面板）**
- 显示所有历史会话，按更新时间排序
- 显示相对时间（"3 分钟前"、"2 天前"）
- 支持创建新会话、切换会话、删除会话（带确认弹窗）
- 可折叠收起

**消息区域**
- **用户消息** — 蓝色气泡，纯文本显示
- **助手消息** — 白色气泡，支持以下区块类型：

  | 区块 | 展示方式 | 说明 |
  |------|---------|------|
  | 💭 思考链 | 可折叠 details | DeepSeek 的 reasoning_content，默认收起 |
  | 正文 | Markdown 渲染 | 支持代码高亮、表格、链接等 GFM 语法 |
  | 🛠 工具调用 | 可折叠 details | 显示工具名称、调用参数、执行结果，按工具分组 |
  | ⚠️ 错误 | 可折叠 details | 显示错误信息，附带「重试」按钮 |

- 流式输出时显示闪烁光标 `▍`
- 代码块右上角有「复制」按钮
- 顶部加载更多 / "已加载全部消息" 指示器
- 滚动到底部按钮（当不在底部时显示）

**模式切换**
- **Simple 模式** — 单轮对话，LLM 直接回复
- **Agent 模式**（默认）— 进入多轮工具循环，LLM 可调用工具、观察结果、继续推理

**输入区**
- 多行文本框（自动调整高度，4–10 行）
- `Enter` 发送，`Ctrl+Enter` 换行
- 发送中按钮变为「中断」按钮，可随时中断流式回复

### 2️⃣ 工具视图（Tools）

浏览 Agent 当前可调用的全部工具：

- 卡片式布局，每张卡片展示工具名称、描述
- 可展开查看工具的参数结构（JSON Schema）
- 点击「查看详情」弹窗展示完整信息
- 顶部显示工具总数和连接状态

内置 9 个工具：

| 工具名 | 用途 | 说明 |
|--------|------|------|
| `read` | 读取文件 | 支持 offset/limit 分块，单次 2000 行 / 50KB |
| `write` | 写入文件 | 支持覆盖/追加/子串替换三种模式 |
| `bash` | 执行命令 | 自动适配 Windows PowerShell / Unix Bash，30s 超时 |
| `web_search` | 网页搜索 | 基于 DuckDeeDuckGo，无需额外 API Key |
| `web_fetch` | 网页抓取 | HTML 自动转 Markdown，支持文件下载 |
| `knowledge_search` | 知识检索 | RAG 向量检索，从知识库中查找相关 chunk |
| `knowledge_insert` | 知识入库 | 将文本或文件入库到知识库 |
| `memory_search` | 记忆检索 | 语义检索历史对话记忆 |
| `env_editor` | 配置编辑 | 读/写 .env 配置，热更新无需重启 |

### 3️⃣ 技能视图（Skills）

展示所有可插拔技能的状态：

- 绿色标签 = 可用，灰色标签 = 缺失环境
- 显示技能路径、主环境、依赖环境列表
- 缺失环境以橙色高亮提示
- 点击「查看详情」弹窗展示完整元信息

### 4️⃣ 记忆视图（Memories）

浏览 Agent 的持久化记忆文件：

- 顶部统计：记忆文件总数、长期记忆数、每日记忆数
- 卡片列表区分：
  - 📌 **长期记忆**（MEMORY.md）— 黄色卡片，重要摘要索引
  - 📅 **每日记忆**（YYYY-MM-DD.md）— 白色卡片，自动记录的会话摘要
- 内容预览（前 120 字符）
- 点击「查看详情」弹窗显示文件完整内容

---

## 🧠 核心架构解读

### Agent 工具循环

```
用户输入
    │
    ▼
┌─────────────────────────────┐
│  上下文组装                  │
│  （摘要 + 历史消息 + 本轮）  │
└──────────┬──────────────────┘
           ▼
┌─────────────────────────────┐
│  LLM 推理（流式）            │
│  输出文本 + 思考链 + 工具调用 │
└──────┬──────────────────────┘
       │
       ├── 无工具调用 → yield "done" → 结束
       │
       └── 有工具调用 → 逐个执行工具
               │
               ├── read / write / bash
               ├── web_search / web_fetch
               ├── knowledge_search / knowledge_insert
               ├── memory_search
               └── env_editor
               │
               ▼
           工具结果返回 LLM → 继续推理（最多 20 轮）
```

### 滑动窗口摘要

```
轮次:  1  2  3  4  5  6  │  7  8  9 ...
                        │
                        ▼
                    ┌───────────┐
                    │ 触发摘要   │
                    │ (count=6)  │
                    └───────────┘
                          │
                    压缩前 4 轮为摘要
                    保留后 2 轮为原文
                    count 重置为 2
```

- `summary_threshold_turns=6`：每 6 轮触发一次摘要
- `summary_compress_turns=4`：前 4 轮压缩
- `summary_keep_turns=2`：后 2 轮保留
- 摘要结果同时写入每日记忆文件（YYYY-MM-DD.md）和 ChromaDB 向量库

### SSE 事件流

Agent 模式下，前端收到的 SSE 事件流：

```
event: reasoning_update    ← 思考链增量
event: message_update      ← 正文增量
event: tool_calls          ← 本轮工具调用列表
event: tool_execution_start ← 单个工具开始执行
event: tool_execution_end  ← 单个工具执行完毕（含耗时）
event: reasoning_update    ← 工具结果返回后继续思考
event: message_update      ← 最终回复
event: assistant_done      ← 本轮完成
event: error               ← 错误（可选）
[DONE]                     ← 流结束标记
```

---

## 📡 API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `POST` | `/v1/chat` | 整段对话（非流式） |
| `POST` | `/v1/chat/stream` | SSE 流式对话 |
| `POST` | `/v1/chat/stream/interrupt` | 中断流式对话 |
| `GET` | `/v1/sessions` | 会话列表（分页） |
| `GET` | `/v1/sessions/{id}/messages` | 会话消息（游标分页） |
| `POST` | `/v1/sessions/{id}/messages` | 追加消息 |
| `PUT` | `/v1/sessions/{id}/title` | 修改标题 |
| `DELETE` | `/v1/sessions/{id}` | 删除会话 |
| `GET` | `/v1/sessions/{id}/summary` | 会话摘要 |
| `GET` | `/v1/tools` | 工具列表 |
| `GET` | `/v1/skills` | 技能列表 |
| `GET` | `/v1/memories` | 记忆文件列表 |
| `POST` | `/v1/knowledge/ingest` | 知识入库 |
| `POST` | `/v1/knowledge/search` | 知识检索 |
| `GET` | `/v1/knowledge/collections` | 知识库集合列表 |
| `GET` | `/v1/knowledge/documents` | 知识文档列表 |

---

## ⚙️ 配置说明

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `deepseek_api_key` | (必填) | DeepSeek API 密钥 |
| `deepseek_base_url` | `https://api.deepseek.com` | API 地址 |
| `deepseek_model` | `deepseek-v4-flash` | 模型标识 |
| `embedding_api_key` | (RAG/记忆用) | 阿里云 Embedding API 密钥，纯对话场景可不配 |
| `host` / `port` | `127.0.0.1:8000` | 服务监听地址 |
| `conversation_max_context_messages` | 5 | 取最近 N 条消息作为上下文 |
| `summary_threshold_turns` | 6 | 摘要触发轮次阈值 |
| `agent_max_turns` | 20 | Agent 工具循环最大轮次 |
| `rag_chunk_size` / `rag_chunk_overlap` | 500 / 150 | 知识库文本切分配置 |
| `rag_top_k` | 5 | 向量检索返回最匹配条数 |
| `agente_tool_choice` | `auto` | 工具调用策略 |

> 可以通过 Agent 调用 `env_editor` 工具随时查看和修改配置，修改后自动生效。

---

## 🔧 技能扩展

技能是预定义的可复用指令包。放在 `work_space/skills/` 目录下，每个技能一个子目录，包含 `SKILL.md` 描述文件。

```
work_space/skills/
└── skill-creator-0.1.0/
    ├── SKILL.md          # YAML frontmatter + Markdown 指令
    ├── _meta.json        # 元数据
    └── scripts/          # 配套脚本
```

SKILL.md 的 frontmatter 需包含：
```yaml
---
name: skill-name
description: 简要描述
requires:
  env: [API_KEY_NAME]     # 可选：依赖的环境变量
primaryEnv: API_KEY_NAME  # 可选：主环境变量名
emoji: 🔧                 # 可选：显示图标
---
```

技能会通过 `load_skills()` 自动扫描加载，校验环境变量是否完整后标记为「可用/不可用」，在 System Prompt 中告知 LLM。

**本项目中的SKILL完美契合clawhub，所以大家可以在clawhub上安装SKILL后放到 `LumenAgent\work_space\skills`  这个文件夹中即可**

---

## 📝 记忆系统

记忆系统分两层：

### 每日记忆（`work_space/memory/YYYY-MM-DD.md`）
- 每次会话摘要触发时自动追加
- 按 `---` 分隔 + `## timestamp session=xxx` 头部标记
- 自动向量化写入 ChromaDB（独立 collection `memory_store`）

### 长期记忆（`work_space/memory/MEMORY.md`）
- 当文件超过 150KB 时自动触发整理
- LLM 压缩重写，保持内容精炼

### 检索方式
- Agent 通过 `memory_search` 工具语义检索
- 前端通过「记忆」面板浏览所有文件内容

---

## The End

该项目是我们独自开发的agent项目，前端界面不好看是因为我不会前端开发TAT。如果有小伙伴想要参与到开发过程中的话可以联系我的邮箱：3194676188@qq.com。最后还希望大家可以给我点一个免费的star（是我开发下去的动力啊😘）
> 如有侵权请联系我

