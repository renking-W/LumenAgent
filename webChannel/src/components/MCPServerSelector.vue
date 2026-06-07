<template>
  <div class="mcp-selector" :class="{ 'mcp-selector--empty': filteredServers.length === 0, 'mcp-selector--collapsed': collapsed }">
    <div class="mcp-selector-header" @click="collapsed = !collapsed">
      <span class="mcp-selector-label">
        <span class="mcp-collapse-icon">{{ collapsed ? '▶' : '▼' }}</span>
        <span class="mcp-icon">🔌</span>
        MCP 服务器
        <span v-if="selectedCount > 0" class="mcp-selected-summary">
          {{ selectedSummary }}
        </span>
      </span>
      <div class="mcp-selector-actions" @click.stop>
        <el-tag v-if="selectedCount > 0" size="small" type="primary" effect="light">
          已选 {{ selectedCount }}
        </el-tag>
        <el-button
          v-if="filteredServers.length > 0 && selectedCount > 0"
          size="small"
          text
          type="info"
          @click="$emit('update:selectedIds', [])"
        >
          清除
        </el-button>
      </div>
    </div>

    <transition name="mcp-collapse">
      <div v-show="!collapsed" class="mcp-selector-body">
        <!-- 加载状态 -->
        <div v-if="loading" class="mcp-selector-loading">
          <span class="mcp-loading-dot"></span>
          加载中...
        </div>

        <!-- 无可用 MCP -->
        <div v-else-if="filteredServers.length === 0" class="mcp-selector-empty">
          <span>暂无启用的 MCP 服务器</span>
        </div>

        <!-- 服务器标签列表 -->
        <div v-else class="mcp-selector-tags">
          <div
            v-for="svr in filteredServers"
            :key="svr.id"
            class="mcp-tag"
            :class="{ 'mcp-tag--active': selectedIdsSet.has(svr.id) }"
            :title="svr.url"
            @click="toggleServer(svr.id)"
          >
            <span class="mcp-tag-dot"></span>
            <span class="mcp-tag-name">{{ svr.name }}</span>
            <span v-if="selectedIdsSet.has(svr.id)" class="mcp-tag-check">✓</span>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import type { MCPServerInfo } from '../types'

const props = defineProps<{
  selectedIds: string[]
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:selectedIds': [ids: string[]]
}>()

const servers = ref<MCPServerInfo[]>([])
const loading = ref(false)
const collapsed = ref(true) // 默认收缩

// 只展示已启用的 MCP 服务器
const filteredServers = computed(() =>
  servers.value.filter((s) => s.enabled)
)

const selectedIdsSet = computed(() => new Set(props.selectedIds))
const selectedCount = computed(() => props.selectedIds.length)

/** 选中的 MCP 名称摘要（逗号分隔，过长截断） */
const selectedSummary = computed(() => {
  const names = servers.value
    .filter((s) => props.selectedIds.includes(s.id))
    .map((s) => s.name)
  if (names.length === 0) return ''
  const joined = names.join(', ')
  return joined.length > 28 ? joined.slice(0, 26) + '…' : joined
})

const toggleServer = (id: string) => {
  if (props.disabled) return
  if (selectedIdsSet.value.has(id)) {
    emit('update:selectedIds', props.selectedIds.filter((i) => i !== id))
  } else {
    emit('update:selectedIds', [...props.selectedIds, id])
  }
}

const fetchServers = async () => {
  loading.value = true
  try {
    const res = await fetch('/v1/mcp/servers')
    if (res.ok) {
      servers.value = await res.json()
    }
  } catch {
    // 静默失败
  } finally {
    loading.value = false
  }
}

// 当列表刷新时，清除已经不存在的选择
watch(servers, () => {
  const validIds = new Set(filteredServers.value.map((s) => s.id))
  const newSelected = props.selectedIds.filter((id) => validIds.has(id))
  if (newSelected.length !== props.selectedIds.length) {
    emit('update:selectedIds', newSelected)
  }
})

defineExpose({ fetchServers })

onMounted(fetchServers)
</script>

<style scoped>
.mcp-selector {
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 8px 14px;
  transition: all 0.2s ease;
}
.mcp-selector--empty {
  opacity: 0.6;
}
.mcp-selector--collapsed {
  background: #ffffff;
  border-color: #e5e7eb;
}
.mcp-selector--collapsed:hover {
  border-color: #bfdbfe;
  background: #f8fafc;
}

.mcp-selector-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  user-select: none;
  min-height: 24px;
}
.mcp-selector-label {
  font-size: 0.82rem;
  font-weight: 600;
  color: #6b7280;
  display: flex;
  align-items: center;
  gap: 6px;
}
.mcp-collapse-icon {
  font-size: 0.6rem;
  color: #9ca3af;
  width: 12px;
  flex-shrink: 0;
  transition: transform 0.2s ease;
}
.mcp-icon {
  font-size: 0.9rem;
}
.mcp-selected-summary {
  font-size: 0.78rem;
  font-weight: 400;
  color: #3b82f6;
  margin-left: 2px;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mcp-selector-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 收缩体动画 */
.mcp-selector-body {
  overflow: hidden;
}
.mcp-collapse-enter-active {
  animation: mcp-slide-down 0.2s ease-out;
}
.mcp-collapse-leave-active {
  animation: mcp-slide-down 0.2s ease-in reverse;
}
@keyframes mcp-slide-down {
  from {
    max-height: 0;
    opacity: 0;
    margin-top: -6px;
  }
  to {
    max-height: 200px;
    opacity: 1;
    margin-top: 8px;
  }
}

/* 加载 */
.mcp-selector-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.82rem;
  color: #9ca3af;
}
.mcp-loading-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #93c5fd;
  animation: mcp-pulse 1.2s ease-in-out infinite;
}
@keyframes mcp-pulse {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 1; }
}

/* 空状态 */
.mcp-selector-empty {
  font-size: 0.82rem;
  color: #9ca3af;
}

/* 标签列表 */
.mcp-selector-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

/* 单个标签 */
.mcp-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid #d1d5db;
  background: #ffffff;
  color: #374151;
  font-size: 0.82rem;
  cursor: pointer;
  transition: all 0.15s ease;
  user-select: none;
}
.mcp-tag:hover {
  border-color: #93c5fd;
  background: #eff6ff;
}
.mcp-tag--active {
  border-color: #3b82f6;
  background: #eff6ff;
  color: #1d4ed8;
}
.mcp-tag-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #d1d5db;
  flex-shrink: 0;
}
.mcp-tag--active .mcp-tag-dot {
  background: #3b82f6;
}
.mcp-tag-name {
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mcp-tag-check {
  font-size: 0.7rem;
  font-weight: 700;
  color: #2563eb;
}
</style>
