<template>
  <div class="log-page">
    <div class="log-header">
      <div class="log-header-left">
        <div class="log-kicker">System Logs</div>
        <h2>日志监控</h2>
      </div>
      <div class="log-header-actions">
        <div class="log-header-filters">
          <el-select v-model="levelFilter" size="small" placeholder="日志级别" clearable style="width: 110px" @change="resetAndFetch">
            <el-option label="全部" value="" />
            <el-option label="INFO" value="INFO" />
            <el-option label="WARNING" value="WARNING" />
            <el-option label="ERROR" value="ERROR" />
          </el-select>
          <el-input v-model="keywordFilter" size="small" placeholder="搜索关键字…" clearable style="width: 160px" @keydown.enter="resetAndFetch" @clear="resetAndFetch" />
        </div>
        <div class="log-header-buttons">
          <el-button size="small" plain @click="toggleAutoRefresh">
            {{ autoRefresh ? '⏸ 暂停' : '▶ 自动刷新' }}
          </el-button>
          <el-button size="small" plain @click="resetAndFetch" :loading="loading">⟳</el-button>
        </div>
      </div>
    </div>

    <div class="log-file-bar">
      <span class="log-file-label">日志文件：</span>
      <el-radio-group v-model="selectedFile" size="small" @change="resetAndFetch">
        <el-radio-button v-for="f in logFiles" :key="f" :value="f">{{ f }}</el-radio-button>
      </el-radio-group>
      <span class="log-file-total">{{ totalLines }} 行 · 已显示 {{ logs.length }} 条</span>
    </div>

    <div class="log-container" ref="logContainerRef" @scroll="onScroll">
      <div v-if="loading && logs.length === 0" class="log-empty">加载中...</div>
      <div v-else-if="logs.length === 0" class="log-empty">
        <div class="log-empty-icon">📋</div>
        <h3>暂无日志</h3>
        <p>{{ errorMessage || '没有匹配的日志条目' }}</p>
      </div>
      <template v-else>
        <!-- 顶部加载更多指示器 -->
        <div v-if="isLoadingMore" class="log-load-more">加载更早的日志...</div>
        <div v-else-if="!hasMore && logs.length > 0" class="log-load-more log-load-end">已到达全部日志开头</div>

        <div class="log-entries">
          <div
            v-for="(entry, idx) in logs"
            :key="idx"
            class="log-line"
            :class="'log-level--' + entry.level.toLowerCase()"
          >
            <span class="log-line-time">{{ entry.timestamp }}</span>
            <span class="log-line-level" :class="'log-level-tag--' + entry.level.toLowerCase()">{{ entry.level }}</span>
            <span class="log-line-msg" v-html="highlight(entry.message)"></span>
          </div>
        </div>
      </template>
    </div>

    <div class="log-statusbar">
      <span>{{ logs.length }} 条日志</span>
      <span v-if="autoRefresh" class="log-statusbar-live">● {{ refreshInterval }}s 自动刷新</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, onUnmounted } from 'vue'

interface LogEntry {
  timestamp: string
  level: string
  message: string
}

interface LogResponse {
  logs: LogEntry[]
  total_lines: number
  log_files: string[]
}

const PAGE_SIZE = 100

const loading = ref(false)
const isLoadingMore = ref(false)
const logs = ref<LogEntry[]>([])
const logFiles = ref<string[]>(['agent.log'])
const selectedFile = ref('agent.log')
const totalLines = ref(0)
const errorMessage = ref('')
const levelFilter = ref('')
const keywordFilter = ref('')
const autoRefresh = ref(true)
const hasMore = ref(true)
const offset = ref(0)
const refreshInterval = 2
let refreshTimer: ReturnType<typeof setInterval> | null = null
let loadingMoreLock = false

const logContainerRef = ref<HTMLElement | null>(null)

/** 高亮消息中的关键字 */
const highlight = (msg: string): string => {
  const escaped = msg.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  if (!keywordFilter.value) return escaped
  try {
    const pattern = keywordFilter.value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const regex = new RegExp(`(${pattern})`, 'gi')
    return escaped.replace(regex, '<mark class="log-highlight">$1</mark>')
  } catch {
    return escaped
  }
}

const buildParams = (offs: number) => {
  const params = new URLSearchParams()
  params.set('lines', String(PAGE_SIZE))
  params.set('offset', String(offs))
  params.set('file', selectedFile.value)
  if (levelFilter.value) params.set('level', levelFilter.value)
  if (keywordFilter.value) params.set('keyword', keywordFilter.value)
  return params
}

/** 重置并加载最新日志（初始加载 / 刷新 / 切换文件/筛选） */
const resetAndFetch = async () => {
  stopAutoRefreshInternal()
  offset.value = 0
  hasMore.value = true
  await doFetch(true)
  scrollToBottom()
  if (autoRefresh.value) startRefreshTimer()
}

/** 加载更多旧日志（往上滚动触发） */
const loadMore = async () => {
  if (!hasMore.value || loadingMoreLock) return
  loadingMoreLock = true
  isLoadingMore.value = true

  const container = logContainerRef.value
  const prevHeight = container?.scrollHeight ?? 0

  try {
    const res = await fetch(`/v1/logs?${buildParams(offset.value)}`)
    if (res.ok) {
      const data: LogResponse = await res.json()
      // append 到现有日志末尾（显示上在顶部，因为日志是正序排列的）
      logs.value = [...logs.value, ...data.logs]
      offset.value += data.logs.length
      hasMore.value = data.logs.length === PAGE_SIZE
      totalLines.value = data.total_lines
      if (data.log_files?.length) {
        logFiles.value = data.log_files
      }
    }
  } catch {
    // 静默失败
  } finally {
    isLoadingMore.value = false
    loadingMoreLock = false
  }

  // 保持滚动位置：新内容在上方，原来的内容应该保持在视野中
  if (container) {
    await nextTick()
    container.scrollTop = container.scrollHeight - prevHeight
  }
}

/** 核心 fetch：从后端获取日志，后端返回 newest-first */
const doFetch = async (reset: boolean) => {
  if (reset) loading.value = true
  errorMessage.value = ''
  try {
    const res = await fetch(`/v1/logs?${buildParams(reset ? 0 : offset.value)}`)
    if (res.ok) {
      const data: LogResponse = await res.json()
      // 后端返回 newest-first → 反转成 oldest-first（最新在底部）
      const reversed = data.logs.reverse()
      if (reset) {
        logs.value = reversed
        offset.value = data.logs.length
      }
      hasMore.value = data.logs.length === PAGE_SIZE
      totalLines.value = data.total_lines
      if (data.log_files?.length) {
        logFiles.value = data.log_files
      }
    } else {
      const text = await res.text()
      errorMessage.value = `请求失败: ${text}`
      if (reset) logs.value = []
    }
  } catch {
    errorMessage.value = '无法连接到后端，请确认服务是否运行'
    if (reset) logs.value = []
  } finally {
    if (reset) loading.value = false
  }
}

const scrollToBottom = () => {
  const container = logContainerRef.value
  if (container) {
    nextTick(() => {
      container.scrollTop = container.scrollHeight
    })
  }
}

const SCROLL_TOP_THRESHOLD = 60
let lastScrollTop = 0

const onScroll = () => {
  const container = logContainerRef.value
  if (!container || isLoadingMore.value || !hasMore.value) return

  // 往上滚到顶部附近 → 加载更早日志
  if (container.scrollTop < SCROLL_TOP_THRESHOLD) {
    loadMore()
  }
}

const toggleAutoRefresh = () => {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) {
    resetAndFetch()
  } else {
    stopAutoRefreshInternal()
  }
}

const startRefreshTimer = () => {
  if (refreshTimer) clearInterval(refreshTimer)
  refreshTimer = setInterval(async () => {
    // 自动刷新：重新加载最新日志，保持当前滚动位置
    offset.value = 0
    await doFetch(true)
  }, refreshInterval * 1000)
}

const stopAutoRefreshInternal = () => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

const stopAutoRefresh = () => {
  stopAutoRefreshInternal()
  autoRefresh.value = false
}

onMounted(() => {
  resetAndFetch()
})

onUnmounted(stopAutoRefresh)
</script>

<style scoped>
.log-page {
  padding: var(--space-5) var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  min-height: 100%;
  height: 100%;
}

/* ── 紧凑顶栏 ── */
.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
  background: var(--color-white);
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-2xl);
  box-shadow: var(--shadow-sm);
}
.log-header-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.log-kicker {
  font-size: 0.7rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-gold-600);
  font-weight: 600;
}
.log-header-left h2 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--color-navy-900);
}
.log-header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.log-header-filters {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}
.log-header-buttons {
  display: flex;
  gap: var(--space-2);
}

/* ── 文件选择栏 ── */
.log-file-bar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  background: var(--color-white);
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
  flex-wrap: wrap;
}
.log-file-label {
  font-size: 0.82rem;
  color: var(--color-slate-500);
  font-weight: 500;
  white-space: nowrap;
}
.log-file-total {
  font-size: 0.78rem;
  color: var(--color-slate-400);
  margin-left: auto;
}

/* ── 日志容器 ── */
.log-container {
  flex: 1;
  background: var(--color-navy-900);
  border: 1px solid var(--color-navy-700);
  border-radius: var(--radius-xl);
  overflow-y: auto;
  min-height: 0;
  font-family: var(--font-mono);
  font-size: 0.82rem;
  line-height: 1.6;
}
.log-entries {
  display: flex;
  flex-direction: column;
}
.log-line {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-4);
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
  transition: background var(--transition-fast);
}
.log-line:hover {
  background: rgba(255, 255, 255, 0.03);
}
.log-line-time {
  color: var(--color-slate-500);
  flex-shrink: 0;
  white-space: nowrap;
  width: 170px;
}
.log-line-level {
  flex-shrink: 0;
  width: 68px;
  font-weight: 600;
  text-align: center;
  border-radius: 3px;
  font-size: 0.75rem;
  padding: 0 4px;
  height: 1.5em;
  line-height: 1.5em;
}
.log-level-tag--info { color: var(--color-indigo-400); }
.log-level-tag--warning { color: var(--color-warning); }
.log-level-tag--error { color: var(--color-error); }
.log-level--info .log-line-time { color: var(--color-slate-500); }
.log-level--warning .log-line-time { color: var(--color-warning); }
.log-level--error .log-line-time { color: var(--color-error); }
.log-line-msg {
  color: var(--color-slate-300);
  flex: 1;
  min-width: 0;
  word-break: break-all;
}
.log-level--error .log-line-msg { color: #FCA5A5; }
.log-level--warning .log-line-msg { color: #FDE68A; }

/* ── 加载更多指示器 ── */
/* ── 关键字高亮 ── */
.log-highlight {
  background: rgba(234, 179, 8, 0.35);
  color: #FCD34D;
  padding: 0 2px;
  border-radius: 2px;
}

.log-load-more {
  text-align: center;
  padding: var(--space-2);
  font-size: 0.78rem;
  color: var(--color-slate-500);
}
.log-load-end {
  color: var(--color-slate-600);
}

/* ── 空状态 ── */
.log-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  color: var(--color-slate-400);
  gap: var(--space-2);
}
.log-empty-icon { font-size: 2.5rem; opacity: 0.5; }
.log-empty h3 { margin: 0; color: var(--color-slate-400); font-weight: 600; }
.log-empty p { margin: 0; font-size: 0.9rem; color: var(--color-slate-500); }

/* ── 底部状态栏 ── */
.log-statusbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-2) var(--space-4);
  font-size: 0.78rem;
  color: var(--color-slate-400);
  background: var(--color-white);
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-lg);
}
.log-statusbar-live {
  color: var(--color-success);
  animation: live-pulse 2s ease-in-out infinite;
}
@keyframes live-pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}
</style>
