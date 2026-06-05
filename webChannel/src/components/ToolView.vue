<template>
  <div class="catalog-pane">
    <div class="hero-card">
      <div>
        <div class="hero-kicker">Agent Tools</div>
        <h2>工具能力总览</h2>
      </div>
      <div class="hero-stats">
        <div class="stat-box">
          <span class="stat-label">工具数量</span>
          <span class="stat-value">{{ tools.length }}</span>
        </div>
        <div class="stat-box">
          <span class="stat-label">连接状态</span>
          <span class="stat-value" :class="connected ? 'ok' : 'bad'">
            {{ connected ? '正常' : '异常' }}
          </span>
        </div>
      </div>
    </div>

    <div class="grid-cards">
      <article v-for="tool in tools" :key="tool.name" class="card">
        <div class="card-top">
          <div>
            <h3>{{ tool.name }}</h3>
            <p>{{ tool.description }}</p>
          </div>
          <div class="card-top-actions">
            <el-tag type="info" effect="light">Tool</el-tag>
            <el-button size="small" type="primary" plain @click="showToolDetail(tool)">
              查看详情
            </el-button>
          </div>
        </div>
        <details class="schema-box">
          <summary>查看参数结构</summary>
          <pre>{{ pretty(tool.parameters) }}</pre>
        </details>
      </article>
    </div>

    <el-dialog
      v-model="toolDialogVisible"
      :title="selectedTool?.name || '工具详情'"
      width="640px"
      destroy-on-close
    >
      <template v-if="selectedTool">
        <div class="dialog-section">
          <h4 class="dialog-label">完整描述</h4>
          <p class="dialog-text">{{ selectedTool.description }}</p>
        </div>
        <div class="dialog-section">
          <h4 class="dialog-label">参数结构 (Parameters)</h4>
          <pre class="dialog-pre">{{ pretty(selectedTool.parameters) }}</pre>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { ToolInfo } from '../types'

defineProps<{
  tools: ToolInfo[]
  connected: boolean
}>()

const toolDialogVisible = ref(false)
const selectedTool = ref<ToolInfo | null>(null)

const pretty = (value: unknown) => JSON.stringify(value, null, 2)

const showToolDetail = (tool: ToolInfo) => {
  selectedTool.value = tool
  toolDialogVisible.value = true
}
</script>

<style scoped>
.catalog-pane {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100%;
}
.hero-card {
  background: #ffffff; border: 1px solid #e5e7eb; border-radius: 24px;
  padding: 22px; display: flex; justify-content: space-between;
  gap: 16px; box-shadow: 0 12px 30px rgba(15, 23, 42, 0.05);
}
.hero-kicker {
  font-size: 0.8rem; letter-spacing: 0.12em; text-transform: uppercase;
  color: #2563eb; margin-bottom: 6px;
}
.hero-card h2 { margin: 0; color: #111827; }
.hero-card p { margin: 8px 0 0; color: #6b7280; }
.hero-stats {
  display: grid; grid-template-columns: repeat(2, minmax(120px, 1fr));
  gap: 12px; min-width: 260px;
}
.stat-box {
  border: 1px solid #e5e7eb; border-radius: 18px; padding: 14px;
  background: #f8fafc; display: flex; flex-direction: column; gap: 6px;
}
.stat-label { font-size: 0.8rem; color: #6b7280; }
.stat-value { font-size: 1.2rem; font-weight: 700; color: #111827; }
.stat-value.ok { color: #059669; }
.stat-value.bad { color: #dc2626; }
.grid-cards { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.card {
  background: #ffffff; border: 1px solid #e5e7eb; border-radius: 22px;
  padding: 18px; box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
  display: flex; flex-direction: column; gap: 14px;
  height: 320px; overflow: hidden;
}
.card-top {
  display: flex; justify-content: space-between; gap: 12px;
  align-items: start; flex-shrink: 0; overflow: hidden;
}
.card h3 { margin: 0; color: #111827; font-size: 1rem; }
.card p {
  margin: 8px 0 0; color: #6b7280; line-height: 1.6;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
  overflow: hidden; line-clamp: 3;
}
.card-top > div { min-width: 0; overflow: hidden; }
.card-top-actions { display: flex; flex-direction: column; align-items: flex-end; gap: 8px; flex-shrink: 0; }
.schema-box { border: 1px solid #e5e7eb; border-radius: 16px; flex-shrink: 0; }
.schema-box summary {
  cursor: pointer; padding: 12px 14px; font-weight: 600;
  color: #111827; background: #f8fafc;
}
.schema-box pre {
  padding: 12px 14px; background: #ffffff; margin: 0;
  max-height: 220px; overflow: auto;
}
.dialog-section { margin-bottom: 20px; }
.dialog-label { font-size: 0.9rem; color: #111827; margin: 0 0 8px; font-weight: 600; }
.dialog-text { color: #6b7280; line-height: 1.7; white-space: pre-wrap; }
.dialog-pre {
  background: #f8fafc; padding: 14px; border-radius: 12px;
  border: 1px solid #e5e7eb; max-height: 360px; overflow: auto;
}
</style>
