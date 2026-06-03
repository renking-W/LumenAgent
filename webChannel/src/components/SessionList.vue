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
        <span class="session-title">历史会话</span>
        <div class="session-actions">
          <el-button size="small" type="primary" plain @click="emit('new-session')">＋ 新会话</el-button>
          <el-button size="small" circle @click="fetchSessions" :loading="loading">⟳</el-button>
        </div>
      </div>

      <div v-if="loading" class="session-status">加载中...</div>
      <div v-else-if="sessions.length === 0" class="session-status">暂无会话</div>
      <div v-else class="session-items">
        <div
          v-for="s in sessions"
          :key="s.id"
          class="session-item"
          :class="{ active: s.id === activeSessionId }"
        >
          <div class="session-item-main" @click="selectSession(s.id)">
            <div class="session-name">{{ s.title || '新会话' }}</div>
            <div class="session-footer">
              <span class="session-footer-time">{{ formatTime(s.created_at) }}</span>
              <span class="session-footer-dot">·</span>
              <span class="session-footer-relative">{{ formatRelative(s.updated_at) }}</span>
            </div>
          </div>
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
  </aside>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

const props = defineProps<{
  activeSessionId: string
}>()

const emit = defineEmits<{
  'select-session': [sessionId: string]
  'delete-session': [sessionId: string]
  'new-session': []
}>()

type SessionSummary = { id: string; created_at: string; updated_at: string; title: string }

const collapsed = ref(false)
const loading = ref(false)
const sessions = ref<SessionSummary[]>([])

const fetchSessions = async () => {
  loading.value = true
  try {
    const res = await fetch('/v1/sessions?limit=50')
    if (res.ok) sessions.value = await res.json()
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
}

const selectSession = (id: string) => {
  emit('select-session', id)
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
  border-right: 1px solid #e5e7eb;
  background: #ffffff;
  transition: width 0.25s ease;
  overflow: hidden;
}
.session-panel.collapsed {
  width: auto;
}
.toggle-btn {
  margin: 8px;
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
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid #e5e7eb;
}
.session-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.session-title {
  font-weight: 600;
  color: #111827;
  font-size: 0.95rem;
  white-space: nowrap;
}
.session-status {
  padding: 24px 14px;
  text-align: center;
  color: #9ca3af;
  font-size: 0.85rem;
}
.session-items {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.session-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 4px 4px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s;
  margin-bottom: 4px;
}
.session-item:hover {
  background: #f3f4f6;
}
.session-item.active {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
}
.session-item-main {
  flex: 1;
  min-width: 0;
  padding: 6px 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.session-name {
  font-size: 0.88rem;
  color: #111827;
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
  font-size: 0.75rem;
  color: #9ca3af;
}
.session-footer-dot {
  color: #d1d5db;
}
.delete-btn {
  opacity: 0;
  transition: opacity 0.15s;
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  font-size: 0.75rem;
}
.session-item:hover .delete-btn {
  opacity: 1;
}
.delete-icon {
  font-style: normal;
  font-size: 1rem;
  line-height: 1;
}
</style>
