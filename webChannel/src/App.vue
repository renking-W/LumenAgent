<template>
  <el-container class="shell">
    <!-- ======== 移动端遮罩 ======== -->
    <div
      v-if="sidebarVisible"
      class="sidebar-overlay"
      @click="sidebarVisible = false"
    ></div>

    <!-- ======== 左侧栏 ======== -->
    <el-aside width="250px" class="sidebar" :class="{ 'sidebar--mobile': sidebarVisible, 'sidebar--collapsed': sidebarCollapsed }">
      <div class="brand">
        <div class="brand-mark" @click="sidebarCollapsed = !sidebarCollapsed" :title="sidebarCollapsed ? '展开侧栏' : '收起侧栏'">
          <img class="brand-mark-img" src="/logo.svg" alt="LumenAgent" />
        </div>
        <div v-if="!sidebarCollapsed" class="brand-text">
          <div class="brand-title">LumenAgent</div>
          <div class="brand-subtitle">AI Agent 管理控制台</div>
        </div>
      </div>

      <nav class="nav">
        <!-- ── 核心功能 ── -->
        <div v-if="!sidebarCollapsed" class="nav-section-label">核心</div>
        <button
          class="nav-item"
          :class="{ active: activeView === 'chat' }"
          @click="activeView = 'chat'"
        >
          <span class="nav-icon">💬</span>
          <span v-if="!sidebarCollapsed" class="nav-text">
            <span class="nav-title">对话</span>
            <span class="nav-desc">实时流式聊天</span>
          </span>
        </button>
        <button
          class="nav-item"
          :class="{ active: activeView === 'tools' }"
          @click="activeView = 'tools'"
        >
          <span class="nav-icon">🛠️</span>
          <span v-if="!sidebarCollapsed" class="nav-text">
            <span class="nav-title">工具</span>
            <span class="nav-desc">单独展示所有 Tool</span>
          </span>
        </button>
        <button
          class="nav-item"
          :class="{ active: activeView === 'skills' }"
          @click="activeView = 'skills'"
        >
          <span class="nav-icon">🎯</span>
          <span v-if="!sidebarCollapsed" class="nav-text">
            <span class="nav-title">技能</span>
            <span class="nav-desc">单独展示所有 Skill</span>
          </span>
        </button>
        <button
          class="nav-item"
          :class="{ active: activeView === 'memories' }"
          @click="activeView = 'memories'"
        >
          <span class="nav-icon">🧠</span>
          <span v-if="!sidebarCollapsed" class="nav-text">
            <span class="nav-title">记忆</span>
            <span class="nav-desc">浏览所有记忆文件</span>
          </span>
        </button>

        <!-- ── 扩展管理 ── -->
        <div v-if="!sidebarCollapsed" class="nav-section-separator"></div>
        <div v-if="!sidebarCollapsed" class="nav-section-label">扩展</div>
        <button
          class="nav-item"
          :class="{ active: activeView === 'mcp' }"
          @click="activeView = 'mcp'"
        >
          <span class="nav-icon">🔌</span>
          <span v-if="!sidebarCollapsed" class="nav-text">
            <span class="nav-title">MCP</span>
            <span class="nav-desc">管理 MCP Server 配置</span>
          </span>
        </button>
        <button
          class="nav-item"
          :class="{ active: activeView === 'knowledge' }"
          @click="activeView = 'knowledge'"
        >
          <span class="nav-icon">📚</span>
          <span v-if="!sidebarCollapsed" class="nav-text">
            <span class="nav-title">知识库</span>
            <span class="nav-desc">管理知识文档与检索</span>
          </span>
        </button>
        <button
          class="nav-item"
          :class="{ active: activeView === 'scheduler' }"
          @click="activeView = 'scheduler'"
        >
          <span class="nav-icon">⏰</span>
          <span v-if="!sidebarCollapsed" class="nav-text">
            <span class="nav-title">定时任务</span>
            <span class="nav-desc">管理 AI 定时调度任务</span>
          </span>
        </button>
        <button
          class="nav-item"
          :class="{ active: activeView === 'logs' }"
          @click="activeView = 'logs'"
        >
          <span class="nav-icon">📋</span>
          <span v-if="!sidebarCollapsed" class="nav-text">
            <span class="nav-title">日志</span>
            <span class="nav-desc">系统日志实时监控</span>
          </span>
        </button>
      </nav>

      <!-- ── 侧栏底部信息 ── -->
      <div v-if="!sidebarCollapsed" class="sidebar-footer">
        <span class="sidebar-footer-version">LumenAgent v0.0.1</span>
      </div>

    </el-aside>

    <!-- ======== 右侧：顶栏 + 主体 + 底部输入 ======== -->
    <el-container direction="vertical" class="right-area">
      <el-header height="auto" class="topbar-wrapper">
        <button class="hamburger" @click="sidebarVisible = !sidebarVisible" title="切换菜单">
          <span class="hamburger-bar"></span>
          <span class="hamburger-bar"></span>
          <span class="hamburger-bar"></span>
        </button>
        <AppTopbar
          :active-view="activeView"
          :use-agent-mode="useAgentMode"
          @update:use-agent-mode="useAgentMode = $event"
          @scroll-to-bottom="scrollToBottom"
          @refresh="refreshCapabilities"
          @open-api-keys="apiKeyDialogVisible = true"
        />
      </el-header>

      <el-main ref="mainContent" class="main-content" @scroll="onMainScroll">
        <ChatView
          v-if="activeView === 'chat'"
          ref="chatViewRef"
          :messages="messages"
          :active-session-id="activeSessionId"
          :streaming-message-id="streamingMessageId"
          :is-near-bottom="isNearBottom"
          :loading-more="loadingMore"
          :has-more="hasMore"
          @select-session="loadSessionMessages"
          @scroll-to-bottom="scrollToBottom"
          @delete-session="onDeleteSession"
          @new-session="resetConversation"
          @load-more="loadMoreMessages"
          @retry="handleRetry"
        />
        <ToolView    v-else-if="activeView === 'tools'"     :tools="tools" :connected="connected" />
        <SkillView   v-else-if="activeView === 'skills'"   :skills="skills" />
        <MemoryView  v-else-if="activeView === 'memories'" :memories="memories" />
        <MCPServerView v-else-if="activeView === 'mcp'" />
        <KnowledgeView v-else-if="activeView === 'knowledge'" />
        <SchedulerView v-else-if="activeView === 'scheduler'" />
        <LogView v-else-if="activeView === 'logs'" />
      </el-main>

      <el-footer v-if="activeView === 'chat'" height="auto" class="composer-wrapper">
        <div class="composer-mcp-bar">
          <MCPServerSelector
            v-if="useAgentMode"
            :selected-ids="selectedMcpServerIds"
            :disabled="sending"
            @update:selected-ids="selectedMcpServerIds = $event"
          />
        </div>
        <AppComposer
          :prompt="prompt"
          :sending="sending"
          :use-agent-mode="useAgentMode"
          :status-text="statusText"
          @update:prompt="prompt = $event"
          @send="sendMessage"
          @interrupt="interruptChat"
        />
      </el-footer>
    </el-container>

    <!-- ======== API Key 管理弹窗 ======== -->
    <ApiKeyManager v-model="apiKeyDialogVisible" />
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch, nextTick } from 'vue'
import type { ToolInfo, SkillInfo, MemoryFileItem, ChatBlock, ChatMessage } from './types'
import AppTopbar from './components/AppTopbar.vue'
import ChatView from './components/ChatView.vue'
import ToolView from './components/ToolView.vue'
import SkillView from './components/SkillView.vue'
import MemoryView from './components/MemoryView.vue'
import MCPServerView from './components/MCPServerView.vue'
import MCPServerSelector from './components/MCPServerSelector.vue'
import KnowledgeView from './components/KnowledgeView.vue'
import SchedulerView from './components/SchedulerView.vue'
import LogView from './components/LogView.vue'
import AppComposer from './components/AppComposer.vue'
import ApiKeyManager from './components/ApiKeyManager.vue'

// ── state ──────────────────────────────────────────
const sidebarVisible = ref(false)
const sidebarCollapsed = ref(false)
const activeView = ref<'chat' | 'tools' | 'skills' | 'memories' | 'mcp' | 'knowledge' | 'scheduler' | 'logs'>('chat')
const connected = ref(false)
const sending = ref(false)
const useAgentMode = ref(true)
const prompt = ref('')
const lastUserPrompt = ref('')
const activeSessionId = ref('')
const statusText = ref('等待输入')
const tools = ref<ToolInfo[]>([])
const skills = ref<SkillInfo[]>([])
const memories = ref<MemoryFileItem[]>([])
const mainContent = ref<HTMLElement | null>(null)
const chatViewRef = ref<InstanceType<typeof ChatView> | null>(null)
const abortController = ref<AbortController | null>(null)

const selectedMcpServerIds = ref<string[]>([])
const apiKeyDialogVisible = ref(false)

const messages = reactive<ChatMessage[]>([])

// ── 游标分页 ──────────────────────────────────────
const beforeSeq = ref<number | undefined>(undefined)
const loadingMore = ref(false)
const hasMore = ref(true)

// ── 流式过程中独立维护的分组列表（中断时从此读取，不依赖 messages 的 blocks） ──
const pendingTexts = ref<ChatBlock[]>([])
const pendingReasonings = ref<ChatBlock[]>([])
const pendingToolUses = ref<ChatBlock[]>([])
const pendingToolResults = ref<ChatBlock[]>([])
const pendingErrors = ref<ChatBlock[]>([])

const clearPendingBlocks = () => {
  pendingTexts.value = []
  pendingReasonings.value = []
  pendingToolUses.value = []
  pendingToolResults.value = []
  pendingErrors.value = []
}

const pushPendingBlock = (block: ChatBlock) => {
  switch (block.kind) {
    case 'text': pendingTexts.value.push(block); break
    case 'reasoning': pendingReasonings.value.push(block); break
    case 'tool_use': pendingToolUses.value.push(block); break
    case 'tool_result': pendingToolResults.value.push(block); break
    case 'error': pendingErrors.value.push(block); break
  }
}

// ── 预置消息：刚打开时的空状态引导 ──
// 故意留空，由 ChatView 的空状态组件展示

// ── 智能滚动 ──────────────────────────────────────
const SCROLL_THRESHOLD = 180
const isNearBottom = ref(true)

const getMainEl = (): HTMLElement | null =>
  (mainContent.value as any)?.$el ?? mainContent.value

const onMainScroll = () => {
  const el = getMainEl()
  if (!el) return
  const diff = el.scrollHeight - el.scrollTop - el.clientHeight
  isNearBottom.value = diff < SCROLL_THRESHOLD
}

const scrollToBottom = () => {
  chatViewRef.value?.scrollPaneToBottom()
  isNearBottom.value = true
}

// 当消息列表变化且用户靠近底部时，自动滚下去
watch(
  () => messages.map((m) => m.blocks.length).join(','),
  () => {
    if (isNearBottom.value) {
      chatViewRef.value?.scrollPaneToBottom()
      isNearBottom.value = true
    }
  }
)

// ── 流式状态（用于光标） ───────────────────────────
const streamingMessageId = computed(() => {
  if (!sending.value || messages.length === 0) return ''
  const last = messages[messages.length - 1]
  return last.role === 'assistant' ? last.id : ''
})

// ── helpers ────────────────────────────────────────
const pretty = (value: unknown) => JSON.stringify(value, null, 2)
const nowStamp = () => new Date().toLocaleTimeString('zh-CN', { hour12: false })

/** 总是创建新块（不做内容合并），适用于 tool_use / tool_result 等独立块 */
const pushBlock = (kind: string, title: string, content: string, expanded = true) => {
  const msg = getOrCreateAssistant()
  const block: ChatBlock = { id: crypto.randomUUID(), kind, title, content, expanded }
  msg.blocks.push(block)
  return block
}

const addMessage = (role: 'user' | 'assistant') => {
  const msg: ChatMessage = {
    id: crypto.randomUUID(),
    role,
    roleLabel: role === 'user' ? 'User' : 'Assistant',
    time: nowStamp(),
    blocks: [],
  }
  messages.push(msg)
  return msg
}

const getOrCreateAssistant = () => {
  let msg = messages[messages.length - 1]
  if (!msg || msg.role !== 'assistant') msg = addMessage('assistant')
  return msg
}

const appendBlock = (kind: string, title: string, content: string, expanded = true) => {
  const msg = getOrCreateAssistant()
  const existing = msg.blocks[msg.blocks.length - 1]
  if (existing && existing.kind === kind) {
    existing.content += content
    return existing
  }
  const block: ChatBlock = { id: crypto.randomUUID(), kind, title, content, expanded }
  msg.blocks.push(block)
  return block
}

// ── actions ────────────────────────────────────────
/** 如果当前正在流式输出，中断连接并通知后端 */
const interruptStreamIfActive = async () => {
  if (!sending.value || !activeSessionId.value) return
  abortController.value?.abort()
  try {
    await fetch('/v1/chat/stream/interrupt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: activeSessionId.value }),
    })
  } catch { /* ignore */ }
  sending.value = false
  abortController.value = null
  clearPendingBlocks()
}

const refreshCapabilities = async () => {
  let ok = true

  try {
    const toolRes = await fetch('/v1/tools')
    if (toolRes.ok) tools.value = await toolRes.json()
    else ok = false
  } catch { ok = false }

  try {
    const skillRes = await fetch('/v1/skills')
    if (skillRes.ok) skills.value = await skillRes.json()
    else ok = false
  } catch { ok = false }

  try {
    const memRes = await fetch('/v1/memories')
    if (memRes.ok) {
      const data = await memRes.json()
      if (Array.isArray(data)) memories.value = data
    } else ok = false
  } catch { ok = false }

  connected.value = ok
}

const resetConversation = async () => {
  await interruptStreamIfActive()
  messages.splice(0)
  activeSessionId.value = ''
  beforeSeq.value = undefined
  hasMore.value = true
  statusText.value = '已重置为新会话'
}

const onDeleteSession = async (sessionId: string) => {
  if (activeSessionId.value === sessionId) {
    await interruptStreamIfActive()
    messages.splice(0)
    activeSessionId.value = ''
    beforeSeq.value = undefined
    hasMore.value = true
    statusText.value = '会话已删除'
  }
}

// ── 分页辅助 ──────────────────────────────────────
type CB = { type: string; text?: string; thinking?: string; name?: string; input?: unknown; content?: string; is_error?: boolean; id?: string; tool_use_id?: string }
interface StoredMsg { seq: number; role: string; content: CB[]; created_at: string; updated_at: string; status: number }

const formatStoredTime = (iso: string) => {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const cbToBlock = (cb: CB): ChatBlock => {
  if (cb.type === 'thinking') return { id: crypto.randomUUID(), kind: 'reasoning', title: '💭 思考', content: cb.thinking ?? '', expanded: false }
  if (cb.type === 'tool_use') return { id: crypto.randomUUID(), kind: 'tool_use', title: cb.name || '工具调用', content: pretty(cb.input ?? ''), expanded: false }
  if (cb.type === 'tool_result') return { id: crypto.randomUUID(), kind: 'tool_result', title: `工具结果${cb.name ? ': ' + cb.name : ''}`, content: cb.content ?? pretty(cb.input ?? ''), expanded: false }
  return { id: crypto.randomUUID(), kind: 'text', title: '正文', content: cb.text ?? '', expanded: false }
}

/**
 * 将后端原始 StoredMessage 列表转换成 ChatMessage 数组。
 * tool_result 已嵌入 assistant 消息内部，每条 StoredMessage 直接映射为一条 ChatMessage。
 */
function parseStoredMessages(stored: StoredMsg[]): ChatMessage[] {
  const result: ChatMessage[] = []
  for (const sm of stored) {
    result.push({
      id: crypto.randomUUID(),
      role: sm.role as 'user' | 'assistant',
      roleLabel: sm.role === 'user' ? 'User' : 'Assistant',
      time: formatStoredTime(sm.created_at),
      blocks: sm.content.map(cb => cbToBlock(cb)),
      status: sm.status,
      seq: sm.seq,
    })
  }
  return result
}

const loadSessionMessages = async (sessionId: string) => {
  // 如果正在流式输出当前会话，先中断
  await interruptStreamIfActive()

  try {
    const res = await fetch(`/v1/sessions/${sessionId}/messages?limit=20`)
    if (!res.ok) return
    let stored: StoredMsg[] = await res.json()
    activeSessionId.value = sessionId
    beforeSeq.value = undefined
    hasMore.value = stored.length === 20
    loadingMore.value = false

    // 定时任务会话：隐藏第一条用户消息（seq=0，调度器自动注入的 prompt）
    const isScheduled = sessionId.startsWith('__scheduled__')
    if (isScheduled && stored.length > 0) {
      stored = stored.filter((s) => s.seq !== 0)
    }

    const parsed = parseStoredMessages(stored)
    if (parsed.length > 0) {
      // min seq 作为下次分页的 before 游标
      beforeSeq.value = Math.min(...stored.map((s) => s.seq))
    }

    messages.splice(0, messages.length, ...parsed)
    statusText.value = `已加载会话 (${parsed.length} 条消息)`
    await nextTick()
    chatViewRef.value?.scrollPaneToBottom()
  } catch {
    statusText.value = '加载会话失败'
  }
}

const loadMoreMessages = async () => {
  if (loadingMore.value || !beforeSeq.value || !activeSessionId.value) return
  loadingMore.value = true
  try {
    const res = await fetch(`/v1/sessions/${activeSessionId.value}/messages?limit=20&before=${beforeSeq.value}`)
    if (!res.ok) return
    const stored: StoredMsg[] = await res.json()
    const parsed = parseStoredMessages(stored)
    if (parsed.length > 0) {
      beforeSeq.value = Math.min(...stored.map((s) => s.seq))
      // prepend 到消息列表前端
      messages.splice(0, 0, ...parsed)
      hasMore.value = stored.length === 20
    } else {
      hasMore.value = false
    }
    statusText.value = `共 ${messages.length} 条消息`
    await nextTick()
    chatViewRef.value?.restoreScrollAfterPrepend()
  } finally {
    loadingMore.value = false
  }
}

const consumeEvent = (event: { type: string; data?: any }) => {
  switch (event.type) {
    case 'message_update':
      appendBlock('text', '正文', event.data?.delta ?? '')
      break
    case 'reasoning_update':
      appendBlock('reasoning', '💭 思考', event.data?.delta ?? '', false)
      break
    case 'tool_calls': {
      // tool_calls 仅用于通知，实际的 tool_use 块由 tool_execution_start 按序创建
      // 这样与历史消息的存储格式一致：每个 tool_use 自带 input 参数
      break
    }
    case 'tool_execution_start': {
      // 创建独立的 tool_use 块，存储完整工具调用信息供中断时使用
      const data = event.data ?? {}
      const toolCallId: string = data.tool_call_id ?? ''
      const toolName: string = data.name ?? '工具'
      const args: Record<string, unknown> = data.arguments ?? {}
      // content 格式为 {id, name, input}，与历史消息的 tool_use 格式一致，
      // 这样 interruptChat 也能正确解析回 tool_use 条目
      const toolCall = { id: toolCallId, name: toolName, input: args }
      pushBlock('tool_use', `⏳ ${toolName}`, pretty(toolCall), false)
      break
    }
    case 'tool_execution_end': {
      // 清除上一个 tool_use 块的 ⏳ 标记
      const lastMsg = messages[messages.length - 1]
      if (lastMsg && lastMsg.role === 'assistant') {
        for (let bi = lastMsg.blocks.length - 1; bi >= 0; bi--) {
          const block = lastMsg.blocks[bi]
          if (block.kind === 'tool_use') {
            block.title = block.title.replace(/^⏳\s*/, '')
            break
          }
        }
      }
      // 创建独立的 tool_result 块（与历史消息的 cb.content 格式一致）
      const data = event.data ?? {}
      pushBlock('tool_result', `工具结果: ${data.name ?? '工具'}`, data.result_preview ?? '', false)
      break
    }
    case 'assistant_done':
      statusText.value = '本轮完成'
      break
    case 'error':
      appendBlock('error', '错误', event.data?.message ?? '未知错误')
      break
  }
}

const interruptChat = async () => {
  if (!activeSessionId.value) return
  // 1. 中断本地 fetch
  abortController.value?.abort()

  // 2. 通知后端中断流式连接
  try {
    await fetch('/v1/chat/stream/interrupt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: activeSessionId.value }),
    })
  } catch {
    // 忽略
  }

  // 3. 保存已收到的部分 assistant 消息（标记 status=0 表示中断）
  const lastMsg = messages[messages.length - 1]
  if (lastMsg && lastMsg.role === 'assistant') {
    const contentBlocks: Record<string, unknown>[] = []
    const pendingToolUseIds = new Set<string>()

    for (const block of lastMsg.blocks) {
      switch (block.kind) {
        case 'text':
          contentBlocks.push({ type: 'text', text: block.content })
          break
        case 'reasoning':
          contentBlocks.push({ type: 'thinking', thinking: block.content })
          break
        case 'tool_use': {
          try {
            const parsed = JSON.parse(block.content)
            if (Array.isArray(parsed)) {
              // 历史消息格式：数组包含多个工具调用
              for (const tc of parsed) {
                contentBlocks.push({
                  type: 'tool_use',
                  id: tc.id,
                  name: tc.name,
                  input: tc.input || tc.arguments || {},
                })
                pendingToolUseIds.add(tc.id)
              }
            } else if (parsed && typeof parsed === 'object' && parsed.id) {
              // 流式实时格式：单个 {id, name, input} 对象（来自 tool_execution_start）
              contentBlocks.push({
                type: 'tool_use',
                id: parsed.id,
                name: parsed.name || 'tool',
                input: parsed.input || {},
              })
              pendingToolUseIds.add(parsed.id)
            }
          } catch {
            contentBlocks.push({ type: 'tool_use', text: block.content })
          }
          break
        }
        case 'tool_result': {
          try {
            const data = JSON.parse(block.content)
            const tid = data.tool_call_id || ''
            contentBlocks.push({
              type: 'tool_result',
              tool_use_id: tid,
              content: data.result_preview || block.content,
            })
            pendingToolUseIds.delete(tid)
          } catch {
            contentBlocks.push({ type: 'tool_result', content: block.content })
          }
          break
        }
        case 'error':
          contentBlocks.push({ type: 'text', text: block.content, is_error: true })
          break
      }
    }

    // 为所有已发出但未收到结果（无 tool_result 块）的工具调用补一条中断标记
    for (const tid of pendingToolUseIds) {
      contentBlocks.push({
        type: 'tool_result',
        tool_use_id: tid,
        content: '(interrupted)',
      })
    }

    try {
      await fetch(`/v1/sessions/${activeSessionId.value}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          role: 'assistant',
          content: contentBlocks,
          status: 0,
        }),
      })
    } catch {
      // 保存请求失败不影响主流程
    }
  }

  statusText.value = '已中断'
}

const handleRetry = () => {
  if (lastUserPrompt.value && !sending.value) {
    prompt.value = lastUserPrompt.value
    sendMessage()
  }
}

const sendMessage = async () => {
  const content = prompt.value.trim()
  if (!content || sending.value) return
  lastUserPrompt.value = content
  sending.value = true
  abortController.value = new AbortController()
  statusText.value = '发送中...'
  addMessage('user').blocks.push({
    id: crypto.randomUUID(), kind: 'text', title: '用户输入', content, expanded: true,
  })
  prompt.value = ''
  await nextTick()
  chatViewRef.value?.scrollPaneToBottom()
  isNearBottom.value = true
  addMessage('assistant')
  await nextTick()
  chatViewRef.value?.scrollPaneToBottom()
  isNearBottom.value = true
  try {
    const res = await fetch('/v1/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: content,
        session_id: activeSessionId.value || undefined,
        mode: useAgentMode.value ? 'agent' : 'simple',
        mcp_server_ids: useAgentMode.value && selectedMcpServerIds.value.length > 0
          ? selectedMcpServerIds.value
          : undefined,
      }),
      signal: abortController.value.signal,
    })
    if (!res.ok || !res.body) throw new Error(await res.text())
    const sessionId = res.headers.get('x-session-id')
    if (sessionId) activeSessionId.value = sessionId

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() ?? ''
      for (const part of parts) {
        const line = part.split('\n').find((l) => l.startsWith('data: '))
        if (!line) continue
        const raw = line.slice(6)
        if (raw === '[DONE]') continue
        consumeEvent(JSON.parse(raw))
      }
    }
    statusText.value = '响应完成'
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      statusText.value = '已中断'
    } else {
      statusText.value = '请求失败'
      appendBlock('error', '请求失败', error instanceof Error ? error.message : String(error))
    }
  } finally {
    sending.value = false
    abortController.value = null
    chatViewRef.value?.refreshSessions()
  }
}

// ── lifecycle ──────────────────────────────────────
onMounted(async () => {
  await refreshCapabilities()
})

// 切换界面时自动刷新对应数据
watch(activeView, async () => {
  if (activeView.value === 'tools') {
    try {
      const res = await fetch('/v1/tools')
      if (res.ok) tools.value = await res.json()
    } catch { /* ignore */ }
  } else if (activeView.value === 'skills') {
    try {
      const res = await fetch('/v1/skills')
      if (res.ok) skills.value = await res.json()
    } catch { /* ignore */ }
  } else if (activeView.value === 'memories') {
    try {
      const res = await fetch('/v1/memories')
      if (res.ok) {
        const data = await res.json()
        if (Array.isArray(data)) memories.value = data
      }
    } catch { /* ignore */ }
  } else if (activeView.value === 'knowledge') {
    // KnowledgeView 自身 onMounted 会加载数据，无需额外操作
  } else if (activeView.value === 'scheduler') {
    // SchedulerView 自身 onMounted 会加载数据，无需额外操作
  } else if (activeView.value === 'chat') {
    // 切回对话界面时自动滚动到底部
    await nextTick()
    scrollToBottom()
  }
})
</script>

<style scoped>
/* ── 整体容器 ── */
.shell {
  height: 100%;
  color: var(--color-navy-800);
  background: var(--color-slate-50);
}

/* ── 左侧栏 ── */
.sidebar {
  padding: var(--space-5) var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  overflow: hidden;
  border-right: 1px solid var(--color-navy-800);
  background: var(--color-navy-900);
  transition: width var(--transition-slow), padding var(--transition-slow);
}
.sidebar--collapsed {
  width: 76px !important;
  padding: var(--space-5) var(--space-3);
}

/* ── 品牌区域 ── */
.brand {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-1) var(--space-3);
  border-bottom: 1px solid var(--color-navy-700);
  margin-bottom: var(--space-2);
}
.brand-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
}
.brand-mark {
  width: 40px; height: 40px; border-radius: var(--radius-lg);
  display: grid; place-items: center;
  background: var(--color-gold-500);
  cursor: pointer; user-select: none;
  transition: all var(--transition-normal); flex-shrink: 0;
  position: relative;
  color: var(--color-navy-900);
}
.brand-mark-img {
  width: 22px;
  height: 22px;
  display: block;
}
/* 品牌标记发光环 */
.brand-mark::after {
  content: '';
  position: absolute;
  inset: -3px;
  border-radius: inherit;
  border: 2px solid var(--color-gold-500);
  opacity: 0.3;
  transition: opacity var(--transition-normal);
}
.brand-mark:hover {
  transform: scale(1.05);
  box-shadow: 0 0 24px rgba(234, 179, 8, 0.4);
}
.brand-mark:hover::after {
  opacity: 0.6;
}
.sidebar--collapsed .brand {
  justify-content: center;
  padding-left: 0;
  padding-right: 0;
  border-bottom: none;
  margin-bottom: 0;
}
.sidebar--collapsed .brand-mark {
  width: 40px; height: 40px;
}
.brand-title {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--color-white);
  letter-spacing: -0.01em;
}
.brand-subtitle {
  font-size: 0.78rem;
  color: var(--color-slate-400);
  margin-top: 2px;
}

/* ── 导航 ── */
.nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}

/* ── 导航分组标签 ── */
.nav-section-label {
  font-size: 0.68rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-navy-500);
  padding: var(--space-3) var(--space-3) var(--space-1);
  user-select: none;
}
.nav-section-separator {
  height: 1px;
  background: var(--color-navy-700);
  margin: var(--space-2) var(--space-3);
}
.nav-item {
  text-align: left;
  border: 1px solid transparent;
  background: transparent;
  border-radius: var(--radius-md);
  padding: 10px 12px;
  cursor: pointer;
  transition: all var(--transition-fast);
  display: flex;
  align-items: center;
  gap: var(--space-3);
  color: var(--color-slate-400);
  position: relative;
}
.nav-item:hover {
  background: rgba(255, 255, 255, 0.05);
  color: var(--color-slate-200);
}
.nav-item.active {
  background: rgba(234, 179, 8, 0.08);
  color: var(--color-gold-500);
  border-color: rgba(234, 179, 8, 0.15);
}
/* 激活指示条 */
.nav-item.active::before {
  content: '';
  position: absolute;
  left: -4px;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  background: var(--color-gold-500);
  border-radius: 0 2px 2px 0;
}
.sidebar--collapsed .nav-item {
  padding: 10px 8px;
  justify-content: center;
}
.sidebar--collapsed .nav-item:hover { transform: none; }
.sidebar--collapsed .nav-item.active::before { display: none; }

.nav-icon {
  width: 34px; height: 34px; border-radius: var(--radius-md);
  display: grid; place-items: center;
  font-size: 1.1rem; flex-shrink: 0;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06);
  transition: all var(--transition-fast);
}
.active .nav-icon {
  background: rgba(234, 179, 8, 0.12);
  border-color: rgba(234, 179, 8, 0.2);
}
.nav-item:hover .nav-icon {
  background: rgba(255, 255, 255, 0.08);
}
.nav-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}
.nav-title {
  font-weight: 600;
  font-size: 0.9rem;
  color: inherit;
  transition: color var(--transition-fast);
}
.nav-desc {
  font-size: 0.75rem;
  color: var(--color-navy-500);
  transition: color var(--transition-fast);
}
.nav-item.active .nav-desc {
  color: var(--color-gold-600);
}

/* ── 右侧区域 ── */
.right-area {
  background: var(--color-slate-50);
}

/* ── 顶栏 ── */
.topbar-wrapper {
  padding: 0;
  border-bottom: 1px solid var(--color-slate-200);
  background: var(--color-white);
}

/* ── 主体内容（滚动容器） ── */
.main-content {
  padding: 0;
  overflow: auto;
}

/* ── 底部输入区 ── */
.composer-wrapper {
  padding: 0;
}
.composer-mcp-bar {
  padding: var(--space-3) var(--space-6) 0;
}

/* ── 移动端汉堡按钮 ── */
.hamburger {
  display: none;
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-sm);
  background: var(--color-white);
  cursor: pointer;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 0;
  margin-right: var(--space-3);
}
.hamburger:hover {
  border-color: var(--color-gold-500);
  background: var(--color-gold-50);
}
.hamburger-bar {
  display: block;
  width: 18px;
  height: 2px;
  background: var(--color-navy-600);
  border-radius: 1px;
  transition: background var(--transition-fast);
}
.hamburger:hover .hamburger-bar {
  background: var(--color-gold-600);
}

/* ── 侧栏底部 ── */
.sidebar-footer {
  margin-top: auto;
  padding: var(--space-3) var(--space-3) 0;
  border-top: 1px solid var(--color-navy-700);
}
.sidebar-footer-version {
  font-size: 0.72rem;
  color: var(--color-navy-500);
  user-select: none;
}

/* ── 移动端遮罩 ── */
.sidebar-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(2, 6, 23, 0.5);
  backdrop-filter: blur(4px);
  z-index: 100;
}

/* ── 响应式：<1180px ── */
@media (max-width: 1180px) {
  .hamburger { display: flex; }
  .sidebar-overlay { display: block; }
  .sidebar {
    display: none !important;
  }
  .sidebar--mobile {
    display: flex !important;
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    z-index: 200;
    box-shadow: 4px 0 32px rgba(2, 6, 23, 0.3);
  }
}

/* ── 响应式：<768px ── */
@media (max-width: 768px) {
  .topbar-wrapper {
    padding: 0 var(--space-2);
  }
}
</style>
