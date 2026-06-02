<template>
  <footer class="composer">
    <div class="composer-grid">
      <el-input
        :model-value="prompt"
        @update:model-value="$emit('update:prompt', $event)"
        type="textarea"
        :autosize="{ minRows: 4, maxRows: 10 }"
        placeholder="输入你的问题，支持代码、需求、修复说明..."
        @keydown.enter.prevent="$emit('send')"
        @keydown.ctrl.enter.prevent="$emit('send')"
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
defineProps<{
  prompt: string
  sending: boolean
  useAgentMode: boolean
  statusText: string
}>()

defineEmits<{
  'update:prompt': [value: string]
  send: []
  interrupt: []
}>()
</script>

<style scoped>
.composer {
  padding: 18px 24px 24px;
  border-top: 1px solid #e5e7eb; background: #ffffff;
}
.composer-grid {
  display: grid; grid-template-columns: 1fr 260px;
  gap: 16px; align-items: end;
}
.composer-side { display: flex; flex-direction: column; gap: 10px; }

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
