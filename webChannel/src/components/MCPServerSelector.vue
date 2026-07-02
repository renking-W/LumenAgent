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
            :title="svr.kind === 'http' ? svr.url : svr.command + ' ' + svr.args.join(' ')"
            @click="toggleServer(svr.id)"
          >
            <span class="mcp-tag-dot"></span>
            <span class="mcp-kind-badge" :class="svr.kind === 'http' ? 'kind-http' : 'kind-stdio'">
              {{ svr.kind === 'http' ? 'H' : 'S' }}
            </span>
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
import type { MCPUnifiedServer, MCPServerInfo, MCPStdioServerInfo } from '../types'

const props = defineProps<{
  selectedIds: string[]
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:selectedIds': [ids: string[]]
}>()

const servers = ref<MCPUnifiedServer[]>([])
const loading = ref(false)
const collapsed = ref(true)

const filteredServers = computed(() =>
  servers.value.filter((s) => s.enabled)
)

const selectedIdsSet = computed(() => new Set(props.selectedIds))
const selectedCount = computed(() => props.selectedIds.length)

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
    const [httpRes, stdioRes] = await Promise.all([
      fetch('/v1/mcp/http-servers'),
      fetch('/v1/mcp/stdio-servers'),
    ])
    const httpList: MCPServerInfo[] = httpRes.ok ? await httpRes.json() : []
    const stdioList: MCPStdioServerInfo[] = stdioRes.ok ? await stdioRes.json() : []
    servers.value = [
      ...httpList.map((s) => ({ ...s, kind: 'http' as const })),
      ...stdioList.map((s) => ({ ...s, kind: 'stdio' as const })),
    ]
  } catch {
    // 静默失败
  } finally {
    loading.value = false
  }
}

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
  background: var(--color-slate-50);
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-lg);
  padding: var(--space-2) var(--space-4);
  transition: all var(--transition-normal);
}
.mcp-selector--empty {
  opacity: 0.6;
}
.mcp-selector--collapsed {
  background: var(--color-white);
  border-color: var(--color-slate-200);
}
.mcp-selector--collapsed:hover {
  border-color: var(--color-gold-300);
  background: var(--color-gold-50);
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
  color: var(--color-slate-500);
  display: flex;
  align-items: center;
  gap: 6px;
}
.mcp-collapse-icon {
  font-size: 0.6rem;
  color: var(--color-slate-400);
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
  color: var(--color-gold-600);
  margin-left: 2px;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mcp-selector-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
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
  gap: var(--space-2);
  font-size: 0.82rem;
  color: var(--color-slate-400);
}
.mcp-loading-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-gold-400);
  animation: mcp-pulse 1.2s ease-in-out infinite;
}
@keyframes mcp-pulse {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 1; }
}

/* 空状态 */
.mcp-selector-empty {
  font-size: 0.82rem;
  color: var(--color-slate-400);
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
  border-radius: var(--radius-full);
  border: 1px solid var(--color-slate-200);
  background: var(--color-white);
  color: var(--color-navy-600);
  font-size: 0.82rem;
  cursor: pointer;
  transition: all var(--transition-fast);
  user-select: none;
}
.mcp-tag:hover {
  border-color: var(--color-gold-300);
  background: var(--color-gold-50);
}
.mcp-tag--active {
  border-color: var(--color-gold-500);
  background: var(--color-gold-50);
  color: var(--color-gold-700);
}
.mcp-tag-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-slate-300);
  flex-shrink: 0;
}
.mcp-tag--active .mcp-tag-dot {
  background: var(--color-gold-500);
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
  color: var(--color-gold-600);
}
.mcp-kind-badge {
  font-size: 0.62rem;
  font-weight: 700;
  padding: 1px 4px;
  border-radius: 3px;
  flex-shrink: 0;
  line-height: 1.4;
}
.kind-http {
  background: #fef3c7;
  color: #92400e;
}
.kind-stdio {
  background: #ede9fe;
  color: #5b21b6;
}
</style>
