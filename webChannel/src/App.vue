<template>
  <el-container class="shell">
    <!-- ======== 移动端遮罩 ======== -->
    <div
      v-if="sidebarVisible"
      class="sidebar-overlay"
      @click="sidebarVisible = false"
    ></div>

    <!-- ======== 左侧栏 ======== -->
    <el-aside width="250px" class="sidebar" :class="{ 'sidebar--mobile': sidebarVisible }">
      <div class="brand">
        <div class="brand-mark">L</div>
        <div>
          <div class="brand-title">LumenAgent</div>
          <div class="brand-subtitle">Claude-style Web Channel</div>
        </div>
      </div>

      <nav class="nav">
        <button
          class="nav-item"
          :class="{ active: activeView === 'chat' }"
          @click="activeView = 'chat'"
        >
          <span class="nav-title">对话</span>
          <span class="nav-desc">实时流式聊天</span>
        </button>
        <button
          class="nav-item"
          :class="{ active: activeView === 'tools' }"
          @click="activeView = 'tools'"
        >
          <span class="nav-title">工具</span>
          <span class="nav-desc">单独展示所有 Tool</span>
        </button>
        <button
          class="nav-item"
          :class="{ active: activeView === 'skills' }"
          @click="activeView = 'skills'"
        >
          <span class="nav-title">技能</span>
          <span class="nav-desc">单独展示所有 Skill</span>
        </button>
      </nav>

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
        <ToolView   v-else-if="activeView === 'tools'"  :tools="tools" :connected="connected" />
        <SkillView  v-else                             :skills="skills" />
      </el-main>

      <el-footer v-if="activeView === 'chat'" height="auto" class="composer-wrapper">
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
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch, nextTick } from 'vue'
import type { ToolInfo, SkillInfo, ChatBlock, ChatMessage } from './types'
import AppTopbar from './components/AppTopbar.vue'
import ChatView from './components/ChatView.vue'
import ToolView from './components/ToolView.vue'
import SkillView from './components/SkillView.vue'
import AppComposer from './components/AppComposer.vue'

// ── state ──────────────────────────────────────────
const sidebarVisible = ref(false)
const activeView = ref<'chat' | 'tools' | 'skills'>('chat')
const connected = ref(false)
const sending = ref(false)
const useAgentMode = ref(true)
const prompt = ref('')
const lastUserPrompt = ref('')
const activeSessionId = ref('')
const statusText = ref('等待输入')
const tools = ref<ToolInfo[]>([])
const skills = ref<SkillInfo[]>([])
const mainContent = ref<HTMLElement | null>(null)
const chatViewRef = ref<InstanceType<typeof ChatView> | null>(null)
const abortController = ref<AbortController | null>(null)

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
const refreshCapabilities = async () => {
  try {
    const [toolRes, skillRes] = await Promise.all([
      fetch('/v1/tools'),
      fetch('/v1/skills'),
    ])
    tools.value = await toolRes.json()
    skills.value = await skillRes.json()
    connected.value = true
  } catch {
    connected.value = false
  }
}

const resetConversation = () => {
  messages.splice(0)
  activeSessionId.value = ''
  beforeSeq.value = undefined
  hasMore.value = true
  statusText.value = '已重置为新会话'
}

const onDeleteSession = (sessionId: string) => {
  if (activeSessionId.value === sessionId) {
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
  try {
    const res = await fetch(`/v1/sessions/${sessionId}/messages?limit=20`)
    if (!res.ok) return
    const stored: StoredMsg[] = await res.json()
    activeSessionId.value = sessionId
    beforeSeq.value = undefined
    hasMore.value = stored.length === 20
    loadingMore.value = false

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
      const toolCalls = event.data?.tool_calls ?? []
      const toolName = Array.isArray(toolCalls) && toolCalls.length > 0
        ? toolCalls.map((tc: any) => tc.name).filter(Boolean).join(', ')
        : '工具调用'
      appendBlock('tool_use', toolName, pretty(toolCalls), false)
      break
    }
    case 'tool_execution_start':
      appendBlock('tool_result', `开始执行 ${event.data?.name ?? 'tool'}`, pretty(event.data ?? {}), false)
      break
    case 'tool_execution_end':
      appendBlock('tool_result', `执行结束 ${event.data?.name ?? 'tool'}`, pretty(event.data ?? {}), false)
      break
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
            const toolCalls = JSON.parse(block.content)
            if (Array.isArray(toolCalls)) {
              for (const tc of toolCalls) {
                contentBlocks.push({
                  type: 'tool_use',
                  id: tc.id,
                  name: tc.name,
                  input: tc.input || tc.arguments || {},
                })
                pendingToolUseIds.add(tc.id)
              }
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
      tools.value = await res.json()
      connected.value = true
    } catch { connected.value = false }
  } else if (activeView.value === 'skills') {
    try {
      const res = await fetch('/v1/skills')
      skills.value = await res.json()
      connected.value = true
    } catch { connected.value = false }
  }
})
</script>

<style scoped>
/* ── 整体容器 ── */
.shell {
  height: 100%;
  color: #1f2937;
  background: #ffffff;
}

/* ── 左侧栏 ── */
.sidebar {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow: hidden;
  border-right: 1px solid #e5e7eb;
  background: #ffffff;
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 4px 10px;
}
.brand-mark {
  width: 44px; height: 44px; border-radius: 14px;
  display: grid; place-items: center;
  font-weight: 700; color: #ffffff;
  background: linear-gradient(135deg, #6366f1, #0ea5e9);
}
.brand-title { font-size: 1.1rem; font-weight: 700; color: #111827; }
.brand-subtitle { font-size: 0.85rem; color: #6b7280; }
.nav { display: flex; flex-direction: column; gap: 10px; }
.nav-item {
  text-align: left; border: 1px solid #e5e7eb; background: #ffffff;
  border-radius: 16px; padding: 14px 16px; cursor: pointer;
  transition: all 0.2s ease; display: flex; flex-direction: column; gap: 4px;
}
.nav-item:hover { transform: translateY(-1px); box-shadow: 0 10px 22px rgba(15, 23, 42, 0.05); }
.nav-item.active { border-color: #93c5fd; background: #eff6ff; }
.nav-title { font-weight: 700; color: #111827; }
.nav-desc { font-size: 0.84rem; color: #6b7280; }

/* ── 右侧区域 ── */
.right-area { background: #f8fafc; }

/* ── 顶栏 ── */
.topbar-wrapper { padding: 0; border-bottom: 1px solid #e5e7eb; background: #ffffff; }

/* ── 主体内容（滚动容器） ── */
.main-content { padding: 0; overflow: auto; }

/* ── 底部输入区 ── */
.composer-wrapper { padding: 0; }

/* ── 移动端汉堡按钮 ── */
.hamburger {
  display: none;
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #ffffff;
  cursor: pointer;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 0;
  margin-right: 12px;
}
.hamburger-bar {
  display: block;
  width: 18px;
  height: 2px;
  background: #374151;
  border-radius: 1px;
}

/* ── 移动端遮罩 ── */
.sidebar-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 100;
}

/* ── 响应式：<1180px ── */
@media (max-width: 1180px) {
  .hamburger {
    display: flex;
  }
  .sidebar-overlay {
    display: block;
  }
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
    box-shadow: 4px 0 24px rgba(0, 0, 0, 0.15);
  }
}

/* ── 响应式：<768px ── */
@media (max-width: 768px) {
  .topbar-wrapper {
    padding: 0 8px;
  }
}
</style>
