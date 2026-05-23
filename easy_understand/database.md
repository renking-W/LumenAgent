# 数据库模块

## 1. 核心实现

| 文件 | 作用 |
|---|---|
| `lumen_agent/infrastructure/sqlite_conversation.py` | SQLite 具体实现，所有 CRUD |
| `lumen_agent/domain/ports.py` | 仓储接口（抽象类），定义 `ConversationRepositoryPort` |
| `lumen_agent/data/conversations.db` | SQLite 数据库文件 |

## 2. 配置

| 文件 | 作用 |
|---|---|
| `lumen_agent/config.py` | 定义 `conversation_db_path` 配置项（默认 `data/conversations.db`） |

## 3. 使用数据库的业务层

| 文件 | 作用 |
|---|---|
| `lumen_agent/application/chat_service.py` | 对话编排：落库用户/助手消息、触发摘要 |
| `lumen_agent/application/summary_service.py` | 摘要压缩：读写历史消息 |
| `lumen_agent/application/context_assembly.py` | 上下文组装：读取历史构建 prompt |
| `lumen_agent/application/chat_in_cli.py` | CLI 入口：初始化 repo |

## 4. API 路由（通过 DI 间接使用）

| 文件 | 作用 |
|---|---|
| `lumen_agent/api/dependency.py` | 注入 `SqliteConversationRepository` 实例 |
| `lumen_agent/api/routers/chat.py` | 对话路由 |
| `lumen_agent/api/routers/sessions.py` | 会话管理路由 |

## 调用链路

```
chat_service.py / summary_service.py / context_assembly.py
        ↓
domain/ports.py  ← 抽象的接口定义
        ↓
infrastructure/sqlite_conversation.py  ← 具体的 SQLite 实现
        ↓
lumen_agent/data/conversations.db  ← 磁盘上的数据库文件
```