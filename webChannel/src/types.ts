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
  enabled: boolean
  created_at: string
  updated_at: string
}

export type MCPServerTestResult = {
  status: 'ok' | 'error'
  message?: string
  tools_count?: number
}
