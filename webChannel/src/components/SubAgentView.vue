<template>
  <div class="sa-page">
    <!-- ======== 页头 ======== -->
    <div class="sa-header">
      <div class="sa-header-left">
        <div class="sa-kicker">Sub-Agent Orchestration</div>
        <h2>本地 Agent 编排</h2>
      </div>
      <div class="sa-header-stats">
        <div class="sa-stat">
          <span class="sa-stat-value">{{ availableCount }}</span>
          <span class="sa-stat-label">可用适配器</span>
        </div>
        <span class="sa-stat-div"></span>
        <div class="sa-stat">
          <span class="sa-stat-value" style="color: var(--color-accent)">{{ runningCount }}</span>
          <span class="sa-stat-label">运行中</span>
        </div>
        <span class="sa-stat-div"></span>
        <div class="sa-stat">
          <span class="sa-stat-value">{{ runs.length }}</span>
          <span class="sa-stat-label">历史记录</span>
        </div>
      </div>
      <div class="sa-header-actions">
        <el-button size="small" plain @click="fetchData" :loading="loading">⟳ 刷新</el-button>
      </div>
    </div>

    <!-- ======== Tabs ======== -->
    <div class="sa-tabs">
      <button class="sa-tab" :class="{ active: activeTab === 'adapters' }" @click="activeTab = 'adapters'">
        🤖 适配器
      </button>
      <button class="sa-tab" :class="{ active: activeTab === 'runs' }" @click="activeTab = 'runs'; fetchRuns()">
        📋 运行历史
      </button>
    </div>

    <!-- ======== Tab: 适配器 ======== -->
    <div v-if="activeTab === 'adapters'" class="sa-content">
      <div v-if="!adapters.length && !loading" class="sa-empty">
        <div class="sa-empty-icon">🤖</div>
        <p>未发现可用的 Agent 适配器</p>
        <p class="sa-empty-hint">请安装 Claude Code ACP 适配器：<code>npm install -g @agentclientprotocol/claude-agent-acp</code></p>
      </div>
      <div v-else class="sa-adapter-grid">
        <div
          v-for="a in adapters"
          :key="a.name"
          class="sa-adapter-card"
          :class="{ 'sa-adapter-card--unavailable': !a.available }"
        >
          <div class="sa-adapter-icon">🤖</div>
          <div class="sa-adapter-body">
            <div class="sa-adapter-label">{{ a.label }}</div>
            <div class="sa-adapter-name">{{ a.name }}</div>
            <div class="sa-adapter-status" :class="a.available ? 'status-ok' : 'status-err'">
              {{ a.available ? '✅ 可用' : '❌ ' + (a.hint || '不可用') }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ======== Tab: 运行历史 ======== -->
    <div v-if="activeTab === 'runs'" class="sa-content">
      <div v-if="!runs.length && !loading" class="sa-empty">
        <div class="sa-empty-icon">📋</div>
        <p>暂无运行记录</p>
        <p class="sa-empty-hint">通过对话让 Lumen 调度 Agent 后，运行记录会在此展示</p>
      </div>

      <div v-for="run in runs" :key="run.run_id" class="sa-run-card">
        <div class="sa-run-header" @click="toggleRun(run.run_id)">
          <span class="sa-run-badge" :class="statusClass(run.status)">{{ run.status }}</span>
          <span class="sa-run-agent">{{ run.agent_type }}</span>
          <span class="sa-run-id">{{ run.run_id }}</span>
          <span class="sa-run-time">{{ formatTime(run.created_at) }}</span>
          <button
            v-if="run.status === 'running' || run.status === 'asking'"
            class="sa-stop-btn"
            @click.stop="stopRun(run.run_id)"
          >⏹ 停止</button>
          <span class="sa-run-chevron">{{ expandedRunIds.has(run.run_id) ? '▲' : '▼' }}</span>
        </div>

        <!-- 展开详情 -->
        <div v-if="expandedRunIds.has(run.run_id)" class="sa-run-detail">
          <div class="sa-run-prompt">
            <span class="sa-run-label">任务：</span>
            <span>{{ run.prompt }}</span>
          </div>
          <div class="sa-run-cwd">
            <span class="sa-run-label">工作目录：</span>
            <code>{{ run.cwd }}</code>
          </div>
          <div v-if="run.stop_reason" class="sa-run-stop-reason">
            <span class="sa-run-label">结束原因：</span>
            <span>{{ run.stop_reason }}</span>
          </div>

          <!-- 实时终端输出 -->
          <div class="sa-terminal" ref="terminalEl">
            <div v-if="liveOutput[run.run_id]" class="sa-terminal-content">
              <pre>{{ liveOutput[run.run_id] }}</pre>
            </div>
            <div v-else class="sa-terminal-empty">暂无输出</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useSubAgentWebSocket } from '../composables/useSubAgentWebSocket'

interface AdapterInfo {
  name: string
  label: string
  available: boolean
  hint: string
}

interface RunSummary {
  run_id: string
  parent_session_id: string
  agent_type: string
  prompt: string
  cwd: string
  status: string
  created_at: string
  finished_at?: string
  stop_reason?: string
}

const loading = ref(false)
const adapters = ref<AdapterInfo[]>([])
const runs = ref<RunSummary[]>([])
const activeTab = ref<'adapters' | 'runs'>('adapters')
const expandedRunIds = ref<Set<string>>(new Set())
const liveOutput = ref<Record<string, string>>({})

const { connect, disconnect, onEvent } = useSubAgentWebSocket()

const runningCount = computed(() => runs.value.filter(r => r.status === 'running' || r.status === 'asking').length)
const availableCount = computed(() => adapters.value.filter(a => a.available).length)

// ── 事件接收 ──────────────────────────────────────────
onEvent((event) => {
  const runId = event.run_id
  if (!runId) return

  if (event.event === 'session_update' && event.text) {
    liveOutput.value[runId] = (liveOutput.value[runId] || '') + event.text
  } else if (event.event === 'finished') {
    fetchRuns()
  } else if (event.event === 'permission_request') {
    fetchRuns()
  }
})

// ── 数据获取 ──────────────────────────────────────────
async function fetchData() {
  loading.value = true
  await Promise.all([fetchAdapters(), fetchRuns()])
  loading.value = false
}

async function fetchAdapters() {
  try {
    const res = await fetch('/v1/sub-agents/adapters')
    if (res.ok) {
      adapters.value = await res.json()
    } else {
      console.error('[SubAgent] adapters 请求失败:', res.status, await res.text())
    }
  } catch (err) {
    console.error('[SubAgent] adapters 请求异常:', err)
  }
}

async function fetchRuns() {
  try {
    const res = await fetch('/v1/sub-agents/runs?limit=30')
    if (res.ok) {
      runs.value = await res.json()
      // 对运行中的 run 订阅 WS
      for (const run of runs.value) {
        if (run.status === 'running' || run.status === 'asking') {
          connect(run.run_id)
        }
      }
    }
  } catch { /* ignore */ }
}

async function stopRun(runId: string) {
  try {
    await fetch(`/v1/sub-agents/runs/${runId}/stop`, { method: 'POST' })
    await fetchRuns()
  } catch { /* ignore */ }
}

// ── UI 交互 ────────────────────────────────────────────
function toggleRun(runId: string) {
  if (expandedRunIds.value.has(runId)) {
    expandedRunIds.value.delete(runId)
    expandedRunIds.value = new Set(expandedRunIds.value)
  } else {
    expandedRunIds.value.add(runId)
    expandedRunIds.value = new Set(expandedRunIds.value)
    connect(runId)
  }
}

function statusClass(status: string) {
  return {
    'badge-running': status === 'running',
    'badge-asking': status === 'asking',
    'badge-done': status === 'done',
    'badge-error': status === 'error',
    'badge-stopped': status === 'stopped',
  }
}

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return iso
  }
}

onMounted(fetchData)
</script>

<style scoped>
.sa-page { padding: 24px; max-width: 1100px; margin: 0 auto; }

.sa-header { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }
.sa-header-left { flex: 1; }
.sa-kicker { font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: var(--color-text-muted, #888); margin-bottom: 2px; }
.sa-header h2 { margin: 0; font-size: 22px; }
.sa-header-stats { display: flex; align-items: center; gap: 10px; }
.sa-stat { text-align: center; }
.sa-stat-value { display: block; font-size: 20px; font-weight: 700; line-height: 1; }
.sa-stat-label { font-size: 11px; color: #888; }
.sa-stat-div { width: 1px; height: 32px; background: #e0e0e0; }
.sa-header-actions { display: flex; gap: 8px; }

.sa-tabs { display: flex; gap: 4px; margin-bottom: 16px; border-bottom: 1px solid #e8e8e8; padding-bottom: 0; }
.sa-tab { padding: 8px 18px; border: none; background: transparent; cursor: pointer; font-size: 14px; color: #666; border-bottom: 2px solid transparent; margin-bottom: -1px; }
.sa-tab.active { color: var(--el-color-primary, #409eff); border-bottom-color: var(--el-color-primary, #409eff); font-weight: 600; }

.sa-content { padding-top: 8px; }

.sa-empty { text-align: center; padding: 60px 20px; }
.sa-empty-icon { font-size: 48px; margin-bottom: 12px; }
.sa-empty p { color: #666; margin: 4px 0; }
.sa-empty-hint { font-size: 12px; color: #aaa; }
.sa-empty-hint code { background: #f4f4f5; padding: 2px 6px; border-radius: 4px; font-size: 11px; }

.sa-adapter-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 14px; }
.sa-adapter-card {
  border: 1px solid #e8e8e8; border-radius: 10px; padding: 16px;
  display: flex; gap: 12px; align-items: flex-start;
  background: #fff; transition: box-shadow .2s;
}
.sa-adapter-card:hover { box-shadow: 0 2px 12px rgba(0,0,0,.08); }
.sa-adapter-card--unavailable { opacity: .6; }
.sa-adapter-icon { font-size: 28px; }
.sa-adapter-label { font-weight: 600; font-size: 15px; }
.sa-adapter-name { font-size: 11px; color: #999; font-family: monospace; }
.sa-adapter-status { font-size: 12px; margin-top: 6px; }
.status-ok { color: #52c41a; }
.status-err { color: #ff4d4f; }

.sa-run-card {
  border: 1px solid #e8e8e8; border-radius: 10px; margin-bottom: 10px;
  overflow: hidden; background: #fff;
}
.sa-run-header {
  display: flex; align-items: center; gap: 10px; padding: 12px 16px;
  cursor: pointer; transition: background .15s;
}
.sa-run-header:hover { background: #f9f9f9; }
.sa-run-badge { font-size: 11px; padding: 2px 8px; border-radius: 20px; font-weight: 600; }
.badge-running { background: #e6f7ff; color: #1890ff; }
.badge-asking  { background: #fffbe6; color: #fa8c16; }
.badge-done    { background: #f6ffed; color: #52c41a; }
.badge-error   { background: #fff2f0; color: #ff4d4f; }
.badge-stopped { background: #f5f5f5; color: #999; }
.sa-run-agent { font-size: 13px; font-weight: 600; }
.sa-run-id { font-family: monospace; font-size: 11px; color: #999; }
.sa-run-time { font-size: 12px; color: #bbb; margin-left: auto; }
.sa-stop-btn {
  font-size: 12px; padding: 3px 10px; border: 1px solid #ff4d4f;
  color: #ff4d4f; background: transparent; border-radius: 4px; cursor: pointer;
}
.sa-stop-btn:hover { background: #fff2f0; }
.sa-run-chevron { font-size: 11px; color: #bbb; }

.sa-run-detail { padding: 12px 16px; border-top: 1px solid #f0f0f0; background: #fafafa; }
.sa-run-prompt, .sa-run-cwd, .sa-run-stop-reason { margin-bottom: 8px; font-size: 13px; }
.sa-run-label { font-weight: 600; color: #666; margin-right: 4px; }

.sa-terminal {
  margin-top: 10px; background: #1a1a2e; border-radius: 8px;
  min-height: 80px; max-height: 400px; overflow-y: auto; font-family: monospace; font-size: 12px;
}
.sa-terminal-content { padding: 12px; }
.sa-terminal-content pre { color: #e0e0e0; white-space: pre-wrap; word-break: break-all; margin: 0; }
.sa-terminal-empty { padding: 12px; color: #555; font-style: italic; }
</style>
