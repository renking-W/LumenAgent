<template>
  <!-- 浮动按钮 -->
  <button
    v-if="!visible"
    class="mini-chat-fab"
    title="与 Agent 对话"
    @click="openPanel"
  >
    <img class="mini-chat-fab-icon" src="/logo.svg" alt="Chat" />
  </button>

  <!-- 聊天面板 -->
  <div
    v-else
    ref="panelRef"
    class="mini-chat-panel"
    :style="panelStyle"
  >
    <!-- 顶栏（拖拽移动区域） -->
    <div class="mini-chat-header" @pointerdown.prevent="startDrag">
      <span class="mini-chat-header-title">Agent 对话</span>
      <span class="mini-chat-header-status" :class="{ sending: chat.sending.value }">
        {{ chat.sending.value ? '发送中...' : chat.statusText.value }}
      </span>
      <button class="mini-chat-close" @pointerdown.stop @click="closePanel" title="关闭">×</button>
    </div>

    <!-- 消息列表 -->
    <div ref="msgListRef" class="mini-chat-messages">
      <div v-if="chat.messages.length === 0" class="mini-chat-empty">
        输入消息与 Agent 对话<br/>
        Agent 将能在 VM 上执行命令
      </div>
      <div
        v-for="msg in chat.messages"
        :key="msg.id"
        class="mini-chat-message"
        :class="'role-' + msg.role"
      >
        <div class="mini-chat-message-label">{{ msg.roleLabel }}</div>
        <div class="mini-chat-message-blocks">
          <div
            v-for="block in msg.blocks"
            :key="block.id"
            class="mini-chat-block"
            :class="'kind-' + block.kind"
          >
            <!-- 文本 → markdown 渲染 -->
            <template v-if="block.kind === 'text'">
              <div class="md" v-html="renderMarkdown(block.content)"></div>
            </template>

            <!-- 思考 -->
            <template v-else-if="block.kind === 'thinking'">
              <details class="mini-chat-thinking" :open="block.expanded">
                <summary>{{ block.title }}</summary>
                <div class="md" v-html="renderMarkdown(block.content)"></div>
              </details>
            </template>

            <!-- 工具调用 -->
            <template v-else-if="block.kind === 'tool_use'">
              <details class="mini-chat-tool" :open="block.expanded">
                <summary>{{ block.title }}</summary>
                <pre class="mini-chat-pre">{{ block.content }}</pre>
              </details>
            </template>

            <!-- 工具结果 -->
            <template v-else-if="block.kind === 'tool_result'">
              <details class="mini-chat-tool-result" :open="block.expanded">
                <summary>{{ block.title }}</summary>
                <pre class="mini-chat-pre">{{ block.content }}</pre>
              </details>
            </template>

            <!-- 审批详情 -->
            <template v-else-if="block.kind === 'awaiting_approval'">
              <ApprovalCard :block="block" @approve="handleApprove" @reject="handleReject" @approve-all="handleApproveAll" />
            </template>

            <!-- 错误 -->
            <template v-else-if="block.kind === 'error'">
              <div class="mini-chat-error">{{ block.content }}</div>
            </template>
          </div>
        </div>
        <div class="mini-chat-message-time">{{ msg.time }}</div>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="mini-chat-input-area">
      <input
        ref="inputRef"
        v-model="inputText"
        class="mini-chat-input"
        placeholder="输入消息..."
        :disabled="chat.sending.value"
        @keydown.enter.prevent="send"
      />
      <button
        class="mini-chat-send-btn"
        :class="{ 'mini-chat-send-btn--stop': chat.sending.value }"
        :disabled="chat.sending.value ? false : !inputText.trim()"
        @click="chat.sending.value ? chat.interrupt() : send()"
      >
        {{ chat.sending.value ? '■ 中断' : '发送' }}
      </button>
    </div>

    <!-- 拖拽调节大小的手柄 -->
    <div class="mini-chat-resize-handle" @pointerdown.prevent="startResize"></div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useChatStream } from '../composables/useChatStream'
import { renderMarkdown } from '../utils/markdown'
import type { ChatBlock } from '../types'
import ApprovalCard from './approval/ApprovalCard.vue'

const props = defineProps<{
  vmId?: string
  vmHost?: string
  vmPort?: number
  vmUsername?: string
  vmDescription?: string
}>()

const visible = ref(false)
const inputText = ref('')
const inputRef = ref<HTMLInputElement | null>(null)
const msgListRef = ref<HTMLElement | null>(null)
const panelRef = ref<HTMLElement | null>(null)

// 独立的聊天流实例
const chat = useChatStream()

// ── 面板位置 & 大小 ──
const panelLeft = ref<number | undefined>(undefined)
const panelTop = ref<number | undefined>(undefined)
const panelWidth = ref(420)
const panelHeight = ref(540)
const MIN_W = 300
const MIN_H = 400
const MAX_W = 800
const MAX_H = 800

const panelStyle = computed(() => ({
  width: `${panelWidth.value}px`,
  height: `${panelHeight.value}px`,
  left: panelLeft.value != null ? `${panelLeft.value}px` : undefined,
  top: panelTop.value != null ? `${panelTop.value}px` : undefined,
  right: panelLeft.value != null ? 'auto' : '24px',
  bottom: panelTop.value != null ? 'auto' : '24px',
}))

// 构建 VM 上下文的 self_system 提示词
const vmSelfSystem = computed(() => {
  if (!props.vmId) return undefined
  let text = `当前正在操作的虚拟机信息：\n`
  text += `- VM ID: ${props.vmId}\n`
  text += `- Host: ${props.vmHost ?? '未知'}\n`
  text += `- Port: ${props.vmPort ?? '未知'}\n`
  text += `- Username: ${props.vmUsername ?? '未知'}\n`
  if (props.vmDescription) {
    text += `- Description: ${props.vmDescription}\n`
  }
  text += `\n你可以利用这些信息直接找到并操作这台虚拟机。\n注意：当需要使用sudo指令/管理员权限时需要向用户确认管理员密码以保能够正常执行`
  return text
})

// VM 专属会话 ID：固定格式 vm_{vmId}，保证相同 VM 共享同一会话
const vmSessionId = computed(() => props.vmId ? `vm_${props.vmId}` : '')

async function openPanel() {
  visible.value = true
  // 加载 VM 历史会话（首次创建时后端返回空列表）
  if (vmSessionId.value) {
    await chat.loadSession(vmSessionId.value)
    // loadSession 成功时会设置 sessionId，失败（新会话）时手工设置
    if (!chat.sessionId.value) {
      chat.setSessionId(vmSessionId.value)
    }
  }
  nextTick(() => {
    inputRef.value?.focus()
    scrollToBottom()
  })
}

function closePanel() {
  if (chat.sending.value) {
    chat.interrupt()
  }
  visible.value = false
}

async function send() {
  const text = inputText.value.trim()
  if (!text || chat.sending.value) return
  inputText.value = ''
  chat.send(text, { mode: 'agent', self_system: vmSelfSystem.value, session_kind: 2 })
  await nextTick()
  scrollToBottom()
}

function scrollToBottom() {
  nextTick(() => {
    if (msgListRef.value) {
      msgListRef.value.scrollTop = msgListRef.value.scrollHeight
    }
  })
}

// 自动滚动
watch(
  () => chat.messages.map(m => m.blocks.length).join(','),
  () => scrollToBottom(),
)

// ── 审批操作 ──
function handleApprove(blockId: string, toolCallId: string) {
  chat.approve(blockId, toolCallId, true)
}

function handleReject(blockId: string, toolCallId: string) {
  chat.approve(blockId, toolCallId, false)
}

/** 批量批准块中所有待审批的工具调用 */
function handleApproveAll(blockId: string) {
  // 从聊天消息中找对应块
  for (const msg of chat.messages) {
    const block = msg.blocks.find(b => b.id === blockId)
    if (!block || block.kind !== 'awaiting_approval') continue
    try {
      const toolCalls: Array<{ id: string; _resolved?: boolean }> = JSON.parse(block.content)
      for (const tc of toolCalls) {
        if (tc._resolved === undefined) {
          chat.approve(blockId, tc.id, true)
        }
      }
    } catch { /* ignore */ }
    break
  }
}

// ── 拖拽移动 ──
let dragState: { startX: number; startY: number; origLeft: number; origTop: number } | null = null

function startDrag(e: PointerEvent) {
  const panel = panelRef.value
  if (!panel) return
  panel.setPointerCapture(e.pointerId)

  const rect = panel.getBoundingClientRect()
  const left = panelLeft.value ?? window.innerWidth - rect.width - 24
  const top = panelTop.value ?? window.innerHeight - rect.height - 24
  panelLeft.value = left
  panelTop.value = top

  dragState = { startX: e.clientX, startY: e.clientY, origLeft: left, origTop: top }

  const onMove = (ev: PointerEvent) => {
    if (!dragState) return
    panelLeft.value = dragState.origLeft + (ev.clientX - dragState.startX)
    panelTop.value = dragState.origTop + (ev.clientY - dragState.startY)
  }
  const onUp = () => {
    dragState = null
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
  }
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
}

// ── 拖拽调节大小 ──
let resizeState: { startX: number; startY: number; origW: number; origH: number } | null = null

function startResize(e: PointerEvent) {
  const panel = panelRef.value
  if (!panel) return
  panel.setPointerCapture(e.pointerId)

  resizeState = {
    startX: e.clientX,
    startY: e.clientY,
    origW: panelWidth.value,
    origH: panelHeight.value,
  }

  const onMove = (ev: PointerEvent) => {
    if (!resizeState) return
    panelWidth.value = Math.min(MAX_W, Math.max(MIN_W, resizeState.origW + (ev.clientX - resizeState.startX)))
    panelHeight.value = Math.min(MAX_H, Math.max(MIN_H, resizeState.origH + (ev.clientY - resizeState.startY)))
  }
  const onUp = () => {
    resizeState = null
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
  }
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
}
</script>

<style scoped>
/* ── 浮动按钮 ── */
.mini-chat-fab {
  position: fixed;
  bottom: 24px;
  right: 24px;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: #EAB308;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 16px rgba(234, 179, 8, 0.35);
  transition: transform 0.2s, box-shadow 0.2s;
  z-index: 999;
}
.mini-chat-fab:hover {
  transform: scale(1.08);
  box-shadow: 0 6px 24px rgba(234, 179, 8, 0.5);
}
.mini-chat-fab-icon {
  width: 26px;
  height: 26px;
  display: block;
}

/* ── 面板 ── */
.mini-chat-panel {
  position: fixed;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.18);
  display: flex;
  flex-direction: column;
  z-index: 1000;
  overflow: hidden;
  border: 1px solid #e5e7eb;
  user-select: none;
}

/* ── 顶栏（也是拖拽手柄）── */
.mini-chat-header {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  background: #0F172A;
  color: #fff;
  gap: 8px;
  flex-shrink: 0;
  cursor: grab;
  touch-action: none;
}
.mini-chat-header:active {
  cursor: grabbing;
}
.mini-chat-header-title {
  font-weight: 600;
  font-size: 14px;
}
.mini-chat-header-status {
  font-size: 11px;
  color: #94A3B8;
  flex: 1;
}
.mini-chat-header-status.sending {
  color: #EAB308;
}
.mini-chat-close {
  background: none;
  border: none;
  color: #fff;
  font-size: 20px;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
}
.mini-chat-close:hover {
  color: #EAB308;
}

/* ── 消息列表 ── */
.mini-chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: #F8FAFC;
}
.mini-chat-empty {
  text-align: center;
  color: #94A3B8;
  font-size: 13px;
  padding: 40px 0;
  line-height: 1.8;
}

.mini-chat-message {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.mini-chat-message.role-user {
  align-items: flex-end;
}
.mini-chat-message.role-assistant {
  align-items: flex-start;
}

.mini-chat-message-label {
  font-size: 11px;
  color: #94A3B8;
  font-weight: 500;
}
.mini-chat-message-blocks {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 100%;
}
.mini-chat-message.role-user .mini-chat-message-blocks {
  background: #EAB308;
  color: #1e293b;
  padding: 8px 12px;
  border-radius: 12px 12px 4px 12px;
  font-size: 13px;
}
.mini-chat-message.role-assistant .mini-chat-message-blocks {
  width: 100%;
}
.mini-chat-message-time {
  font-size: 10px;
  color: #CBD5E1;
  margin-top: 1px;
}

/* ── 内容块 ── */
.mini-chat-block {
  font-size: 13px;
  line-height: 1.5;
}
.mini-chat-pre {
  font-size: 11px;
  background: #1E293B;
  color: #E2E8F0;
  padding: 8px;
  border-radius: 6px;
  overflow-x: auto;
  max-height: 160px;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 4px 0;
}
.mini-chat-thinking summary,
.mini-chat-tool summary,
.mini-chat-tool-result summary {
  font-size: 12px;
  color: #64748B;
  cursor: pointer;
  user-select: none;
}
.mini-chat-error {
  color: #EF4444;
  font-size: 13px;
}

/* ── 输入区 ── */
.mini-chat-input-area {
  display: flex;
  gap: 8px;
  padding: 12px;
  border-top: 1px solid #E5E7EB;
  background: #fff;
  flex-shrink: 0;
}
.mini-chat-input {
  flex: 1;
  border: 1px solid #D1D5DB;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
  outline: none;
}
.mini-chat-input:focus {
  border-color: #EAB308;
  box-shadow: 0 0 0 2px rgba(234, 179, 8, 0.2);
}
.mini-chat-send-btn {
  background: #EAB308;
  color: #1e293b;
  border: none;
  border-radius: 8px;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}
.mini-chat-send-btn:hover:not(:disabled) {
  background: #D97706;
}
.mini-chat-send-btn--stop {
  background: #EF4444;
  color: #fff;
}
.mini-chat-send-btn--stop:hover {
  background: #DC2626;
}
.mini-chat-send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ── 调节大小手柄 ── */
.mini-chat-resize-handle {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 16px;
  height: 16px;
  cursor: nwse-resize;
  z-index: 10;
  touch-action: none;
}
.mini-chat-resize-handle::after {
  content: '';
  position: absolute;
  right: 3px;
  bottom: 3px;
  width: 10px;
  height: 10px;
  border-right: 2px solid #CBD5E1;
  border-bottom: 2px solid #CBD5E1;
  border-radius: 0 0 3px 0;
}
</style>
