<template>
  <!-- 待审批：展开卡片 -->
  <div v-if="hasPending" class="approval-card approval-card--pending">
    <div class="approval-header">
      <span class="approval-header-icon">🔒</span>
      <span class="approval-header-title">{{ summaryLabel }}</span>
    </div>

    <div
      v-for="tc in toolCalls"
      :key="tc.id"
      class="approval-tool"
      :class="{
        'approval-tool--approved': tc._resolved === true,
        'approval-tool--rejected': tc._resolved === false,
      }"
    >
      <div class="approval-tool-head">
        <span class="approval-tool-name">🛠 {{ tc.name }}</span>
        <span v-if="tc._resolved === true" class="approval-tool-badge badge-approved">已放行</span>
        <span v-else-if="tc._resolved === false" class="approval-tool-badge badge-rejected">已拒绝</span>
      </div>
      <pre class="approval-tool-params">{{ pretty(tc.input) }}</pre>
      <div v-if="tc._resolved === undefined" class="approval-tool-actions">
        <button class="btn-approve" @click="$emit('approve', block.id, tc.id)">✅ 放行</button>
        <button class="btn-reject" @click="$emit('reject', block.id, tc.id)">❌ 拒绝</button>
      </div>
    </div>

    <!-- 全部批准快捷按钮 -->
    <button
      v-if="hasPending"
      class="approval-approve-all"
      @click="$emit('approve-all', block.id)"
    >全部批准</button>
  </div>

  <!-- 全部已审批 → 折叠成一行 -->
  <div v-else class="approval-card approval-card--done">
    <span class="approval-header-icon">{{ allApproved ? '✅' : '❌' }}</span>
    <span class="approval-header-title">{{ summaryLabel }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ChatBlock } from '../../types'

const props = defineProps<{
  block: ChatBlock
}>()

defineEmits<{
  approve: [blockId: string, toolCallId: string]
  reject: [blockId: string, toolCallId: string]
  'approve-all': [blockId: string]
}>()

interface ToolCallItem {
  id: string
  name: string
  input: unknown
  _resolved?: boolean
}

const toolCalls = computed<ToolCallItem[]>(() => {
  try {
    return JSON.parse(props.block.content)
  } catch {
    return []
  }
})

const hasPending = computed(() => toolCalls.value.some(tc => tc._resolved === undefined))
const allApproved = computed(() => toolCalls.value.length > 0 && toolCalls.value.every(tc => tc._resolved === true))

const summaryLabel = computed(() => {
  const all = toolCalls.value.length
  const done = toolCalls.value.filter(tc => tc._resolved !== undefined).length
  if (done === 0) return `等待审批 (${all})`
  if (done < all) return `审批中 (${done}/${all})`
  const allApproved = toolCalls.value.every(tc => tc._resolved === true)
  if (allApproved) return '✅ 已全部放行'
  const approved = toolCalls.value.filter(tc => tc._resolved === true).length
  const rejected = toolCalls.value.filter(tc => tc._resolved === false).length
  return approved > 0 && rejected > 0
    ? `✅ ${approved}放行 / ${rejected}拒绝`
    : approved > 0 ? `✅ 已全部放行` : `❌ 已全部拒绝`
})

const pretty = (value: unknown) => JSON.stringify(value, null, 2)
</script>

<style scoped>
.approval-card--pending {
  background: #FEF3C7;
  border: 1px solid #F59E0B;
  border-radius: 8px;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.approval-card--done {
  background: #ECFDF5;
  border: 1px solid #6EE7B7;
  border-radius: 8px;
  padding: 6px 10px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #065F46;
}
.approval-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #92400E;
}
.approval-header-icon {
  font-size: 14px;
}
.approval-tool {
  background: #FFFBEB;
  border: 1px solid #FDE68A;
  border-radius: 6px;
  padding: 6px 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.approval-tool--approved {
  border-color: #6EE7B7;
  background: #ECFDF5;
}
.approval-tool--rejected {
  border-color: #FCA5A5;
  background: #FEF2F2;
}
.approval-tool-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}
.approval-tool-name {
  font-size: 12px;
  font-weight: 600;
  color: #1e293b;
}
.approval-tool-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}
.badge-approved {
  background: #D1FAE5;
  color: #065F46;
}
.badge-rejected {
  background: #FEE2E2;
  color: #991B1B;
}
.approval-tool-params {
  font-size: 10px;
  background: #1E293B;
  color: #E2E8F0;
  padding: 4px 6px;
  border-radius: 4px;
  overflow-x: auto;
  max-height: 100px;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}
.approval-tool-actions {
  display: flex;
  gap: 4px;
}
.btn-approve,
.btn-reject {
  flex: 1;
  border: none;
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-approve {
  background: #10B981;
  color: #fff;
}
.btn-approve:hover {
  background: #059669;
}
.btn-reject {
  background: #EF4444;
  color: #fff;
}
.btn-reject:hover {
  background: #DC2626;
}
.approval-approve-all {
  border: 1px dashed #F59E0B;
  background: transparent;
  color: #92400E;
  font-size: 11px;
  font-weight: 600;
  border-radius: 4px;
  padding: 4px 8px;
  cursor: pointer;
  transition: all 0.15s;
}
.approval-approve-all:hover {
  background: #F59E0B;
  color: #fff;
  border-style: solid;
}
</style>
