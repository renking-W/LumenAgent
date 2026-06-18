# 虚拟机模块设计方案

## 背景

基于 SSH（paramiko）实现远程虚拟机管理。用户已有基础 `SshClient` 类和 `VirtualMachineRegistry`。本项目需将其包装为完整、可落地的后端模块。

---

## 1. 核心设计思想

| 维度 | 决策 | 理由 |
|------|------|------|
| **密码存储** | SQLite 明文存储 | 单一用户、本地服务场景，不需引入加密层 |
| **连接模式** | 长连接、连接池管理（不主动断开） | 运维场景需保持常驻，避免反复握手 |
| **Agent 集成** | **暂不集成** | 当前直接使用 API 调用，后需再封装为 Tool |
| **危险命令审批** | 复用现有 `ApprovalRegistry` | 已有完善的审批弹窗、超时拒绝机制 |
| **SSE 流式** | 全走 SSE 输出 | 用户指定 |
| **前端** | 不管 | 用户指定 |
| **日志持久化** | `log/machine_log/{host}.log` | 与项目 `agent.log` 风格一致 |

---

## 2. 数据持久化层

### 2.1 SQLite 表结构

**文件名**：`infrastructure/data_base/sqlite_vm_config.py`

遵循 `SqliteMCPServerRepository` 风格（`aiosqlite`、`row_factory`、`_prepare()` 懒建表）。

```sql
CREATE TABLE IF NOT EXISTS vm_machines (
    vm_id       TEXT PRIMARY KEY,           -- 自定义名称，如 "ubuntu-dev"
    host        TEXT NOT NULL,               -- IP 或域名
    port        INTEGER NOT NULL DEFAULT 22,
    username    TEXT NOT NULL,
    password    TEXT NOT NULL,               -- 明文存储（单一用户场景）
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
```

### 2.2 CRUD 方法

| 方法 | 功能 |
|------|------|
| `create(data)` | 新增记录，自动生成 `vm_id`（`vm-{timestamp}`） |
| `list_all()` | 返回全部记录，按创建时间倒序 |
| `get(vm_id)` | 单条查询 |
| `get_by_host(host)` | 按主机名查 |
| `update(vm_id, data)` | 局部更新（只更新传入字段） |
| `delete(vm_id)` | 删除，返回是否实际删除 |
| `count()` | 统计总数 |

---

## 3. 连接池服务层

### 3.1 状态枚举

```python
class VMConnectionStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
```

### 3.2 核心数据结构

```python
@dataclass
class VMConnection:
    vm_id: str
    config: dict                    # 来自 DB 的完整配置
    client: SshClient | None
    status: VMConnectionStatus
    last_connected_at: str | None
    error_message: str | None
```

### 3.3 VmConnectionService 方法

**文件名**：`application/service/vm_connection_service.py`

| 方法 | 说明 |
|------|------|
| `connect(vm_id)` | 读 DB → 创建 SshClient → 调用 `client.connect()` → 注册到连接池。幂等，已连接直接返回。 |
| `execute(vm_id, command, timeout)` | 调用 `client.execute()`，同时追加写入 `log/machine_log/{host}.log`。若断连自动重连一次。 |
| `disconnect(vm_id)` | 断开 SSH → 从池移除 → **删除 `{host}.log` 日志文件** |
| `disconnect_all()` | 遍历全部断开（供 lifespan shutdown 调用） |
| `get_status(vm_id)` | 返回连接状态 |
| `list_connections()` | 返回全部连接（含状态） |
| `list_with_config()` | 合并 DB 配置 + 连接状态（给前端列表页用） |

### 3.4 日志写入规则

日志追求**终端原生沉浸感**，文件内容直接可读为终端会话实录。

- **前置**：连接建立时自动探测远程 shell 提示符格式（如 `renking@renking:~$`），提取其中的 `{username}@{hostname}` 部分
- **`connect()` 时**：向 `log/machine_log/{host}.log` 写入一条连接建立标记
- **`execute()` 时**：向日志文件写入以下内容：
  ```
  renking@renking:~$ ls -la
  total 40
  drwxr-x--- 4 renking renking 4096 Jun 16 12:52 .
  drwxr-x--- 3 renking renking 4096 Jun 16 12:52 ..
  -rw-r--r-- 1 renking renking  807 Jun 16 12:52 .bashrc
  renking@renking:~$
  ```
  实现方式：
  1. 从连接信息构造提示符：`{username}@{host}:~$ `（若无法探测，兜底使用 `$ `）
  2. 写入 `{prompt}{command}` 作为一行
  3. 写入 `client.execute()` 返回的命令输出（原始内容，不做结构化处理）
  4. 写入换行后的下一个提示符 `{prompt}`
- **`disconnect()` 时**：**删除** `log/machine_log/{host}.log`（断开即清理）

---

## 4. 危险命令审批

### 4.1 危险命令规则

默认匹配模式，可在配置中自定义：

```python
DANGEROUS_PATTERNS = [
    r"\brm\s+-rf\b", r"\bshutdown\b", r"\breboot\b", r"\bpoweroff\b",
    r"\binit\s+0\b", r"\binit\s+6\b", r"\bdd\s+if=", r"\bmkfs\b",
    r"\bfdisk\b", r"\bchmod\s+777\b", r"\b>\s+/dev/sd",
]
```

### 4.2 审批流程

```
用户 POST /v1/vm/{vm_id}/execute → command="rm -rf /tmp"
  → 匹配危险模式
  → 构建虚拟 tool_call：
      tool_call_id = f"vm-exec-{uuid4()}"
      tool_call = {"id": tool_call_id, "name": "vm_execute", "input": {"command": command}}
  → ApprovalRegistry.register(session_id, [tool_call])
  → 挂起，等待前端审批
  → 前端 POST /v1/chat/stream/approve → approve(session_id, tool_call_id, True/False)
  → 批准 → 执行命令；拒绝 → 返回 "命令被拒绝"
```

**复用方式**：直接将 `execute` 请求包装成"虚拟 tool call"，挂到已有的 `ApprovalRegistry` 上，前端已有的审批弹窗无需改动。

---

## 5. API 路由

**文件名**：`api/routers/vm.py`

### 5.1 接口一览

| 方法 | 路径 | 功能 | SSE？ | 需要审批？ |
|------|------|------|-------|-----------|
| `POST` | `/v1/vm/register` | 注册 VM 配置到 DB | ❌ | ❌ |
| `DELETE` | `/v1/vm/{vm_id}` | 从 DB 删除（需先断开） | ❌ | ❌ |
| `PUT` | `/v1/vm/{vm_id}` | 更新 VM 配置 | ❌ | ❌ |
| `GET` | `/v1/vm/list` | 列出所有 VM（配置 + 连接状态） | ❌ | ❌ |
| `POST` | `/v1/vm/{vm_id}/connect` | 建立 SSH 连接 | ❌ | ❌ |
| `POST` | `/v1/vm/{vm_id}/disconnect` | 断开 SSH + 删除日志文件 | ❌ | ❌ |
| `POST` | `/v1/vm/{vm_id}/execute` | **SSE 流式执行命令** | ✅ | ✅ 危险命令 |
| `GET` | `/v1/vm/{vm_id}/status` | 获取 VM 连接状态 | ❌ | ❌ |
| `GET` | `/v1/vm/{vm_id}/log` | 查看该 VM 的日志内容 | ❌ | ❌ |

### 5.2 SSE 流式执行端点

```http
POST /v1/vm/{vm_id}/execute
Content-Type: application/json

{
  "command": "docker ps -a",
  "session_id": "xxx",         // 用于审批传递
  "timeout": 30
}
```

**SSE 响应格式**：
```
data: {"type": "stdout", "content": "CONTAINER ID   IMAGE\n"}
data: {"type": "stdout", "content": "abc123         nginx\n"}
data: {"type": "exit_code", "code": 0}
data: {"type": "done", "message": "命令执行完毕"}
```

等待审批时的 SSE 序列：
```
data: {"type": "approval", "tool_call_id": "vm-exec-xxx", "command": "rm -rf /tmp"}
// ... 前端弹审批窗，用户批准后继续 ...
data: {"type": "stdout", "content": "..."}
data: {"type": "exit_code", "code": 0}
data: {"type": "done"}
```

### 5.3 日志查看接口

**不**复用 `log_service.py` 的解析逻辑（不按 `[timestamp] - LEVEL - message` 正则解析），而是**直接返回终端的原始文本内容**，前端用 `<pre>` 或终端组件原样渲染。

```http
GET /v1/vm/{vm_id}/log?lines=100
```

返回格式：

```json
{
  "vm_id": "ubuntu-dev",
  "host": "192.168.1.100",
  "connected": true,
  "total_lines": 85,
  "lines": [
    "renking@renking:~$ ls -la",
    "total 40",
    "drwxr-x--- 4 renking renking 4096 Jun 16 12:52 .",
    "drwxr-x--- 3 renking renking 4096 Jun 16 12:52 ..",
    "-rw-r--r-- 1 renking renking  807 Jun 16 12:52 .bashrc",
    "renking@renking:~$ docker ps -a",
    "CONTAINER ID   IMAGE     COMMAND",
    "abc123         nginx     \"nginx -g 'daemon off;'\"",
    "renking@renking:~$"
  ]
}
```

每行就是终端里实际出现的文本，前端拿到 `lines` 数组后直接逐行渲染，形成完整的终端会话感。

`lines` 参数控制返回的行数（倒序，最新的在前），支持滚动分页。
```

---

## 6. App Factory 注册

在 `create_app()` 中增加：

```python
from lumen_agent.api.routers import vm as vm_router
application.include_router(vm_router.router)
```

在 `lifespan` 的 shutdown 段中增加：

```python
from lumen_agent.application.service.vm_connection_service import get_vm_connection_service
await get_vm_connection_service().disconnect_all()
```

---

## 7. 配置项（三级体系）

添加到 `config.json` 默认值（可通过 `.env` 覆盖）：

```json
{
  "VM_SSH_TIMEOUT": 60,
  "VM_SSH_BANNER_TIMEOUT": 60,
  "VM_SSH_KEEPALIVE": 40,
  "VM_EXECUTE_TIMEOUT": 30,
  "VM_DANGEROUS_COMMANDS": "rm -rf,shutdown,reboot,poweroff,init 0,init 6,dd if=,mkfs,fdisk,> /dev/sd,chmod 777 /",
  "VM_APPROVAL_MODE": "dangerous"
}
```

---

## 8. 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `infrastructure/data_base/sqlite_vm_config.py` | **新增** | VM 配置表的 SQLite CRUD |
| `application/service/vm_connection_service.py` | **新增** | 连接池管理 + 日志写入 |
| `api/routers/vm.py` | **新增** | 全部 VM 相关的 API 端点 |
| `api/schemas/vm_dtos.py` | **新增** | VM 相关的 Pydantic 请求/响应模型 |
| `api/app_factory.py` | **修改** | 注册 vm_router + lifespan 清理 |
| `config.json` | **修改** | 添加 VM_* 默认配置项 |
| `config_loader.py` | **修改** | 添加 VM_* 默认值到 `_DEFAULT_CONFIG` |

**不修改/删除的现有文件**：

- `infrastructure/virtual_machine/virtual_machine_registry.py` — 已有 `SshClient` 类直接复用，`VirtualMachineRegistry` 被新 `VmConnectionService` 替代。

---

## 9. 实施顺序

| 步骤 | 内容 | 预估 |
|------|------|------|
| 1️⃣ | `sqlite_vm_config.py` — 参照 `SqliteMCPServerRepository` | 🟢 小 |
| 2️⃣ | `vm_dtos.py` — 请求/响应 Pydantic 模型 | 🟢 小 |
| 3️⃣ | `VmConnectionService` — 连接池单例 | 🟡 中 |
| 4️⃣ | 给 `SshClient.execute()` 添加日志写入能力 | 🟢 小 |
| 5️⃣ | `vm.py` router — 增删查/连接/断开/状态/日志查看 | 🟡 中 |
| 6️⃣ | SSE 流式执行端点（含危险命令审批集成） | 🟡 中 |
| 7️⃣ | `config.json` + `config_loader.py` 配置项 | 🟢 极小 |
| 8️⃣ | `app_factory.py` 注册 | 🟢 极小 |
