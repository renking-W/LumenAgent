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

        <!-- ── 功能管理 ── -->
        <div v-if="!sidebarCollapsed" class="nav-section-separator"></div>
        <div v-if="!sidebarCollapsed" class="nav-section-label">功能</div>
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
          :class="{ active: activeView === 'vm' }"
          @click="activeView = 'vm'"
        >
          <span class="nav-icon">🖥️</span>
          <span v-if="!sidebarCollapsed" class="nav-text">
            <span class="nav-title">虚拟机</span>
            <span class="nav-desc">管理远程 SSH 虚拟机</span>
          </span>
        </button>
        <button
          class="nav-item"
          :class="{ active: activeView === 'sub-agents' }"
          @click="activeView = 'sub-agents'"
        >
          <span class="nav-icon">🤖</span>
          <span v-if="!sidebarCollapsed" class="nav-text">
            <span class="nav-title">Agent 编排</span>
            <span class="nav-desc">调度本地编码 Agent</span>
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

        <!-- ── 其它 ── -->
        <div v-if="!sidebarCollapsed" class="nav-section-separator"></div>
        <div v-if="!sidebarCollapsed" class="nav-section-label">其它</div>
        <button
          class="nav-item"
          :class="{ active: activeView === 'config' }"
          @click="activeView = 'config'"
        >
          <span class="nav-icon">⚙️</span>
          <span v-if="!sidebarCollapsed" class="nav-text">
            <span class="nav-title">系统配置</span>
            <span class="nav-desc">编辑系统运行参数</span>
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
          @approve-tool="(blockId, toolId) => handleToolApproval(blockId, toolId, true)"
          @reject-tool="(blockId, toolId) => handleToolApproval(blockId, toolId, false)"
        />
        <ToolView    v-else-if="activeView === 'tools'"     :tools="tools" :connected="connected" />
        <SkillView   v-else-if="activeView === 'skills'"   :skills="skills" />
        <MemoryView  v-else-if="activeView === 'memories'" :memories="memories" />
        <MCPServerView v-else-if="activeView === 'mcp'" />
        <VMView v-else-if="activeView === 'vm'" />
        <ConfigView v-else-if="activeView === 'config'" />
        <KnowledgeView v-else-if="activeView === 'knowledge'" />
        <SchedulerView v-else-if="activeView === 'scheduler'" />
        <LogView v-else-if="activeView === 'logs'" />
        <SubAgentView v-else-if="activeView === 'sub-agents'" />
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
          :approval-mode="approvalMode"
          :status-text="statusText"
          @update:prompt="prompt = $event"
          @update:use-agent-mode="useAgentMode = $event"
          @send="sendMessage"
          @interrupt="interruptChat"
          @update:approval-mode="approvalMode = $event"
        />
      </el-footer>
    </el-container>

    <!-- ======== API Key 管理弹窗 ======== -->
    <ApiKeyManager v-model="apiKeyDialogVisible" />
  </el-container>
</template>

<script setup lang="ts">
import { ElMessageBox } from 'element-plus'
import { onMounted, ref, watch, nextTick } from 'vue'
import type { ToolInfo, SkillInfo, MemoryFileItem, ChatBlock, ChatMessage } from './types'
import { useChatStream } from './composables/useChatStream'
import AppTopbar from './components/AppTopbar.vue'
import ChatView from './components/ChatView.vue'
import ToolView from './components/ToolView.vue'
import SkillView from './components/SkillView.vue'
import MemoryView from './components/MemoryView.vue'
import MCPServerView from './components/MCPServerView.vue'
import VMView from './components/VMView.vue'
import MCPServerSelector from './components/MCPServerSelector.vue'
import KnowledgeView from './components/KnowledgeView.vue'
import SchedulerView from './components/SchedulerView.vue'
import LogView from './components/LogView.vue'
import ConfigView from './components/ConfigView.vue'
import AppComposer from './components/AppComposer.vue'
import ApiKeyManager from './components/ApiKeyManager.vue'
import SubAgentView from './components/SubAgentView.vue'

// ── 聊天流 ─────────────────────────────────────────
const chat = useChatStream()
const messages = chat.messages
const sending = chat.sending
const activeSessionId = chat.sessionId
const streamingMessageId = chat.streamingMessageId
const statusText = chat.statusText
const lastUserPrompt = chat.lastUserPrompt

// ── 视图切换（默认为聊天界面）──────────────────
const activeView = ref<'chat' | 'tools' | 'skills' | 'memories' | 'mcp' | 'vm' | 'config' | 'knowledge' | 'scheduler' | 'logs' | 'sub-agents'>('chat')

// ── UI 状态 ───────────────────────────────────────
const sidebarVisible = ref(false)
const sidebarCollapsed = ref(false)
const useAgentMode = ref(true)
const approvalMode = ref<'none' | 'all' | 'dangerous'>('dangerous')
const prompt = ref('')
const selectedMcpServerIds = ref<string[]>([])
const apiKeyDialogVisible = ref(false)
const mainContent = ref<HTMLElement | null>(null)
const chatViewRef = ref<InstanceType<typeof ChatView> | null>(null)
const connected = ref(false)
const tools = ref<ToolInfo[]>([])
const skills = ref<SkillInfo[]>([])
const memories = ref<MemoryFileItem[]>([])

// ── 游标分页 ──────────────────────────────────────
const beforeSeq = ref<number | undefined>(undefined)
const loadingMore = ref(false)
const hasMore = ref(true)

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

// ── actions（委托给 composable） ──────────────────
const handleToolApproval = (blockId: string, toolCallId: string, approved: boolean) =>
  chat.approve(blockId, toolCallId, approved)

const resetConversation = async () => {
  await chat.reset()
  beforeSeq.value = undefined
  hasMore.value = true

  // 提示用户手动输入 session_id（可选，留空则由后端自动生成）
  try {
    const { value } = await ElMessageBox.prompt(
      '输入会话 ID（留空则自动生成）',
      '新建会话',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消（自动生成）',
        inputPlaceholder: '自定义 session_id（可选）',
        inputValidator: (val: string) => {
          if (val && val.trim().length > 0 && !/^[a-zA-Z0-9_-]+$/.test(val.trim())) {
            return '仅允许字母、数字、下划线和连字符'
          }
          return true
        },
      }
    )
    if (value && value.trim()) {
      chat.setSessionId(value.trim())
    }
  } catch {
    // 用户取消 → 沿用空 session_id（后端自动生成）
  }
}

const interruptChat = () => chat.interrupt()
const handleRetry = () => {
  if (lastUserPrompt.value && !sending.value) {
    prompt.value = lastUserPrompt.value
    sendMessage()
  }
}

const onDeleteSession = async (sessionId: string) => {
  if (activeSessionId.value === sessionId) {
    await chat.reset()
    beforeSeq.value = undefined
    hasMore.value = true
    statusText.value = '会话已删除'
  }
}

// ── 分页辅助 ──────────────────────────────────────
type CB = { type: string; text?: string; thinking?: string; name?: string; input?: unknown; content?: string; is_error?: boolean; id?: string; tool_use_id?: string; image_url?: { url: string } }
interface StoredMsg { seq: number; role: string; content: CB[]; created_at: string; updated_at: string; status: number }

const formatStoredTime = (iso: string) => {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const cbToBlock = (cb: CB): ChatBlock => {
  if (cb.type === 'thinking') return { id: crypto.randomUUID(), kind: 'thinking', title: '💭 思考', content: cb.thinking ?? '', expanded: false }
  if (cb.type === 'tool_use') return { id: crypto.randomUUID(), kind: 'tool_use', title: cb.name || '工具调用', content: pretty(cb.input ?? ''), expanded: false }
  if (cb.type === 'tool_result') return { id: crypto.randomUUID(), kind: 'tool_result', title: `工具结果${cb.name ? ': ' + cb.name : ''}`, content: cb.content ?? pretty(cb.input ?? ''), expanded: false }
  if (cb.type === 'image_url') return { id: crypto.randomUUID(), kind: 'image', title: '图片', content: cb.image_url?.url ?? '', expanded: true }
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

const pretty = (value: unknown) => JSON.stringify(value, null, 2)

const loadSessionMessages = async (sessionId: string) => {
  await chat.loadSession(sessionId)
  beforeSeq.value = undefined
  hasMore.value = true
  await nextTick()
  chatViewRef.value?.scrollPaneToBottom()
}

const sendMessage = async (imageUrls: string[] = []) => {
  const content = prompt.value.trim()
  if (!content || sending.value) return
  prompt.value = ''
  // 用 composable 发送
  chat.send(content, {
    mode: useAgentMode.value ? 'agent' : 'simple',
    approval_mode: useAgentMode.value ? approvalMode.value : undefined,
    mcp_server_ids: useAgentMode.value && selectedMcpServerIds.value.length > 0
      ? selectedMcpServerIds.value
      : undefined,
    image_urls: useAgentMode.value && imageUrls.length ? imageUrls : undefined,
  })
  await nextTick()
  chatViewRef.value?.scrollPaneToBottom()
  isNearBottom.value = true
}

// ── 功能刷新 ────────────────────────────────────────

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

/* ── 左侧栏 — 浅薄荷青柠绿 ── */
.sidebar {
  padding: var(--space-5) var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  overflow: hidden;
  border-right: 1px solid #D5E3CC;
  background: #EEF5E6;
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
  border-bottom: 1px solid #D5E3CC;
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
  color: #2C4A28;
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
  color: #2C4A28;
  letter-spacing: -0.01em;
}
.brand-subtitle {
  font-size: 0.78rem;
  color: #6B8C5C;
  margin-top: 2px;
}

/* ── 导航 ── */
.nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #C8DFC0 transparent;
}

/* ── 导航分组标签 ── */
.nav-section-label {
  font-size: 0.68rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #8AAC7A;
  padding: var(--space-3) var(--space-3) var(--space-1);
  user-select: none;
}
.nav-section-separator {
  height: 1px;
  background: #D5E3CC;
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
  color: #4A6B42;
  position: relative;
}
.nav-item:hover {
  background: rgba(44, 74, 40, 0.06);
  color: #1A3A1A;
}
.nav-item.active {
  background: rgba(234, 179, 8, 0.12);
  color: #8A6D00;
  border-color: rgba(234, 179, 8, 0.2);
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
  background: rgba(44, 74, 40, 0.04);
  border: 1px solid rgba(44, 74, 40, 0.08);
  transition: all var(--transition-fast);
}
.active .nav-icon {
  background: rgba(234, 179, 8, 0.15);
  border-color: rgba(234, 179, 8, 0.25);
}
.nav-item:hover .nav-icon {
  background: rgba(44, 74, 40, 0.08);
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
  color: #7A9C6A;
  transition: color var(--transition-fast);
}
.nav-item.active .nav-desc {
  color: #A07D00;
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
  border-top: 1px solid #D5E3CC;
}
.sidebar-footer-version {
  font-size: 0.72rem;
  color: #8AAC7A;
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
