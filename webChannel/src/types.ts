export type ToolInfo = { name: string; description: string; parameters: unknown }

export type SkillInfo = {
  name: string
  description: string
  path: string
  available: boolean
  emoji: string
  requires_env?: string[]
  primary_env?: string | null
  missing_envs?: string[]
}

export type ChatBlock = {
  id: string
  kind: string
  title: string
  content: string
  expanded: boolean
}

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  roleLabel: string
  time: string
  blocks: ChatBlock[]
  status?: number      // 1=正常, 0=中断/异常（仅历史消息有此字段）
  seq?: number         // 游标分页 seq，仅历史消息有此字段
}

export type MemoryFileItem = {
  file_name: string
  content: string
  type: 'long_term' | 'daily'
}

export type MCPServerInfo = {
  id: string
  name: string
  url: string
  api_key: string | null
  transport?: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export type MCPStdioServerInfo = {
  id: string
  name: string
  command: string
  args: string[]
  env: Record<string, string>
  cwd: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export type MCPUnifiedServer =
  | (MCPServerInfo & { kind: 'http' })
  | (MCPStdioServerInfo & { kind: 'stdio' })

export type MCPServerTestResult = {
  status: 'ok' | 'error'
  message?: string
  tools_count?: number
}

// ── 知识库 ──────────────────────────────────────────
export type KnowledgeDocumentSummary = {
  knowledge_id: string
  file_name: string
  source_name: string
  source_path: string | null
  status: string
  chunk_count: number
  created_at: string
  updated_at: string
}

export type KnowledgeChunkDetail = {
  chunk_index: number
  start_char: number
  end_char: number
  content: string
  content_preview: string
  created_at: string
  file_name: string
}

export type KnowledgeDocumentDetail = KnowledgeDocumentSummary & {
  chunks: KnowledgeChunkDetail[]
}

export type KnowledgeIngestResponse = {
  knowledge_id: string
  source_name: string
  source_path: string | null
  chunks_added: number
  collection_name: string
}

export type KnowledgeSearchRequest = {
  query: string
  top_k?: number
  similarity_threshold?: number
}

export type KnowledgeSearchChunk = {
  text: string
  score: number
  distance: number
  metadata: Record<string, unknown>
}

export type KnowledgeSearchResponse = {
  query: string
  collection_name: string
  top_k: number
  similarity_threshold: number
  chunks: KnowledgeSearchChunk[]
}

// ── 定时任务 ──────────────────────────────────────────
export type SchedulerJob = {
  job_id: string
  name: string
  prompt: string
  trigger_type: 'cron' | 'interval' | 'date'
  trigger_expr: string
  timezone?: string
  enabled: boolean
  created_by: string
  created_at: string
  updated_at?: string
  next_run_time?: string | null
  pending?: boolean
}

export type SchedulerJobListResponse = {
  total: number
  jobs: SchedulerJob[]
}

export type SchedulerCreateRequest = {
  name: string
  prompt: string
  trigger_type: string
  trigger_expr: string
  timezone?: string
}

export type SchedulerCreateResponse = {
  job_id: string
  name: string
  trigger_type: string
  trigger_expr: string
  message: string
}

export type SchedulerExecution = {
  id: number
  task_id: string
  session_id: string
  status: string
  output: string
  error_message: string
  triggered_at: string
  finished_at: string
}

export type SchedulerExecutionResponse = {
  task_id: string
  total: number
  executions: SchedulerExecution[]
}

export type SchedulerHealthResponse = {
  running: boolean
  jobs: unknown[]
}

// ── API Key ──────────────────────────────────────────
export type ApiKeyItem = {
  id: string
  name: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export type ApiKeyCreatedResponse = ApiKeyItem & {
  key: string
}

export type ApiKeyListResponse = {
  total: number
  keys: ApiKeyItem[]
}

// ── 系统配置 ──────────────────────────────────────────
export type ConfigItem = {
  key: string
  value: unknown
  category: 'basic' | 'advanced'
}

export type ConfigListResponse = {
  basic: ConfigItem[]
  advanced: ConfigItem[]
}

export type UpdateConfigResponse = {
  status: string
  key: string
  value: string
  source: string
  note: string
}

// ── 虚拟机管理 ──────────────────────────────────────
export type VMStatus = 'disconnected' | 'connecting' | 'connected' | 'error'

export type VMListResponseItem = {
  vm_id: string
  host: string
  port: number
  username: string
  description: string
  status: VMStatus
  last_connected_at: string | null
  error_message: string | null
}

export type VMRegisterRequest = {
  vm_id: string
  host: string
  port: number
  username: string
  password: string
  description?: string
}

export type VMUpdateRequest = {
  host?: string
  port?: number
  username?: string
  password?: string
  description?: string
}

export type VMExecuteRequest = {
  command: string
  session_id?: string
  timeout?: number
}

export type VMLogResponse = {
  vm_id: string
  host: string
  connected: boolean
  total_lines: number
  lines: string[]
}

// ── VM WebSocket 事件 ──────────────────────────────────────────
export type VMWebSocketEvent = {
  type: 'vm_event'
  subtype: 'command_start' | 'output' | 'exit_code' | 'error' | 'done' | 'connect' | 'disconnect' | 'connecting'
  vm_id: string
  data: unknown
  source?: string
  timestamp: string
}
