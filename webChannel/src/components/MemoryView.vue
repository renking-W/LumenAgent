<template>
  <div class="catalog-pane">
    <div class="hero-card">
      <div>
        <div class="hero-kicker">Agent Memory</div>
        <h2>记忆文件总览</h2>
      </div>
      <div class="hero-stats">
        <div class="stat-box">
          <span class="stat-label">记忆文件</span>
          <span class="stat-value">{{ memories.length }}</span>
        </div>
        <div class="stat-box">
          <span class="stat-label">长期记忆</span>
          <span class="stat-value">{{ longTermCount }}</span>
        </div>
        <div class="stat-box">
          <span class="stat-label">每日记忆</span>
          <span class="stat-value">{{ dailyCount }}</span>
        </div>
      </div>
    </div>

    <div v-if="!memories.length" class="empty-state">
      <p>暂无记忆文件</p>
    </div>

    <div v-else class="grid-cards">
      <article
        v-for="item in memories"
        :key="item.file_name"
        class="card"
        :class="{ 'card--long-term': item.type === 'long_term' }"
      >
        <div class="card-top">
          <div>
            <h3>
              {{ item.type === 'long_term' ? '📌' : '📅' }}
              {{ item.file_name }}
            </h3>
            <p class="card-desc">
              {{ item.type === 'long_term' ? '长期记忆 — MEMORY.md 摘要索引' : '每日记忆 — 自动记录的关键信息' }}
            </p>
          </div>
          <div class="card-top-actions">
            <el-tag
              :type="item.type === 'long_term' ? 'warning' : 'info'"
              effect="light"
            >
              {{ item.type === 'long_term' ? '长期' : '每日' }}
            </el-tag>
            <el-button size="small" type="primary" plain @click="showMemoryDetail(item)">
              查看详情
            </el-button>
          </div>
        </div>
        <div class="meta-row">
          <span class="meta-key">文件名</span>
          <span class="meta-val">{{ item.file_name }}</span>
        </div>
        <div class="meta-row">
          <span class="meta-key">文件类型</span>
          <span class="meta-val">{{ item.type === 'long_term' ? '长期记忆' : '每日记忆' }}</span>
        </div>
        <div class="preview-box">
          <span class="meta-key">内容预览</span>
          <p class="preview-text">{{ preview(item.content) }}</p>
        </div>
      </article>
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

const longTermCount = computed(() =>
  props.memories.filter((item) => item.type === 'long_term').length
)

const dailyCount = computed(() =>
  props.memories.filter((item) => item.type === 'daily').length
)

const preview = (content: string) => {
  if (!content || typeof content !== 'string') return ''
  // 取前 120 个字符作为预览，去除 frontmatter 和空行
  const cleaned = content
    .replace(/^---[\s\S]*?---\n*/m, '')  // remove frontmatter
    .replace(/^[#]+ .+\n*/gm, '')          // remove headings
    .replace(/\n{2,}/g, '\n')              // collapse blank lines
    .trim()
  if (!cleaned) return '(内容为空)'
  return cleaned.slice(0, 120) + (cleaned.length > 120 ? '...' : '')
}

const memoryDialogVisible = ref(false)
const selectedMemory = ref<MemoryFileItem | null>(null)

const showMemoryDetail = (item: MemoryFileItem) => {
  selectedMemory.value = item
  memoryDialogVisible.value = true
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
  display: grid; grid-template-columns: repeat(3, minmax(100px, 1fr));
  gap: 12px; min-width: 320px;
}
.stat-box {
  border: 1px solid #e5e7eb; border-radius: 18px; padding: 14px;
  background: #f8fafc; display: flex; flex-direction: column; gap: 6px;
}
.stat-label { font-size: 0.8rem; color: #6b7280; }
.stat-value { font-size: 1.2rem; font-weight: 700; color: #111827; }
.empty-state {
  display: flex; align-items: center; justify-content: center;
  padding: 48px; color: #9ca3af; font-size: 1rem;
  border: 2px dashed #e5e7eb; border-radius: 24px; background: #ffffff;
}
.grid-cards { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.card {
  background: #ffffff; border: 1px solid #e5e7eb; border-radius: 22px;
  padding: 18px; box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
  display: flex; flex-direction: column; gap: 14px;
  height: 320px; overflow: hidden;
}
.card--long-term {
  border-color: #fde68a;
  background: linear-gradient(135deg, #fffbeb 0%, #ffffff 100%);
}
.card-top {
  display: flex; justify-content: space-between; gap: 12px;
  align-items: start; flex-shrink: 0; overflow: hidden;
}
.card h3 { margin: 0; color: #111827; font-size: 1rem; }
.card-desc {
  margin: 8px 0 0; color: #6b7280; line-height: 1.6;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; line-clamp: 2;
}
.card-top > div { min-width: 0; overflow: hidden; }
.card-top-actions { display: flex; flex-direction: column; align-items: flex-end; gap: 8px; flex-shrink: 0; }
.meta-row { display: flex; flex-direction: column; gap: 4px; }
.meta-key { font-size: 0.8rem; color: #6b7280; }
.meta-val { color: #111827; word-break: break-all; line-height: 1.5; }
.preview-box {
  display: flex; flex-direction: column; gap: 4px;
  border: 1px solid #e5e7eb; border-radius: 14px; padding: 10px 12px;
  background: #f9fafb; flex: 1; min-height: 0; overflow: hidden;
}
.preview-text {
  margin: 0; color: #6b7280; font-size: 0.85rem; line-height: 1.6;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
  overflow: hidden; line-clamp: 3;
}
/* ── Dialog ── */
.dialog-section { margin-bottom: 20px; }
.dialog-label { font-size: 0.9rem; color: #111827; margin: 0 0 8px; font-weight: 600; }
.dialog-text { color: #6b7280; line-height: 1.7; }
.dialog-content-box {
  border: 1px solid #e5e7eb; border-radius: 14px; overflow: hidden;
  background: #f8fafc;
}
.dialog-pre {
  margin: 0; padding: 16px;
  max-height: 480px; overflow: auto;
  font-size: 0.85rem; line-height: 1.7;
  white-space: pre-wrap; word-break: break-word;
  color: #1f2937;
}
</style>
