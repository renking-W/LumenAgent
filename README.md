# 流明 Agent（LumenAgent）

一个面向个人使用与工程实践的 AI Agent 系统。LumenAgent 将多轮对话、工具调用、记忆、知识库、MCP、定时任务、远程主机操作和微信通道整合在同一套运行链路中。

![Python](https://img.shields.io/badge/Python-3.10--3.12-3776AB?logo=python&logoColor=fff)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136+-009688?logo=fastapi&logoColor=fff)
![Vue](https://img.shields.io/badge/Vue_3-4FC08D?logo=vue.js&logoColor=fff)
![License](https://img.shields.io/badge/License-MIT-2F855A)

## 核心能力

| 能力 | 说明 |
|---|---|
| Agent 对话 | 支持思考、工具调用、工具结果和正文的 SSE 流式输出 |
| 后台运行 | 对话由 ChatRun 托管，刷新或切换页面不会中断生成 |
| 工具系统 | 文件、网页、命令、知识库、记忆、配置、定时任务、VM 与 MCP 工具 |
| 工具审批 | 支持无审批、全部审批和危险工具审批 |
| 文件处理 | 上传文件到工作区；CSV、Office 和 PDF 可转换为 Markdown 读取 |
| 记忆系统 | 自动生成每日记忆并维护长期记忆，支持向量检索 |
| 知识库 | 文档切分、Embedding、ChromaDB 存储与语义检索 |
| MCP | 支持 HTTP 和 Stdio MCP Server，可按会话选择工具 |
| 定时任务 | Agent 可创建 cron、interval 和 date 类型任务 |
| 远程主机 | 通过 SSH 执行命令，并在 Web 终端中实时显示输出 |
| 用户系统 | JWT 登录、角色权限、每日额度、用户会话和管理员后台 |
| 微信通道 | 管理员扫码绑定个人微信，消息进入完整 Agent 链路 |
| 外部 API | 使用 API Key 接入 Agent、记忆、工具、Skill、知识库和 MCP |

## 运行架构

~~~mermaid
flowchart LR
    UI["Web / 微信 / 外部 API"] --> API["FastAPI"]
    API --> RUN["ChatRun Manager"]
    RUN --> AGENT["Agent 工具循环"]
    AGENT --> LLM["LLM"]
    AGENT --> TOOLS["内置工具 / MCP / Skill"]
    AGENT --> DATA["SQLite / ChromaDB / 工作区"]
    RUN --> UI
~~~

核心设计：

- FastAPI 同时提供 API 和构建后的 Vue 静态资源。
- ChatRun 在后台执行对话，前端通过事件游标订阅和补放消息。
- Agent 统一装配系统规则、用户信息、会话历史、摘要、记忆、Skill 和工具。
- SQLite 保存用户、会话、消息、任务与配置数据。
- ChromaDB 保存知识、记忆和 MCP 工具向量。
- 工作区保存上传文件、规则、记忆和 Skill。
- 微信 Node 子进程由 FastAPI 生命周期托管，不单独暴露公网端口。

## 快速开始

### 环境要求

- Python 3.10 至 3.12
- Node.js 22 或更高版本
- 一个可用的 LLM API Key
- Embedding API Key 可选；知识库和记忆向量检索需要使用

### 1. 获取项目

~~~bash
git clone https://github.com/renking-W/LumenAgent.git
cd LumenAgent
~~~

### 2. 安装依赖

~~~bash
npm install
npm --prefix weixinChannel install
~~~

根目录安装脚本会准备 Python 环境和前端依赖。第二条命令安装微信通道依赖；不使用微信时也可以安装，后续无需额外处理。

网络较慢时可以配置镜像：

~~~bash
npm config set registry https://registry.npmmirror.com
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
~~~

### 3. 配置服务

创建 **lumen_agent/.env**：

~~~env
LLM_PROVIDER=deepseek
LLM_API_KEY=sk-your-llm-api-key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat

AUTH_ENABLED=true
AUTH_INITIAL_ADMIN_USERNAME=admin
AUTH_INITIAL_ADMIN_PASSWORD=change-this-password

# 知识库和记忆向量检索需要配置
EMBEDDING_API_KEY=sk-your-embedding-api-key
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings
EMBEDDING_MODEL=text-embedding-v4
~~~

配置优先级为：

~~~text
系统环境变量 > lumen_agent/.env > lumen_agent/config.json > 内置默认值
~~~

服务启动时会生成 **lumen_agent/config.json** 和 JWT Secret。其他运行参数可以在管理员前端的“系统配置”页面中修改。

### 4. 启动

~~~bash
npm start
~~~

默认地址：

- Web 控制台：http://127.0.0.1:21675
- Swagger：http://127.0.0.1:21675/docs
- 健康检查：http://127.0.0.1:21675/health
- 管理后台：http://127.0.0.1:21675/admin

使用配置中的管理员账号登录后，即可设置模型、Embedding、MCP 和其他运行参数。

## Docker 部署

Docker 镜像包含 Python 后端、Vue 前端和微信 Node 运行时。容器对外只开放 1675 端口。

### 1. 准备配置

在项目根目录创建 **lumen_agent/config.json**。未列出的字段由内置默认值补齐：

~~~json
{
  "LLM_PROVIDER": "deepseek",
  "LLM_API_KEY": "sk-your-llm-api-key",
  "LLM_BASE_URL": "https://api.deepseek.com",
  "LLM_MODEL": "deepseek-chat",
  "AUTH_ENABLED": true,
  "AUTH_JWT_SECRET": "replace-with-a-long-random-secret",
  "AUTH_INITIAL_ADMIN_USERNAME": "admin",
  "AUTH_INITIAL_ADMIN_PASSWORD": "change-this-password",
  "EMBEDDING_API_KEY": "",
  "EMBEDDING_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings",
  "EMBEDDING_MODEL": "text-embedding-v4"
}
~~~

建议使用以下命令生成 JWT Secret：

~~~bash
openssl rand -hex 48
~~~

### 2. 构建镜像

~~~bash
docker build --network=host --progress=plain -t lumen-agent:latest .
~~~

### 3. 准备持久化目录

~~~bash
mkdir -p lumen_agent/data work_space log weixinChannel/data

LUMEN_UID=$(docker run --rm --entrypoint id lumen-agent:latest -u lumen)
LUMEN_GID=$(docker run --rm --entrypoint id lumen-agent:latest -g lumen)

chown -R "$LUMEN_UID:$LUMEN_GID" \
  lumen_agent/data work_space log weixinChannel/data
chown "$LUMEN_UID:$LUMEN_GID" lumen_agent/config.json
~~~

### 4. 运行容器

~~~bash
docker run -d \
  --name lumen-agent \
  --restart unless-stopped \
  -p 1675:1675 \
  -e TZ=Asia/Shanghai \
  -v /usr/share/zoneinfo/Asia/Shanghai:/etc/localtime:ro \
  --mount type=bind,src="$(pwd)/lumen_agent/config.json",dst=/app/lumen_agent/config.json \
  -v "$(pwd)/lumen_agent/data:/app/lumen_agent/data" \
  -v "$(pwd)/work_space:/app/work_space" \
  -v "$(pwd)/log:/app/log" \
  -v "$(pwd)/weixinChannel/data:/app/weixinChannel/data" \
  lumen-agent:latest
~~~

访问：

~~~text
http://服务器IP:1675
~~~

常用命令：

~~~bash
docker logs -f lumen-agent
docker ps --filter name=lumen-agent
docker restart lumen-agent
docker rm -f lumen-agent
~~~

生产环境建议使用域名和 HTTPS 反向代理，仅将 HTTPS 端口开放给公网。

## 控制台功能

| 页面 | 用途 |
|---|---|
| 对话 | 创建和管理会话，查看流式回复、工具调用与审批 |
| 工具 | 浏览 Agent 可调用的内置工具 |
| 技能 | 查看工作区中可用的 Skill |
| 记忆 | 浏览长期记忆和每日记忆 |
| MCP | 管理 HTTP 与 Stdio MCP Server |
| 虚拟机 | 管理 SSH 主机和 Web 实时终端 |
| 知识库 | 上传、检索、查看和重建知识文档 |
| 定时任务 | 查看任务状态、触发规则和执行记录 |
| 系统配置 | 修改模型、Embedding 和运行参数 |
| 日志 | 查看和下载后端日志 |
| 微信接入 | 管理员扫码绑定或解除个人微信 |
| 管理后台 | 管理用户、角色、密码、额度和用户会话 |

## Agent 与数据

### 对话运行

前端发送消息后，后端创建 ChatRun 并返回运行标识。Agent 在后台继续执行，前端通过 SSE 订阅事件。连接断开后，再次订阅会从事件游标后补放内容；只有显式点击中断按钮才会请求停止生成。

### 摘要与记忆

长会话会按配置的窗口自动生成摘要。摘要游标和会话级任务状态用于避免并发重复压缩。摘要内容会写入每日记忆，并增量更新向量索引。

~~~text
work_space/memory/
├── MEMORY.md
└── YYYY-MM-DD.md
~~~

### 文件与知识库

上传接口只限制文件大小，单文件最大 100 MB。CSV、DOCX、XLSX、DOC、PPTX、PPT 和 PDF 可以通过 MarkItDown 转换为 Markdown。

特殊文档的修改结果以 Markdown 文件返回，不生成同格式的 Office 或 PDF 文件。无法处理的文件会直接向用户说明。

知识库使用 Embedding 和 ChromaDB。文件内容未变化时复用已有向量，内容变化后重新建立索引。

### 微信通道

管理员在“微信接入”页面扫码绑定账号。绑定状态保存在 **weixinChannel/data**，FastAPI 启动时自动运行微信通道。

微信消息使用固定会话 **wechat-personal**，并进入完整 Agent 流程。工具权限为直接执行；工具调用前，系统会先把已经生成的正文发送到微信。

微信通道目前处理文字消息。详细说明见 [weixinChannel/README.md](weixinChannel/README.md)。

## API 接入

Web 控制台使用 JWT Bearer Token。外部客户端使用 API Key 调用对话接口，API Key 可以在管理员界面创建。

Agent 模式会装配：

- 会话历史与摘要
- RULE.md 和 USER.md
- 长期记忆与每日记忆
- 内置工具和工具审批
- Skill
- 知识库
- MCP Server
- 服务端模型配置

接口、认证、SSE 事件和请求示例见 [API.md](API.md)。

## 项目结构

~~~text
LumenAgent/
├── lumen_agent/        # FastAPI、Agent、模型适配、存储与后台服务
├── webChannel/         # Vue 3 管理控制台
├── weixinChannel/      # 微信协议适配与 SDK
├── work_space/         # 上传文件、规则、记忆和 Skill
├── Dockerfile
├── API.md
└── README.md
~~~

主要后端目录：

~~~text
lumen_agent/
├── agent/              # Agent 引擎、Prompt 和工具
├── api/                # HTTP、SSE、WebSocket 路由和 DTO
├── application/        # 对话、认证、知识库和 MCP 服务
├── infrastructure/     # SQLite、ChatRun、调度器和进程管理
└── model_adapters/     # LLM 协议适配
~~~

## 开发命令

启动前端开发服务：

~~~bash
npm --prefix webChannel run dev
~~~

前端类型检查：

~~~bash
npm --prefix webChannel run typecheck
~~~

微信通道类型检查：

~~~bash
npm --prefix weixinChannel run typecheck
~~~

Python 语法检查：

~~~bash
python -m compileall -q lumen_agent
~~~

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python、FastAPI、Pydantic、HTTPX |
| 前端 | Vue 3、TypeScript、Vite、Element Plus |
| 模型协议 | DeepSeek、OpenAI Chat Completions、Responses API |
| 数据 | SQLite、ChromaDB |
| Agent 扩展 | MCP、SKILL.md |
| 文档处理 | MarkItDown |
| 调度 | APScheduler |
| 远程主机 | Paramiko、WebSocket |
| 微信 | Node.js、weixin-agent-sdk |

## 数据与安全

以下目录包含运行数据，不应提交到 Git：

- **lumen_agent/config.json**：API Key、JWT Secret 和系统配置
- **lumen_agent/data/**：SQLite 与 ChromaDB
- **work_space/**：上传文件、记忆、规则和 Skill
- **weixinChannel/data/**：微信登录凭据和内部 API Key
- **log/**：运行日志

部署建议：

- 使用强管理员密码和随机 JWT Secret。
- 通过 HTTPS 访问服务。
- 限制配置文件和持久化目录的系统权限。
- 定期备份配置、数据库、工作区和微信凭据。
- SQLite 与进程内 ChromaDB 适合单个后端实例运行。

## License

本项目采用 MIT License。

- GitHub：https://github.com/renking-W/LumenAgent
- Email：3194676188@qq.com
