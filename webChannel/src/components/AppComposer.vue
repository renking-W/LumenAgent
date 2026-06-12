<template>
  <footer class="composer">
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
  statusText: string
}>()

const emit = defineEmits<{
  'update:prompt': [value: string]
  send: []
  interrupt: []
}>()

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
