<template>
  <aside class="session-panel" :class="{ collapsed }">
    <!-- 展开/收缩按钮 -->
    <div class="session-toggle-area">
      <el-button size="small" circle @click="collapsed = !collapsed" class="toggle-btn">
        {{ collapsed ? '▶' : '◀' }}
      </el-button>
    </div>

    <!-- 会话列表主体 -->
    <div v-show="!collapsed" class="session-body">
      <div class="session-head">
        <div class="session-tabs">
          <button
            class="session-tab"
            :class="{ active: sessionKind === 0 }"
            @click="switchKind(0)"
          >历史会话</button>
          <button
            class="session-tab"
            :class="{ active: sessionKind === 1 }"
            @click="switchKind(1)"
          >定时任务</button>
        </div>
        <div class="session-actions">
          <el-button size="small" circle @click="fetchSessions" :loading="loading">⟳</el-button>
        </div>
      </div>

      <!-- 新建会话按钮（仅历史会话可见） -->
      <div v-if="sessionKind === 0" class="new-session-area">
        <button class="new-session-btn" @click="emit('new-session')">
          <span class="new-session-icon">＋</span>
          新建会话
        </button>
      </div>

      <div v-if="loading" class="session-status">加载中...</div>
      <div v-else-if="sessions.length === 0" class="session-status">
        {{ sessionKind === 1 ? '暂无定时任务会话' : '暂无历史会话' }}
      </div>
      <div v-else class="session-items">
        <div
          v-for="s in sessions"
          :key="s.id"
          class="session-item"
          :class="{ active: s.id === activeSessionId }"
        >
          <div class="session-item-main" @click="selectSession(s.id)">
            <div class="session-name">{{ s.title || (sessionKind === 1 ? '定时任务' : '新会话') }}</div>
            <div class="session-footer">
              <span class="session-footer-time">{{ formatTime(s.created_at) }}</span>
              <span class="session-footer-dot">·</span>
              <span class="session-footer-relative">{{ formatRelative(s.updated_at) }}</span>
            </div>
          </div>
          <div class="session-actions-vertical">
          <el-button
            size="small"
            circle
            class="rename-btn"
            title="重命名"
            @click.stop="handleRename(s)"
          >
            <span class="rename-icon">✎</span>
          </el-button>
          <el-popconfirm
            title="确定删除此会话？"
            confirm-button-text="删除"
            cancel-button-text="取消"
            @confirm="handleDelete(s.id, $event)"
          >
            <template #reference>
              <el-button
                size="small"
                circle
                class="delete-btn"
                title="删除会话"
                @click.stop
              >
                <span class="delete-icon">×</span>
              </el-button>
            </template>
          </el-popconfirm>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessageBox } from 'element-plus'

const props = defineProps<{
  activeSessionId: string
}>()

const emit = defineEmits<{
  'select-session': [sessionId: string]
  'delete-session': [sessionId: string]
  'new-session': []
}>()

type SessionSummary = { id: string; created_at: string; updated_at: string; title: string; kind?: number }

const collapsed = ref(false)
const loading = ref(false)
const sessions = ref<SessionSummary[]>([])
const sessionKind = ref<number>(0)

const fetchSessions = async () => {
  loading.value = true
  try {
    const res = await fetch(`/v1/sessions?limit=50&kind=${sessionKind.value}`)
    if (res.ok) sessions.value = await res.json()
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
}

const switchKind = (kind: number) => {
  sessionKind.value = kind
  fetchSessions()
}

const selectSession = (id: string) => {
  emit('select-session', id)
}

const handleRename = async (session: SessionSummary) => {
  try {
    const { value } = await ElMessageBox.prompt(
      '请输入新的会话标题',
      '重命名会话',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        inputValue: session.title || '新会话',
        inputPlaceholder: '会话标题',
      }
    )
    if (value && value.trim()) {
      const res = await fetch(`/v1/sessions/${session.id}/title`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: value.trim() }),
      })
      if (res.ok) {
        session.title = value.trim()
      }
    }
  } catch {
    // 用户取消或请求失败，静默处理
  }
}

const handleDelete = async (id: string, event?: MouseEvent) => {
  event?.stopPropagation()
  try {
    const res = await fetch(`/v1/sessions/${id}`, { method: 'DELETE' })
    if (res.ok) {
      sessions.value = sessions.value.filter((s) => s.id !== id)
      emit('delete-session', id)
    }
  } catch {
    // ignore
  }
}

const formatTime = (iso: string) => {
  const d = new Date(iso)
  return (
    d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }) +
    ' ' +
    d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
  )
}

const formatRelative = (iso: string) => {
  const now = Date.now()
  const t = new Date(iso).getTime()
  const diff = now - t
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  return `${Math.floor(diff / 86400000)} 天前`
}

defineExpose({ fetchSessions })

onMounted(fetchSessions)
</script>

<style scoped>
.session-panel {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: row;
  border-right: 1px solid var(--color-slate-200);
  background: var(--color-white);
  transition: width var(--transition-slow);
  overflow: hidden;
}
.session-panel.collapsed {
  width: auto;
}
.toggle-btn {
  margin: var(--space-2);
  flex-shrink: 0;
}
.session-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}
.session-head {
  padding: var(--space-3) var(--space-3);
  border-bottom: 1px solid var(--color-slate-200);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.session-head .session-actions {
  align-self: flex-end;
}
.session-actions {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex-shrink: 0;
}

/* ── 分类切换标签 ── */
.session-tabs {
  display: flex;
  gap: 4px;
  background: var(--color-slate-100);
  border-radius: var(--radius-md);
  padding: 3px;
}
.session-tab {
  flex: 1;
  text-align: center;
  border: none;
  background: transparent;
  color: var(--color-slate-500);
  font-size: 0.8rem;
  font-weight: 500;
  padding: 5px 8px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
  white-space: nowrap;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}
.session-tab:hover {
  color: var(--color-navy-700);
}
.session-tab.active {
  background: var(--color-white);
  color: var(--color-navy-800);
  font-weight: 600;
  box-shadow: var(--shadow-xs);
}
.session-status {
  padding: var(--space-6) var(--space-4);
  text-align: center;
  color: var(--color-slate-400);
  font-size: 0.85rem;
}
.session-items {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-2);
}
.session-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 3px 3px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-fast);
  margin-bottom: 2px;
}
.session-item:hover {
  background: var(--color-slate-50);
}
.session-item.active {
  background: var(--color-gold-50);
  border: 1px solid var(--color-gold-200);
}
.session-item-main {
  flex: 1;
  min-width: 0;
  padding: var(--space-1) 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.session-name {
  font-size: 0.88rem;
  color: var(--color-navy-800);
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.session-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  font-size: 0.72rem;
  color: var(--color-slate-400);
}
.session-footer-dot {
  color: var(--color-slate-300);
}
.session-actions-vertical {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex-shrink: 0;
}
.delete-btn,
.rename-btn {
  opacity: 0;
  transition: opacity var(--transition-fast);
  width: 24px;
  height: 24px;
  font-size: 0.75rem;
  padding: 0;
}
.session-item:hover .delete-btn,
.session-item:hover .rename-btn {
  opacity: 1;
}
.rename-btn {
  color: var(--color-slate-500);
}
.rename-btn:hover {
  color: var(--color-gold-600);
  background: var(--color-gold-50);
}
.rename-icon {
  font-style: normal;
  font-size: 1rem;
  line-height: 1;
}
.delete-icon {
  font-style: normal;
  font-size: 1rem;
  line-height: 1;
}

/* ── 新建会话按钮 ── */
.new-session-area {
  padding: var(--space-2) var(--space-3) 0;
}
.new-session-btn {
  width: 100%;
  border: 1px dashed var(--color-slate-300);
  background: var(--color-slate-50);
  color: var(--color-slate-500);
  font-size: 0.82rem;
  font-weight: 500;
  border-radius: var(--radius-md);
  padding: 6px 12px;
  cursor: pointer;
  transition: all var(--transition-fast);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  font-family: inherit;
  line-height: 1.4;
  box-sizing: border-box;
}
.new-session-btn:hover {
  border-color: var(--color-gold-400);
  background: var(--color-gold-50);
  color: var(--color-gold-600);
  border-style: solid;
}
.new-session-icon {
  font-style: normal;
  font-size: 1rem;
  line-height: 1;
}
</style>
