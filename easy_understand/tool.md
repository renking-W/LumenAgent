# 工具模块

## 1. 工具基础设施（核心）

| 文件 | 作用 |
|---|---|
| `lumen_agent/agent/tools/base.py` | `BaseTool` 抽象基类、`ToolResult` 数据类 |
| `lumen_agent/agent/tools/registry.py` | `ToolRegistry` 注册表，管理工具的注册与创建 |

## 2. 具体工具实现（5 个）

| 文件 | 工具名 | 作用 |
|---|---|---|
| `lumen_agent/agent/tools/read.py` | `read` | 读取文件 |
| `lumen_agent/agent/tools/write.py` | `write` | 写入文件 |
| `lumen_agent/agent/tools/bash.py` | `bash` | 执行 shell 命令 |
| `lumen_agent/agent/tools/web_search.py` | `web_search` | 网络搜索 |
| `lumen_agent/agent/tools/web_fetch.py` | `web_fetch` | 抓取网页内容 |

## 3. 工具包入口

| 文件 | 作用 |
|---|---|
| `lumen_agent/agent/tools/__init__.py` | 统一导出入口，import 时自动注册所有工具 |

## 4. 使用工具的调用方

| 文件 | 作用 |
|---|---|
| `lumen_agent/agent/agent.py` | `AgentStreamExecutor` — 工具循环执行器，调度 LLM ↔ 工具循环 |
| `lumen_agent/agent/prompts/builder.py` | `build_system_prompt()` — 把工具列表序列化进 system prompt |
| `lumen_agent/application/chat_service.py` | `reply_with_agent()` — 编排层，构造工具列表传给 agent |
| `lumen_agent/api/routers/tools.py` | API 路由 — 暴露工具列表给前端 |

## 调用链路

```
chat_service.py          ← 发起 agent 模式对话
        ↓
agent.py                 ← AgentStreamExecutor: LLM ↔ 工具循环
        ↓
builder.py               ← 构建含工具描述的 system prompt
        ↓
tools/__init__.py        ← 触发注册
        ↓
tools/registry.py        ← 管理所有工具类
        ↓
tools/base.py            ← 基类
        ↓
read / write / bash / web_search / web_fetch  ← 具体实现
```