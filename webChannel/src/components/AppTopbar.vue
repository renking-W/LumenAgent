<template>
  <header class="topbar">
    <div>
      <h1>{{ pageTitle }}</h1>
      <p>{{ pageSubtitle }}</p>
    </div>
    <div class="topbar-actions">
      <el-switch
        :model-value="useAgentMode"
        @update:model-value="$emit('update:useAgentMode', $event)"
        active-text="Agent"
        inactive-text="Simple"
      />
      <el-button
        v-if="activeView === 'chat'"
        type="primary"
        @click="$emit('scroll-to-bottom')"
      >
        定位到底部
      </el-button>
      <el-button v-else type="primary" plain @click="$emit('refresh')">
        刷新数据
      </el-button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  activeView: 'chat' | 'tools' | 'skills' | 'memories'
  useAgentMode: boolean
}>()

defineEmits<{
  'update:useAgentMode': [value: boolean]
  'scroll-to-bottom': []
  refresh: []
}>()

const pageTitle = computed(() => {
  if (props.activeView === 'tools') return 'Tools Library'
  if (props.activeView === 'skills') return 'Skills Library'
  if (props.activeView === 'memories') return 'Memory Files'
  return 'Agent Console'
})

const pageSubtitle = computed(() => {
  if (props.activeView === 'tools') return '浏览 Agent 可调用的工具定义、参数结构与说明。'
  if (props.activeView === 'skills') return '浏览所有 SKILL 的可用状态、环境依赖与位置。'
  if (props.activeView === 'memories') return '浏览所有记忆文件的内容与详情，包括长期记忆和每日记忆。'
  return '支持 SSE 实时渲染思考、工具调用、工具结果与正文内容。'
})
</script>

<style scoped>
.topbar {
  display: flex; justify-content: space-between; align-items: center;
  gap: 16px; padding: 20px 24px;
  border-bottom: 1px solid #e5e7eb; background: #ffffff;
}
.topbar h1 { margin: 0; font-size: 1.6rem; color: #111827; }
.topbar p { margin: 6px 0 0; color: #6b7280; }
.topbar-actions { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
</style>
