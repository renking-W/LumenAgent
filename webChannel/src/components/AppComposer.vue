<template>
  <footer class="composer">
    <div class="composer-approval-bar">
      <button
        class="approval-toggle"
        :class="{ 'approval-toggle--on': approvalMode === 'none' }"
        :disabled="!useAgentMode"
        :title="useAgentMode ? '切换审批模式' : '仅 Agent 模式下可用'"
        @click="toggleApprovalMode"
      >
        <span v-if="approvalMode === 'none'" class="approval-toggle-icon">⚡</span>
        <span v-else class="approval-toggle-icon">🔒</span>
        <span class="approval-toggle-text">
          {{ approvalMode === 'none' ? '始终放行' : approvalMode === 'all' ? '全部审批' : '危险审批' }}
        </span>
      </button>
    </div>
    <div class="composer-grid">
      <el-input
        :model-value="prompt"
        @update:model-value="$emit('update:prompt', $event)"
        type="textarea"
        :autosize="{ minRows: 4, maxRows: 10 }"
        placeholder="输入你的问题，支持代码、需求、修复说明..."
        @keydown.enter.exact.prevent="$emit('send')"
        @keydown.ctrl.enter.prevent="insertNewline"
      />
      <div class="composer-side">
        <el-button
          v-if="!sending"
          type="primary"
          size="large"
          @click="$emit('send')"
        >
          发送
        </el-button>
        <el-button
          v-else
          type="danger"
          size="large"
          @click="$emit('interrupt')"
        >
          中断
        </el-button>
      </div>
    </div>
  </footer>
</template>

<script setup lang="ts">
import { nextTick } from 'vue'

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
  send: []
  interrupt: []
}>()

const toggleApprovalMode = () => {
  // 循环切换: dangerous → none → dangerous
  if (props.approvalMode === 'dangerous') {
    emit('update:approval-mode', 'none')
  } else if (props.approvalMode === 'none') {
    emit('update:approval-mode', 'dangerous')
  } else {
    emit('update:approval-mode', 'dangerous')
  }
}

/** 在光标位置插入换行 */
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
  padding: var(--space-4) var(--space-6) var(--space-5);
  border-top: 1px solid var(--color-slate-200);
  background: var(--color-white);
}
.composer-grid {
  display: grid;
  grid-template-columns: 1fr 220px;
  gap: var(--space-4);
  align-items: end;
}
.composer-side {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

/* ── 审批模式切换 ── */
.composer-approval-bar {
  display: flex;
  align-items: center;
  margin-bottom: var(--space-3);
}
.approval-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-full);
  background: var(--color-white);
  color: var(--color-slate-500);
  font-size: 0.78rem;
  cursor: pointer;
  transition: all var(--transition-fast);
  font-family: inherit;
  line-height: 1.4;
  user-select: none;
}
.approval-toggle:hover:not(:disabled) {
  border-color: var(--color-gold-300);
  color: var(--color-gold-600);
}
.approval-toggle:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.approval-toggle--on {
  background: var(--color-gold-50);
  border-color: var(--color-gold-400);
  color: var(--color-gold-700);
}
.approval-toggle-icon {
  font-size: 0.85rem;
}

@media (max-width: 768px) {
  .composer-grid {
    grid-template-columns: 1fr;
  }
  .composer-side {
    flex-direction: row;
    justify-content: flex-end;
  }
}
</style>
