<template>
  <footer class="composer">
    <!-- 隐藏文件选择框 -->
    <input
      ref="fileInputRef"
      type="file"
      accept="image/*"
      multiple
      style="display:none"
      @change="onPick"
    />

    <!-- 主卡片：图片预览 + 输入框 + 底部操作栏 -->
    <div class="composer-card">
      <!-- 图片附件预览区（在输入框上方，卡片内） -->
      <div v-if="attachments.length > 0" class="composer-attach-preview">
        <div
          v-for="(att, idx) in attachments"
          :key="att.url"
          class="attach-thumb"
        >
          <img :src="att.url" :alt="att.filename" class="attach-thumb-img" />
          <button class="attach-thumb-del" @click="removeAttachment(idx)" title="移除">×</button>
        </div>
      </div>

      <!-- 输入区 -->
      <textarea
        class="composer-textarea"
        :value="prompt"
        :placeholder="sending ? '等待响应中...' : '发消息...'"
        rows="3"
        @input="onInput"
        @keydown.enter.exact.prevent="handleSend"
        @keydown.ctrl.enter="insertNewline"
      />

      <!-- 底部操作栏 -->
      <div class="composer-actions">
        <!-- 左侧：上传 + 模式 + 审批 -->
        <div class="composer-actions-left">
          <!-- 上传按钮 "+" -->
          <button
            class="action-btn action-btn--plus"
            :disabled="sending || uploading"
            :title="uploading ? '上传中...' : '添加图片'"
            @click="fileInputRef?.click()"
          >
            {{ uploading ? '…' : '+' }}
          </button>

          <!-- Agent / Simple 模式切换 -->
          <button
            class="action-btn action-btn--mode"
            :class="{ 'action-btn--mode-active': useAgentMode }"
            @click="emit('update:useAgentMode', !useAgentMode)"
            title="切换 Agent / Simple 模式"
          >
            <span class="mode-icon">✦</span>
            <span class="mode-label">{{ useAgentMode ? 'Agent' : 'Simple' }}</span>
            <span class="mode-chevron">›</span>
          </button>

          <!-- 审批模式（仅 Agent 模式下可见） -->
          <button
            v-if="useAgentMode"
            class="action-btn action-btn--approval"
            :class="{ 'action-btn--approval-off': approvalMode === 'none' }"
            @click="toggleApprovalMode"
            title="切换审批模式"
          >
            <span>{{ approvalMode === 'none' ? '⚡' : '🔒' }}</span>
            <span>{{ approvalMode === 'none' ? '始终放行' : approvalMode === 'all' ? '全部审批' : '危险审批' }}</span>
          </button>
        </div>

        <!-- 右侧：发送 / 中断 -->
        <div class="composer-actions-right">
          <button
            v-if="!sending"
            class="send-btn"
            :disabled="!prompt.trim() && attachments.length === 0"
            @click="handleSend"
            title="发送 (Enter)"
          >
            ↑
          </button>
          <button
            v-else
            class="interrupt-btn"
            @click="$emit('interrupt')"
            title="中断"
          >
            ■
          </button>
        </div>
      </div>
    </div>
  </footer>
</template>

<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  prompt: string
  sending: boolean
  useAgentMode: boolean
  approvalMode: 'none' | 'all' | 'dangerous'
  statusText: string
}>()

const emit = defineEmits<{
  'update:prompt': [value: string]
  'update:approval-mode': [value: 'none' | 'all' | 'dangerous']
  'update:useAgentMode': [value: boolean]
  send: [imageUrls: string[]]
  interrupt: []
}>()

// ── 附件状态 ──────────────────────────────────────
interface Attachment { filename: string; url: string }
const attachments = ref<Attachment[]>([])
const uploading = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)

const removeAttachment = (idx: number) => {
  attachments.value.splice(idx, 1)
}

const onPick = async (e: Event) => {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  input.value = ''
  if (!files.length) return

  const rejected: string[] = []
  const images = files.filter(f => {
    if (f.type.startsWith('image/')) return true
    rejected.push(f.name)
    return false
  })

  if (rejected.length) {
    ElMessage.warning(`当前仅支持图片上传，已跳过：${rejected.join('、')}`)
  }
  if (!images.length) return

  uploading.value = true
  try {
    await Promise.all(images.map(async (file) => {
      const fd = new FormData()
      fd.append('file', file)
      const res = await fetch('/v1/upload', { method: 'POST', body: fd })
      if (!res.ok) {
        const detail = await res.text()
        ElMessage.error(`上传失败：${detail}`)
        return
      }
      const data: { filename: string; url: string } = await res.json()
      attachments.value.push({ filename: data.filename, url: data.url })
    }))
  } catch {
    ElMessage.error('上传请求失败，请检查网络')
  } finally {
    uploading.value = false
  }
}

const handleSend = () => {
  if (!props.prompt.trim() && attachments.value.length === 0) return
  if (props.sending) return
  const urls = attachments.value.map(a => a.url)
  attachments.value = []
  emit('send', urls)
}

// ── 审批模式 ──────────────────────────────────────
const toggleApprovalMode = () => {
  if (props.approvalMode === 'dangerous') {
    emit('update:approval-mode', 'none')
  } else {
    emit('update:approval-mode', 'dangerous')
  }
}

// ── 输入处理 ──────────────────────────────────────
const onInput = (e: Event) => {
  emit('update:prompt', (e.target as HTMLTextAreaElement).value)
}

/** Ctrl+Enter 在光标位置插入换行 */
const insertNewline = (e: KeyboardEvent) => {
  const target = e.target as HTMLTextAreaElement | null
  if (!target) return
  const start = target.selectionStart
  const end = target.selectionEnd
  const newVal = props.prompt.substring(0, start) + '\n' + props.prompt.substring(end)
  emit('update:prompt', newVal)
  nextTick(() => {
    target.selectionStart = target.selectionEnd = start + 1
  })
}
</script>

<style scoped>
.composer {
  padding: var(--space-3) var(--space-5) var(--space-4);
  background: var(--color-white);
  border-top: 1px solid var(--color-slate-200);
}

/* ── 主卡片 ── */
.composer-card {
  border: 1.5px solid var(--color-slate-200);
  border-radius: var(--radius-xl);
  background: var(--color-white);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  overflow: hidden;
}
.composer-card:focus-within {
  border-color: var(--color-slate-300);
  box-shadow: 0 0 0 3px rgba(203, 213, 225, 0.3);
}

/* ── 图片预览区 ── */
.composer-attach-preview {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4) 0;
}
.attach-thumb {
  position: relative;
  width: 64px;
  height: 64px;
  flex-shrink: 0;
}
.attach-thumb-img {
  width: 64px;
  height: 64px;
  object-fit: cover;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-slate-200);
  display: block;
}
.attach-thumb-del {
  position: absolute;
  top: -5px;
  right: -5px;
  width: 18px;
  height: 18px;
  border-radius: var(--radius-full);
  background: var(--color-error);
  color: #fff;
  border: none;
  font-size: 0.72rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: opacity var(--transition-fast);
  line-height: 1;
}
.attach-thumb-del:hover { opacity: 0.8; }

/* ── 输入框 ── */
.composer-textarea {
  display: block;
  width: 100%;
  min-height: 72px;
  max-height: 240px;
  resize: none;
  border: none;
  outline: none;
  background: transparent;
  padding: var(--space-4) var(--space-4) var(--space-2);
  font-family: var(--font-sans);
  font-size: 0.95rem;
  line-height: 1.6;
  color: var(--color-navy-800);
  box-sizing: border-box;
  overflow-y: auto;
  scrollbar-width: thin;
}
.composer-textarea::placeholder {
  color: var(--color-slate-400);
}

/* ── 底部操作栏 ── */
.composer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-3) var(--space-3);
  gap: var(--space-2);
}
.composer-actions-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.composer-actions-right {
  flex-shrink: 0;
}

/* ── 通用 action 按钮基础 ── */
.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1.5px solid var(--color-slate-200);
  border-radius: var(--radius-full);
  background: var(--color-white);
  color: var(--color-slate-600);
  font-size: 0.8rem;
  font-family: inherit;
  cursor: pointer;
  transition: all var(--transition-fast);
  user-select: none;
  line-height: 1;
  white-space: nowrap;
}
.action-btn:hover:not(:disabled) {
  border-color: var(--color-slate-300);
  color: var(--color-navy-700);
  background: var(--color-slate-50);
}
.action-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* + 上传按钮 */
.action-btn--plus {
  width: 32px;
  height: 32px;
  padding: 0;
  justify-content: center;
  font-size: 1.2rem;
  font-weight: 300;
  color: var(--color-slate-500);
}
.action-btn--plus:hover:not(:disabled) {
  border-color: var(--color-gold-400);
  color: var(--color-gold-600);
  background: var(--color-gold-50);
}

/* 模式切换按钮 */
.action-btn--mode {
  padding: 5px 12px 5px 9px;
  height: 32px;
  color: var(--color-slate-600);
}
.action-btn--mode-active {
  background: var(--color-gold-50);
  border-color: var(--color-gold-300);
  color: var(--color-gold-700);
}
.action-btn--mode-active:hover:not(:disabled) {
  background: var(--color-gold-100);
  border-color: var(--color-gold-400);
}
.mode-icon {
  font-size: 0.75rem;
  opacity: 0.8;
}
.mode-label {
  font-weight: 600;
  font-size: 0.82rem;
}
.mode-chevron {
  font-size: 0.95rem;
  opacity: 0.5;
  margin-left: 1px;
}

/* 审批模式按钮 */
.action-btn--approval {
  padding: 5px 11px;
  height: 32px;
  font-size: 0.78rem;
}
.action-btn--approval-off {
  background: var(--color-gold-50);
  border-color: var(--color-gold-300);
  color: var(--color-gold-700);
}

/* ── 发送按钮 ── */
.send-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-full);
  border: none;
  background: var(--color-gold-500);
  color: var(--color-white);
  font-size: 1.1rem;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-fast);
  box-shadow: 0 2px 8px rgba(234, 179, 8, 0.35);
  line-height: 1;
}
.send-btn:hover:not(:disabled) {
  background: var(--color-gold-600);
  box-shadow: 0 4px 12px rgba(234, 179, 8, 0.45);
  transform: translateY(-1px);
}
.send-btn:disabled {
  background: var(--color-slate-300);
  box-shadow: none;
  cursor: not-allowed;
}

/* ── 中断按钮 ── */
.interrupt-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-full);
  border: none;
  background: var(--color-error);
  color: var(--color-white);
  font-size: 0.9rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-fast);
  box-shadow: 0 2px 8px rgba(239, 68, 68, 0.3);
  line-height: 1;
}
.interrupt-btn:hover {
  opacity: 0.85;
  transform: translateY(-1px);
}

@media (max-width: 768px) {
  .composer { padding: var(--space-2) var(--space-3) var(--space-3); }
  .action-btn--mode .mode-label { font-size: 0.78rem; }
}
</style>
