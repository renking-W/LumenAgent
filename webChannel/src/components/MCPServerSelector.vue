<template>
  <div
    class="mcp-selector"
    :class="{ 'mcp-selector--empty': enabledServers.length === 0, 'mcp-selector--collapsed': collapsed }"
  >
    <div class="mcp-selector-header" @click="collapsed = !collapsed">
      <span class="mcp-selector-label">
        <span class="mcp-collapse-icon">{{ collapsed ? '▶' : '▼' }}</span>
        <span class="mcp-icon">🔌</span>
        已启用 MCP
        <span v-if="enabledServers.length > 0" class="mcp-count-badge">
          {{ enabledServers.length }}
        </span>
      </span>
    </div>

    <transition name="mcp-collapse">
      <div v-show="!collapsed" class="mcp-selector-body">
        <div v-if="loading" class="mcp-selector-loading">
          <span class="mcp-loading-dot"></span>
          加载中...
        </div>

        <div v-else-if="enabledServers.length === 0" class="mcp-selector-empty">
          <span>暂无启用的 MCP 服务器</span>
        </div>

        <div v-else class="mcp-selector-tags">
          <div
            v-for="svr in enabledServers"
            :key="svr.id"
            class="mcp-tag"
            :title="serverTitle(svr)"
          >
            <span class="mcp-tag-dot"></span>
            <span class="mcp-kind-badge" :class="svr.kind === 'http' ? 'kind-http' : 'kind-stdio'">
              {{ svr.kind === 'http' ? 'H' : 'S' }}
            </span>
            <span class="mcp-tag-name">{{ svr.name }}</span>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { MCPUnifiedServer, MCPServerInfo, MCPStdioServerInfo } from '../types'

const servers = ref<MCPUnifiedServer[]>([])
const loading = ref(false)
const collapsed = ref(true)

const enabledServers = computed(() => servers.value.filter((s) => s.enabled))

/** tag hover：endpoint + AI 生成描述前 80 字，便于快速了解能力 */
const serverTitle = (svr: MCPUnifiedServer) => {
  const endpoint =
    svr.kind === 'http'
      ? svr.url
      : `${svr.command} ${svr.args.join(' ')}`
  const desc = (svr.description || '').trim()
  const descPreview = desc.length > 80 ? `${desc.slice(0, 80)}…` : desc
  return descPreview ? `${endpoint}\n\n${descPreview}` : endpoint
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
.mcp-count-badge {
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--color-gold-700);
  background: var(--color-gold-100);
  padding: 1px 7px;
  border-radius: var(--radius-full);
  line-height: 1.5;
}

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

.mcp-selector-empty {
  font-size: 0.82rem;
  color: var(--color-slate-400);
}

.mcp-selector-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

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
  user-select: none;
}
.mcp-tag-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-emerald-400, #34d399);
  flex-shrink: 0;
}
.mcp-tag-name {
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
