 第一层：全局初始化（模块级别）

  settings = get_settings()                                    # 读配置
  repo = SqliteConversationRepository(...)                     # 连 SQLite
  llm = get_model_adapter(settings)                            # 连 LLM

  程序启动时只执行一次，全局复用。

  ---
  第二层：交互循环（async_main）

  ┌─ 启动 ──────────────────────────────────────────┐
  │  init_tools()         ← 注册工具                 │
  │  logging.disable()    ← 关掉后端日志              │
  │  生成新 session_id                               │
  └─────────────────────────────────────────────────┘
                          │
                          ▼
  ┌─ 循环 ──────────────────────────────────────────┐
  │  input("You: ")       ← 等用户输入               │
  │                      │                          │
  │  ├─ 空输入 → 跳过                               │
  │  ├─ /exit  → break                              │
  │  ├─ /new   → 重置 session_id，续               │
  │  └─ 其他   → 交给回复处理                       │
  └─────────────────────────────────────────────────┘

  ---
  第三层：回复处理（事件驱动）

  reply_with_agent(repo, llm, session_id, msg, settings)
           │
           ▼   异步事件流
  ┌──────────────────────────────────────┐
  │ reasoning_content → 显示"思考中..."   │  ← 用 \r 固定在同一行
  │ content           → 覆盖思考行，打印  │  ← 流式输出，end=""
  │ tool_calls        → "── 调用工具 ──" │  ← 另起一行
  │ tool_execution_end→ "── 工具返回 ──" │
  │ done              → 换行收尾         │
  │ error             → "[错误] xxx"     │
  └──────────────────────────────────────┘
           │
           ▼    输出到终端

  状态标记 _thinking 和 _has_prefix 控制前缀输出时机：
  第三层：回复处理（事件驱动）

  reply_with_agent(repo, llm, session_id, msg, settings)
           │
           ▼   异步事件流
  ┌──────────────────────────────────────┐
  │ reasoning_content → 显示"思考中..."   │  ← 用 \r 固定在同一行
  │ content           → 覆盖思考行，打印  │  ← 流式输出，end=""
  │ tool_calls        → "── 调用工具 ──" │  ← 另起一行
  │ tool_execution_end→ "── 工具返回 ──" │
  │ done              → 换行收尾         │
  │ error             → "[错误] xxx"     │
  └──────────────────────────────────────┘
           │
           ▼    输出到终端

  状态标记 _thinking 和 _has_prefix 控制前缀输出时机：
  - 有 reasoning_content → 先显示 "Assistant: 思考中..." → 被 content 覆盖
  - 无 reasoning_content → 直接 print("Assistant: ") 再跟内容
