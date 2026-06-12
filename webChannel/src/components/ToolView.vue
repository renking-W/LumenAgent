<template>
  <div class="tool-page">
    <!-- ======== 紧凑顶栏 ======== -->
    <div class="tool-header">
      <div class="tool-header-left">
        <div class="tool-kicker">Agent Tools</div>
        <h2>工具能力总览</h2>
      </div>
      <div class="tool-header-stats">
        <div class="tool-stat">
          <span class="tool-stat-value">{{ tools.length }}</span>
          <span class="tool-stat-label">工具数量</span>
        </div>
        <div class="tool-stat-divider"></div>
        <div class="tool-stat">
          <span class="tool-stat-value" :class="connected ? 'ok' : 'bad'">
            <span class="tool-status-dot" :class="connected ? 'dot-ok' : 'dot-bad'"></span>
            {{ connected ? '正常' : '异常' }}
          </span>
          <span class="tool-stat-label">连接状态</span>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="tools.length === 0" class="empty-state">
      <div class="empty-icon">🛠️</div>
      <h3>暂无可用工具</h3>
      <p>当前没有可用的工具定义，请检查后端服务是否正常运行</p>
    </div>

    <!-- 工具列表 -->
    <div v-else class="tool-grid">
      <article v-for="tool in tools" :key="tool.name" class="tool-card">
        <div class="tool-card-head">
          <div class="tool-card-title-row">
            <h3 class="tool-card-name">{{ tool.name }}</h3>
            <el-tag size="small" effect="light" type="info">Tool</el-tag>
          </div>
          <p class="tool-card-desc">{{ tool.description }}</p>
        </div>
        <details class="tool-card-params">
          <summary class="tool-card-params-summary">
            <span>参数结构</span>
            <span class="tool-card-params-arrow">→</span>
          </summary>
          <div class="tool-card-params-body">
            <pre class="tool-card-params-pre">{{ pretty(tool.parameters) }}</pre>
          </div>
        </details>
        <div class="tool-card-actions">
          <el-button size="small" type="primary" plain @click="showToolDetail(tool)">
            查看详情
          </el-button>
        </div>
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
.tool-page {
  padding: var(--space-5) var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-height: 100%;
}

/* ── 紧凑顶栏 ── */
.tool-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4) var(--space-5);
  background: var(--color-white);
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-2xl);
  box-shadow: var(--shadow-sm);
}
.tool-header-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.tool-kicker {
  font-size: 0.7rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-gold-600);
  font-weight: 600;
}
.tool-header-left h2 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--color-navy-900);
}
.tool-header-stats {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}
.tool-stat {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}
.tool-stat-value {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--color-navy-800);
  display: flex;
  align-items: center;
  gap: 6px;
}
.tool-stat-value.ok { color: var(--color-success); }
.tool-stat-value.bad { color: var(--color-error); }
.tool-stat-label {
  font-size: 0.72rem;
  color: var(--color-slate-400);
}
.tool-stat-divider {
  width: 1px;
  height: 32px;
  background: var(--color-slate-200);
}
.tool-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.dot-ok { background: var(--color-success); }
.dot-bad { background: var(--color-error); }

/* ── 工具网格 ── */
.tool-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: var(--space-4);
}
.tool-card {
  background: var(--color-white);
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-xl);
  padding: var(--space-5);
  box-shadow: var(--shadow-xs);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  transition: all var(--transition-normal);
}
.tool-card:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--color-gold-200);
  transform: translateY(-1px);
}
.tool-card-head {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.tool-card-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.tool-card-name {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-navy-900);
  font-family: var(--font-mono);
}
.tool-card-desc {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.6;
  color: var(--color-slate-500);
}

/* ── 参数结构 ── */
.tool-card-params {
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.tool-card-params-summary {
  cursor: pointer;
  list-style: none;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-2) var(--space-3);
  font-size: 0.82rem;
  font-weight: 500;
  color: var(--color-slate-500);
  background: var(--color-slate-50);
  transition: background var(--transition-fast);
  user-select: none;
}
.tool-card-params-summary:hover {
  background: var(--color-slate-100);
}
.tool-card-params-summary::-webkit-details-marker {
  display: none;
}
.tool-card-params-arrow {
  font-size: 0.8rem;
  transition: transform var(--transition-fast);
}
.tool-card-params[open] .tool-card-params-arrow {
  transform: rotate(90deg);
}
.tool-card-params-body {
  border-top: 1px solid var(--color-slate-200);
}
.tool-card-params-pre {
  margin: 0;
  padding: var(--space-3);
  font-size: 0.78rem;
  line-height: 1.5;
  max-height: 200px;
  overflow: auto;
  background: var(--color-navy-900);
  color: var(--color-slate-200);
  font-family: var(--font-mono);
}

/* ── 操作按钮 ── */
.tool-card-actions {
  display: flex;
  gap: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid var(--color-slate-100);
}

/* ── 弹窗 ── */
.dialog-section { margin-bottom: var(--space-5); }
.dialog-label { font-size: 0.9rem; color: var(--color-navy-900); margin: 0 0 var(--space-2); font-weight: 600; }
.dialog-text { color: var(--color-slate-500); line-height: 1.7; white-space: pre-wrap; }
.dialog-pre {
  background: var(--color-slate-50); padding: var(--space-4); border-radius: var(--radius-lg);
  border: 1px solid var(--color-slate-200); max-height: 360px; overflow: auto;
}

/* ── 空状态 ── */
.empty-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 64px 24px; color: var(--color-slate-400); gap: var(--space-2);
  border: 2px dashed var(--color-slate-200); border-radius: var(--radius-2xl); background: var(--color-white);
}
.empty-icon { font-size: 3rem; }
.empty-state h3 { margin: 0; color: var(--color-slate-500); font-weight: 600; font-size: 1.1rem; }
.empty-state p { margin: 0; font-size: 0.9rem; color: var(--color-slate-400); }
</style>
