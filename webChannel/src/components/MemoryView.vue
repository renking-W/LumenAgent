<template>
  <div class="memory-page">
    <!-- ======== 紧凑顶栏 ======== -->
    <div class="memory-header">
      <div class="memory-header-left">
        <div class="memory-kicker">Agent Memory</div>
        <h2>记忆文件总览</h2>
      </div>
      <div class="memory-header-right">
        <div class="memory-stats">
          <div class="memory-stat">
            <span class="memory-stat-value">{{ memories.length }}</span>
            <span class="memory-stat-label">文件总数</span>
          </div>
          <span class="memory-stat-dot"></span>
          <div class="memory-stat">
            <span class="memory-stat-value" style="color: var(--color-gold-600)">{{ longTermCount }}</span>
            <span class="memory-stat-label">长期</span>
          </div>
          <span class="memory-stat-dot"></span>
          <div class="memory-stat">
            <span class="memory-stat-value">{{ dailyCount }}</span>
            <span class="memory-stat-label">每日</span>
          </div>
        </div>
        <el-button
          size="small"
          :loading="reindexing"
          :disabled="reindexing"
          @click="handleReindex"
        >
          {{ reindexing ? '重索引中...' : '⟳ 重索引' }}
        </el-button>
      </div>
    </div>

    <div v-if="reindexResult" class="reindex-result" :class="reindexResult.type">
      {{ reindexResult.message }}
    </div>

    <!-- 空状态 -->
    <div v-if="!memories.length" class="empty-state">
      <div class="empty-icon">🧠</div>
      <h3>暂无记忆文件</h3>
      <p>AI 尚未记录任何记忆，持续使用后记忆文件将自动生成</p>
    </div>

    <!-- ======== 左右分栏 ======== -->
    <div v-else class="memory-split">
      <!-- 左侧：文件列表 -->
      <aside class="memory-list">
        <!-- 长期记忆 -->
        <div v-if="longTermMemories.length > 0" class="memory-group">
          <div class="memory-group-header">
            <span class="memory-group-icon">📌</span>
            <span class="memory-group-title">长期记忆</span>
            <span class="memory-group-count">{{ longTermMemories.length }}</span>
          </div>
          <div class="memory-group-items">
            <button
              v-for="item in longTermMemories"
              :key="item.file_name"
              class="memory-item"
              :class="{ 'memory-item--active': selectedMemory?.file_name === item.file_name }"
              @click="selectMemory(item)"
            >
              <span class="memory-item-name">{{ item.file_name }}</span>
              <span class="memory-item-preview">{{ preview(item.content) }}</span>
            </button>
          </div>
        </div>

        <!-- 每日记忆 -->
        <div v-if="dailyMemories.length > 0" class="memory-group">
          <div class="memory-group-header">
            <span class="memory-group-icon">📅</span>
            <span class="memory-group-title">每日记忆</span>
            <span class="memory-group-count">{{ dailyMemories.length }}</span>
          </div>
          <div class="memory-group-items">
            <button
              v-for="item in dailyMemories"
              :key="item.file_name"
              class="memory-item"
              :class="{ 'memory-item--active': selectedMemory?.file_name === item.file_name }"
              @click="selectMemory(item)"
            >
              <span class="memory-item-name">{{ item.file_name }}</span>
              <span class="memory-item-preview">{{ preview(item.content) }}</span>
            </button>
          </div>
        </div>
      </aside>

      <!-- 右侧：内容预览 -->
      <main class="memory-preview">
        <div v-if="!selectedMemory" class="memory-preview-empty">
          <span class="memory-preview-icon">📄</span>
          <p>从左侧选择一个记忆文件查看内容</p>
        </div>
        <template v-else>
          <div class="memory-preview-header">
            <div class="memory-preview-title-row">
              <span class="memory-preview-icon-small">
                {{ selectedMemory.type === 'long_term' ? '📌' : '📅' }}
              </span>
              <h3 class="memory-preview-filename">{{ selectedMemory.file_name }}</h3>
              <el-tag
                :type="selectedMemory.type === 'long_term' ? 'warning' : 'info'"
                effect="light"
                size="small"
              >
                {{ selectedMemory.type === 'long_term' ? '长期记忆' : '每日记忆' }}
              </el-tag>
              <el-button size="small" text type="primary" @click="showMemoryDetail(selectedMemory)">详情</el-button>
            </div>
          </div>
          <div class="memory-preview-content">
            <pre class="memory-preview-text">{{ selectedMemory.content }}</pre>
          </div>
        </template>
      </main>
    </div>

    <el-dialog
      v-model="memoryDialogVisible"
      :title="selectedMemory?.type === 'long_term' ? '📌 ' : '📅 ' + (selectedMemory?.file_name || '记忆详情')"
      width="720px"
      destroy-on-close
      class="memory-dialog"
    >
      <template v-if="selectedMemory">
        <div class="dialog-section">
          <h4 class="dialog-label">文件名</h4>
          <p class="dialog-text">{{ selectedMemory.file_name }}</p>
        </div>
        <div class="dialog-section">
          <h4 class="dialog-label">文件类型</h4>
          <el-tag
            :type="selectedMemory.type === 'long_term' ? 'warning' : 'info'"
            effect="light"
          >
            {{ selectedMemory.type === 'long_term' ? '长期记忆 (Long-term)' : '每日记忆 (Daily)' }}
          </el-tag>
        </div>
        <div class="dialog-section">
          <h4 class="dialog-label">完整内容</h4>
          <div class="dialog-content-box">
            <pre class="dialog-pre">{{ selectedMemory.content }}</pre>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { MemoryFileItem } from '../types'

const props = defineProps<{
  memories: MemoryFileItem[]
}>()

const longTermMemories = computed(() => props.memories.filter((item) => item.type === 'long_term'))
const dailyMemories = computed(() => props.memories.filter((item) => item.type === 'daily'))
const longTermCount = computed(() => longTermMemories.value.length)
const dailyCount = computed(() => dailyMemories.value.length)

const preview = (content: string) => {
  if (!content || typeof content !== 'string') return ''
  const cleaned = content
    .replace(/^---[\s\S]*?---\n*/m, '')
    .replace(/^[#]+ .+\n*/gm, '')
    .replace(/\n{2,}/g, '\n')
    .trim()
  if (!cleaned) return '(内容为空)'
  return cleaned.slice(0, 120) + (cleaned.length > 120 ? '...' : '')
}

const memoryDialogVisible = ref(false)
const selectedMemory = ref<MemoryFileItem | null>(null)
const reindexing = ref(false)
const reindexResult = ref<{ type: string; message: string } | null>(null)

const showMemoryDetail = (item: MemoryFileItem) => {
  selectedMemory.value = item
  memoryDialogVisible.value = true
}

const selectMemory = (item: MemoryFileItem) => {
  selectedMemory.value = item
}

const handleReindex = async () => {
  reindexing.value = true
  reindexResult.value = null
  try {
    const res = await fetch('/v1/memories/reindex', { method: 'POST' })
    if (res.ok) {
      const data = await res.json()
      reindexResult.value = { type: 'success', message: data.message || '记忆重索引完成' }
    } else {
      const err = await res.text()
      reindexResult.value = { type: 'error', message: `重索引失败: ${err}` }
    }
  } catch {
    reindexResult.value = { type: 'error', message: '网络错误，重索引失败' }
  } finally {
    reindexing.value = false
  }
}
</script>

<style scoped>
.memory-page {
  padding: var(--space-5) var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-height: 100%;
}

/* ── 紧凑顶栏 ── */
.memory-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4) var(--space-5);
  background: var(--color-white);
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-2xl);
  box-shadow: var(--shadow-sm);
}
.memory-header-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.memory-kicker {
  font-size: 0.7rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-gold-600);
  font-weight: 600;
}
.memory-header-left h2 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--color-navy-900);
}
.memory-header-right {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}
.memory-stats {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.memory-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
}
.memory-stat-value {
  font-size: 1rem;
  font-weight: 700;
  color: var(--color-navy-800);
}
.memory-stat-label {
  font-size: 0.68rem;
  color: var(--color-slate-400);
}
.memory-stat-dot {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: var(--color-slate-300);
}

/* ── 重索引结果 ── */
.reindex-result {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  font-size: 0.9rem;
  line-height: 1.5;
}
.reindex-result.success {
  background: var(--color-success-bg);
  border: 1px solid #A7F3D0;
  color: #065F46;
}
.reindex-result.error {
  background: var(--color-error-bg);
  border: 1px solid #FECACA;
  color: #991B1B;
}

/* ── 左右分栏 ── */
.memory-split {
  flex: 1;
  display: flex;
  gap: var(--space-4);
  min-height: 0;
}

/* ── 左侧文件列表 ── */
.memory-list {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  overflow-y: auto;
}
.memory-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.memory-group-header {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  font-size: 0.82rem;
  color: var(--color-navy-700);
  font-weight: 600;
}
.memory-group-icon {
  font-size: 0.9rem;
}
.memory-group-title {
  flex: 1;
}
.memory-group-count {
  font-size: 0.72rem;
  color: var(--color-slate-400);
  background: var(--color-slate-100);
  padding: 0 6px;
  border-radius: var(--radius-full);
}
.memory-group-items {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.memory-item {
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-2) var(--space-3);
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  background: transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
  width: 100%;
}
.memory-item:hover {
  background: var(--color-slate-50);
  border-color: var(--color-slate-200);
}
.memory-item--active {
  background: var(--color-gold-50) !important;
  border-color: var(--color-gold-200) !important;
}
.memory-item-name {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--color-navy-800);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.memory-item--active .memory-item-name {
  color: var(--color-gold-700);
}
.memory-item-preview {
  font-size: 0.75rem;
  color: var(--color-slate-400);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── 右侧内容预览 ── */
.memory-preview {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--color-white);
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-xl);
  overflow: hidden;
  min-width: 0;
}
.memory-preview-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  color: var(--color-slate-400);
}
.memory-preview-icon {
  font-size: 2.5rem;
  opacity: 0.5;
}
.memory-preview-empty p {
  margin: 0;
  font-size: 0.9rem;
}
.memory-preview-header {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-slate-100);
  background: var(--color-slate-50);
}
.memory-preview-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.memory-preview-icon-small {
  font-size: 1.1rem;
}
.memory-preview-filename {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--color-navy-900);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.memory-preview-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4);
}
.memory-preview-text {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--color-navy-700);
  font-family: var(--font-mono);
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

/* ── 弹窗 ── */
.dialog-section { margin-bottom: var(--space-5); }
.dialog-label { font-size: 0.9rem; color: var(--color-navy-900); margin: 0 0 var(--space-2); font-weight: 600; }
.dialog-text { color: var(--color-slate-500); line-height: 1.7; }
.dialog-content-box {
  border: 1px solid var(--color-slate-200); border-radius: var(--radius-lg); overflow: hidden;
  background: var(--color-slate-50);
}
.dialog-pre {
  margin: 0; padding: var(--space-4);
  max-height: 480px; overflow: auto;
  font-size: 0.85rem; line-height: 1.7;
  white-space: pre-wrap; word-break: break-word;
  color: var(--color-navy-800);
}
</style>
