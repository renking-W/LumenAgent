# LumenAgent API 接入文档

本文面向需要通过 HTTP API 接入 LumenAgent 的第三方客户端。API 接入的不是单一大模型 Chat 接口；当请求使用 `mode: "agent"` 时，后端会运行完整的 LumenAgent Agent 链路。

完整 Agent 运行时会同时装配：

- 当前会话历史与自动摘要；
- 工作区中的 `RULE.md` 和 `USER.md`；
- 记忆系统与 `MEMORY.md`、每日记忆文件及记忆检索；
- 内置工具系统与工具审批；
- `work_space/skills/` 下已安装且可用的 SKILL；
- 知识库能力；
- 已启用的 MCP Server 及其工具；
- 服务端配置的模型、思考模式和自定义系统提示词。

因此，第三方调用获得的是与 Web 端 Agent 模式基本一致的能力，而不是简单地将文本转发给模型厂商。

> `POST /v1/chat` 是非流式简单对话接口，不执行完整 Agent 工具循环。需要工具、SKILL、记忆检索、知识库和 MCP 能力时，应使用 `POST /v1/chat/stream`，并保持 `mode` 为 `agent`。

## 1. 基础信息

假设服务部署地址为：

```text
http://your-server:1675
```

后续示例统一使用：

```text
BASE_URL=http://your-server:1675
```

服务检查：

```http
GET /health
```

Swagger 文档：

```text
http://your-server:1675/docs
```

生产环境建议通过 HTTPS 暴露服务，避免 API Key、对话内容和工具参数以明文传输。

## 2. 认证

### 2.1 创建 API Key

管理员可在 Web 管理界面的 API Key 管理入口创建密钥。原始 Key 只在创建成功时展示一次，请立即保存。

首次启动时，系统也可能自动生成默认 API Key，并仅在首次启动日志中打印一次。

### 2.2 请求头

第三方接口使用 Bearer 认证：

```http
Authorization: Bearer lumen_your_api_key
```

JSON 请求还需要：

```http
Content-Type: application/json
```

示例：

```bash
curl "$BASE_URL/v1/chat" \
  -H "Authorization: Bearer $LUMEN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message":"你好"}'
```

### 2.3 API Key 与 JWT 的区别

API Key 和 Web JWT 都使用 `Authorization: Bearer <credential>`，但用途不同：

| 凭证 | 主要用途 | 身份归属 |
|---|---|---|
| API Key | 第三方调用 `/v1/chat*` 兼容接口 | 会话默认归属系统管理员 |
| JWT | Web 登录、ChatRun、会话管理和后台接口 | 归属当前登录用户 |

API Key 不代表一个独立的 Web 用户。不同第三方终端应使用不同的 `session_id` 隔离对话历史，但它们仍共享服务端工作区中的用户资料、记忆、工具、SKILL、知识库和 MCP 配置。

## 3. 完整 Agent 对话

### 3.1 接口

```http
POST /v1/chat/stream
```

响应类型：

```http
Content-Type: text/event-stream
```

服务端通过响应头返回最终会话 ID：

```http
X-Session-Id: <session_id>
```

### 3.2 请求体

```json
{
  "message": "读取项目中的 README.md，并总结主要能力",
  "session_id": "third-party-demo-001",
  "mode": "agent",
  "approval_mode": "dangerous",
  "mcp_server_ids": [],
  "self_system": null,
  "image_urls": null,
  "file_attachments": []
}
```

字段说明：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| `message` | string | 条件必填 | `""` | 用户文本；文字、图片、文件至少提供一种 |
| `session_id` | string/null | 否 | 自动生成 UUID | 复用同一 ID 可延续会话历史 |
| `session_kind` | integer/null | 否 | `0` | 普通第三方对话通常省略；`1` 为内部定时任务会话 |
| `mode` | `simple`/`agent` | 否 | `agent` | `agent` 启用完整工具循环；`simple` 仅执行简单模型对话 |
| `approval_mode` | `none`/`all`/`dangerous` | 否 | `dangerous` | 不审批、全部审批或仅危险工具审批 |
| `mcp_server_ids` | string[] | 否 | `[]` | MCP Server ID；留空时加载全部已启用 MCP Server |
| `self_system` | string/null | 否 | `null` | 本次请求附加的自定义系统提示词 |
| `image_urls` | string[]/null | 否 | `null` | 图片 URL，仅 Agent 模式生效 |
| `file_attachments` | object[] | 否 | `[]` | Agent 可读取的服务端文件元数据 |

`file_attachments` 元素结构：

```json
{
  "name": "report.pdf",
  "path": "/app/work_space/tmp/report.pdf",
  "extension": ".pdf",
  "size": 102400,
  "content_type": "application/pdf",
  "url": "/v1/files/report.pdf"
}
```

其中 `path` 必须是 LumenAgent 服务端或容器内真实可访问的路径。`POST /v1/upload` 属于 JWT 登录接口，第三方 API Key 客户端不能直接依靠该接口上传文件；API Key 调用方需要先通过自己的文件传输链路把文件放到服务端可访问位置。

### 3.3 curl 示例

```bash
export BASE_URL="http://your-server:1675"
export LUMEN_API_KEY="lumen_your_api_key"

curl -N "$BASE_URL/v1/chat/stream" \
  -H "Authorization: Bearer $LUMEN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "检索知识库并告诉我项目的部署方式",
    "session_id": "integration-demo-001",
    "mode": "agent",
    "approval_mode": "dangerous"
  }'
```

`-N` 用于关闭 curl 输出缓冲，使 SSE 内容实时显示。

## 4. SSE 事件

每个业务事件使用以下格式：

```text
data: {"type":"text","data":{"delta":"你好"}}

```

流正常或异常收尾时都会发送：

```text
data: [DONE]

```

事件类型：

| `type` | 关键数据 | 含义 |
|---|---|---|
| `text` | `data.delta` | Assistant 正文增量 |
| `thinking` | `data.delta` | 模型思考内容增量 |
| `tool_calls` | `data.tool_calls` | 模型本轮计划调用的工具列表 |
| `awaiting_approval` | `data.tool_calls` | 工具正在等待人工审批 |
| `approval_result` | `data.tool_call_id`、`data.approved` | 工具审批结果 |
| `tool_use` | `data.tool_call_id`、`data.name`、`data.arguments` | 工具开始执行 |
| `tool_result` | `data.status`、`data.execution_time`、`data.result_preview` | 工具执行结果摘要 |
| `assistant_done` | `{}` | Agent 当前推理轮结束 |
| `error` | `data.message` | 流式执行错误 |

正文事件：

```json
{
  "type": "text",
  "data": {
    "delta": "这是增量正文"
  }
}
```

等待审批事件：

```json
{
  "type": "awaiting_approval",
  "data": {
    "tool_calls": [
      {
        "id": "call_abc123",
        "name": "knowledge_insert",
        "input": {
          "text": "待写入知识库的内容"
        }
      }
    ]
  }
}
```

工具结果事件只包含结果预览，完整工具结果由后端会话链路持久化并继续提供给模型使用。

## 5. 工具审批

当收到 `awaiting_approval` 时，客户端应读取其中的工具调用 ID，并提交审批结果。

### 5.1 接口

```http
POST /v1/chat/stream/approve
```

请求：

```json
{
  "session_id": "integration-demo-001",
  "approvals": {
    "call_abc123": true,
    "call_def456": false
  }
}
```

响应：

```json
{
  "status": "ok",
  "updated": 2
}
```

`true` 表示批准，`false` 表示拒绝。`updated: 0` 通常表示该会话或工具调用已经不再等待审批，或者提交了错误的 `tool_call_id`。

curl 示例：

```bash
curl "$BASE_URL/v1/chat/stream/approve" \
  -H "Authorization: Bearer $LUMEN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "integration-demo-001",
    "approvals": {"call_abc123": true}
  }'
```

审批请求必须使用另一个 HTTP 连接发送，原 SSE 连接需要继续保持，以接收工具执行和后续模型输出。

## 6. 主动中断

```http
POST /v1/chat/stream/interrupt
```

请求：

```json
{
  "session_id": "integration-demo-001"
}
```

curl 示例：

```bash
curl "$BASE_URL/v1/chat/stream/interrupt" \
  -H "Authorization: Bearer $LUMEN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"integration-demo-001"}'
```

成功响应：

```json
{
  "status": "interrupted",
  "session_id": "integration-demo-001"
}
```

没有活跃流时返回 `404`。

## 7. 非流式简单对话

```http
POST /v1/chat
```

该接口等待本轮模型回复完成后一次性返回 JSON，适合不需要工具循环的简单问答。

请求：

```json
{
  "message": "你好",
  "session_id": "simple-demo-001"
}
```

响应：

```json
{
  "content": [
    {
      "type": "text",
      "text": "你好，有什么可以帮助你？"
    }
  ],
  "session_id": "simple-demo-001"
}
```

> 即使请求体传入 `mode: "agent"`，当前 `/v1/chat` 实现仍走非 Agent 的单轮回复逻辑。完整 Agent 接入请使用 `/v1/chat/stream`。

## 8. Python 完整示例

以下示例使用 `httpx` 读取 SSE，并自动批准演示中的所有待审批工具。生产环境应把审批决定交给真实用户或自己的安全策略。

```python
import json
import os

import httpx


BASE_URL = os.environ.get("LUMEN_BASE_URL", "http://127.0.0.1:1675")
API_KEY = os.environ["LUMEN_API_KEY"]
SESSION_ID = "python-integration-demo"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}


def submit_approval(tool_call_id: str, approved: bool) -> None:
    """通过独立请求提交工具审批，不关闭正在读取的 SSE 连接。"""
    response = httpx.post(
        f"{BASE_URL}/v1/chat/stream/approve",
        headers=HEADERS,
        json={
            "session_id": SESSION_ID,
            "approvals": {tool_call_id: approved},
        },
        timeout=30,
    )
    response.raise_for_status()


request_body = {
    "message": "检索知识库并总结 LumenAgent 的主要能力",
    "session_id": SESSION_ID,
    "mode": "agent",
    "approval_mode": "dangerous",
}

with httpx.stream(
    "POST",
    f"{BASE_URL}/v1/chat/stream",
    headers=HEADERS,
    json=request_body,
    timeout=None,
) as response:
    response.raise_for_status()
    print("session_id:", response.headers.get("X-Session-Id"))

    for line in response.iter_lines():
        if not line.startswith("data: "):
            continue
        raw_data = line[6:]
        if raw_data == "[DONE]":
            break

        event = json.loads(raw_data)
        event_type = event.get("type")
        data = event.get("data", {})

        if event_type == "text":
            print(data.get("delta", ""), end="", flush=True)
        elif event_type == "thinking":
            print("[thinking]", data.get("delta", ""))
        elif event_type == "awaiting_approval":
            for tool_call in data.get("tool_calls", []):
                submit_approval(tool_call["id"], approved=True)
        elif event_type == "error":
            raise RuntimeError(data.get("message", "Agent stream failed"))
```

## 9. 会话与上下文

### 9.1 延续会话

首次请求可以省略 `session_id`，并从 `X-Session-Id` 响应头读取后端生成的 ID。后续请求继续传入该 ID，即可携带历史消息、摘要和工具结果。

```text
第一次请求：不传 session_id
响应头：X-Session-Id: 8b8d...
第二次请求：session_id = 8b8d...
```

建议第三方系统持久化以下映射：

```text
第三方用户/对话 ID -> LumenAgent session_id
```

不要让互不相关的终端共享同一个 `session_id`，否则它们会共享同一段对话历史。

### 9.2 API Key 接入的共享能力

API Key 调用会使用服务器当前完整 Agent 配置，包括：

- `USER.md` 中的用户资料；
- `RULE.md` 中的行为规则和文件处理规则；
- `MEMORY.md` 与每日记忆；
- 已入库的知识文档；
- 已注册的内置工具；
- 已安装且环境检查通过的 SKILL；
- 已启用的 MCP Server；
- 当前 LLM、Embedding 和 Agent 参数。

这些资源属于当前 LumenAgent 实例，不会按 API Key 自动隔离。向不可信第三方发放 API Key 前，应检查工作区内容、工具权限、MCP 权限和审批策略。

## 10. 错误处理

| HTTP 状态码 | 常见原因 | 处理建议 |
|---:|---|---|
| `401` | 缺少、无效或已停用的 API Key | 检查 `Authorization: Bearer ...` |
| `404` | 中断的会话当前没有活跃流 | 确认 `session_id` 和生成状态 |
| `422` | 请求字段类型错误，或文字、图片、文件全部为空 | 检查请求 JSON 和字段约束 |
| `503` | 未配置 `LLM_API_KEY`，或认证存储暂时不可用 | 检查服务端配置和日志 |
| `5xx` | 模型、工具、数据库或外部 MCP 调用异常 | 读取响应详情和服务端 `agent.log` |

SSE 连接建立后发生的业务异常通常不会再改变 HTTP 状态码，而是通过 `error` 事件发送：

```json
{
  "type": "error",
  "data": {
    "message": "具体错误信息"
  }
}
```

客户端应同时处理 HTTP 非 2xx、SSE `error` 事件、网络断开和 `[DONE]`。

## 11. Web/JWT 内部接口

以下接口主要供内置 Web UI 使用，需要登录 JWT，不属于 API Key 第三方对话入口：

| 接口组 | 用途 |
|---|---|
| `/v1/auth/*` | 登录、Token 刷新和当前用户 |
| `/v1/chat/runs*` | 后台 ChatRun、断线续订和事件补放 |
| `/v1/sessions*` | 用户会话查询与管理 |
| `/v1/upload` | Web 用户文件上传 |
| `/v1/knowledge*` | 知识库管理 |
| `/v1/mcp/*` | MCP Server 与工具管理 |
| `/v1/scheduler/*` | 定时任务管理 |
| `/v1/admin/*` | 管理员后台 |

这些接口的实时结构和完整字段可通过部署实例的 `/docs` 查看。
