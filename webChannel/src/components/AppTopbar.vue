<template>
  <header class="topbar">
    <div>
      <h1>{{ pageTitle }}</h1>
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
      <el-button plain @click="emit('open-api-keys')">
        🔑 API Key
      </el-button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  activeView: 'chat' | 'tools' | 'skills' | 'memories' | 'mcp' | 'vm' | 'config' | 'knowledge' | 'scheduler' | 'logs'
  useAgentMode: boolean
}>()

const emit = defineEmits<{
  'update:useAgentMode': [value: boolean]
  'scroll-to-bottom': []
  refresh: []
  'open-api-keys': []
}>()

const pageTitle = computed(() => {
  if (props.activeView === 'tools') return 'Tools Library'
  if (props.activeView === 'skills') return 'Skills Library'
  if (props.activeView === 'memories') return 'Memory Files'
  if (props.activeView === 'mcp') return 'MCP Servers'
  if (props.activeView === 'vm') return 'Virtual Machines'
  if (props.activeView === 'config') return 'System Config'
  if (props.activeView === 'knowledge') return 'Knowledge Base'
  if (props.activeView === 'scheduler') return 'Scheduled Tasks'
  if (props.activeView === 'logs') return 'System Logs'
  return 'Agent Console'
})

const pageSubtitle = computed(() => {
  if (props.activeView === 'tools') return '浏览 Agent 可调用的工具定义、参数结构与说明。'
  if (props.activeView === 'skills') return '浏览所有 SKILL 的可用状态、环境依赖与位置。'
  if (props.activeView === 'memories') return '浏览所有记忆文件的内容与详情，包括长期记忆和每日记忆。'
  if (props.activeView === 'mcp') return '管理 MCP Server 连接配置，新增、编辑、删除与连通性测试。'
  if (props.activeView === 'vm') return '管理 SSH 虚拟机连接，注册、连接、执行命令与查看终端日志。'
  if (props.activeView === 'config') return '查看和编辑系统运行时配置，修改后即时热生效。'
  if (props.activeView === 'knowledge') return '管理知识文档，支持入库文本/文件、检索切片、查看文档详情与重建索引。'
  if (props.activeView === 'scheduler') return '管理 AI 定时任务，支持 cron / interval / date 三种触发模式。'
  return '支持 SSE 实时渲染思考、工具调用、工具结果与正文内容。'
})
</script>

<style scoped>
.topbar {
  display: flex; justify-content: space-between; align-items: center;
  gap: var(--space-4); padding: 0 var(--space-6);
  border-bottom: 1px solid var(--color-slate-200);
  background: var(--color-white);
  min-height: 52px;
}
.topbar h1 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-navy-800);
  letter-spacing: -0.01em;
}
.topbar-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}
</style>
