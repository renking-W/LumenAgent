<template>
  <div class="mcp-page">
    <div class="mcp-header">
      <div class="mcp-header-left">
        <div class="mcp-kicker">MCP Servers</div>
        <h2>MCP 服务器管理</h2>
      </div>
      <div class="mcp-header-stats">
        <div class="mcp-stat">
          <span class="mcp-stat-value">{{ servers.length }}</span>
          <span class="mcp-stat-label">全部</span>
        </div>
        <span class="mcp-stat-dot"></span>
        <div class="mcp-stat">
          <span class="mcp-stat-value" style="color: var(--color-gold-600)">{{ httpCount }}</span>
          <span class="mcp-stat-label">HTTP</span>
        </div>
        <span class="mcp-stat-dot"></span>
        <div class="mcp-stat">
          <span class="mcp-stat-value" style="color: #7c3aed">{{ stdioCount }}</span>
          <span class="mcp-stat-label">Stdio</span>
        </div>
        <span class="mcp-stat-dot"></span>
        <div class="mcp-stat">
          <span class="mcp-stat-value" style="color: var(--color-success)">{{ enabledCount }}</span>
          <span class="mcp-stat-label">已启用</span>
        </div>
      </div>
      <div class="mcp-header-actions">
        <el-button size="small" type="primary" @click="openAddDialog">＋ 新增</el-button>
        <el-button size="small" plain @click="fetchServers" :loading="loading">⟳</el-button>
      </div>
    </div>

    <div v-if="loading && !servers.length" class="empty-state"><p>加载中...</p></div>
    <div v-else-if="!servers.length" class="empty-state">
      <div class="empty-icon">🔌</div>
      <h3>暂无 MCP 服务器</h3>
      <p>点击上方按钮添加你的第一个 MCP Server</p>
    </div>

    <div v-else class="mcp-grid">
      <article v-for="svr in servers" :key="svr.id" class="mcp-panel" :class="{ 'mcp-panel--disabled': !svr.enabled }">
        <div class="mcp-panel-top">
          <div class="mcp-panel-status-row">
            <span class="mcp-panel-dot" :class="svr.enabled ? 'dot-on' : 'dot-off'"></span>
            <h3 class="mcp-panel-name">{{ svr.name }}</h3>
            <el-tag
              :type="svr.kind === 'http' ? 'warning' : 'primary'"
              effect="light"
              size="small"
              class="kind-badge"
            >{{ svr.kind === 'http' ? 'HTTP' : 'Stdio' }}</el-tag>
            <el-tag v-if="svr.kind === 'http' && svr.transport" effect="plain" size="small" class="transport-badge">
              {{ svr.transport === 'sse' ? 'SSE' : svr.transport === 'streamable_http' ? 'Streamable' : svr.transport }}
            </el-tag>
            <el-tag :type="svr.enabled ? 'success' : 'info'" effect="light" size="small">
              {{ svr.enabled ? '启用' : '禁用' }}
            </el-tag>
          </div>
          <!-- HTTP: show URL -->
          <p v-if="svr.kind === 'http'" class="mcp-panel-url" :title="svr.url">{{ svr.url }}</p>
          <!-- Stdio: show command + args summary -->
          <p v-else class="mcp-panel-url" :title="svr.command + ' ' + svr.args.join(' ')">
            {{ svr.command }}{{ svr.args.length ? ' ' + svr.args.slice(0, 3).join(' ') + (svr.args.length > 3 ? ' …' : '') : '' }}
          </p>
        </div>

        <div class="mcp-panel-details">
          <template v-if="svr.kind === 'http'">
            <div class="mcp-panel-detail">
              <span class="mcp-detail-key">API Key</span>
              <span class="mcp-detail-val">{{ svr.api_key ? '••••••••' : '未设置' }}</span>
            </div>
          </template>
          <template v-else>
            <div v-if="svr.cwd" class="mcp-panel-detail">
              <span class="mcp-detail-key">CWD</span>
              <span class="mcp-detail-val mcp-detail-mono">{{ svr.cwd }}</span>
            </div>
            <div class="mcp-panel-detail">
              <span class="mcp-detail-key">ENV</span>
              <span class="mcp-detail-val">{{ Object.keys(svr.env).length }} 条</span>
            </div>
          </template>
          <div class="mcp-panel-detail">
            <span class="mcp-detail-key">更新时间</span>
            <span class="mcp-detail-val">{{ formatTime(svr.updated_at) }}</span>
          </div>
          <div v-if="testResults[svr.id]" class="mcp-panel-test" :class="testResults[svr.id].status === 'ok' ? 'test-ok' : 'test-err'">
            <template v-if="testResults[svr.id].status === 'ok'">
              ✅ {{ testResults[svr.id].tools_count }} 个工具
            </template>
            <template v-else>
              ❌ {{ testResults[svr.id].message }}
            </template>
          </div>
        </div>

        <div class="mcp-panel-actions">
          <el-button size="small" plain :loading="testingId === svr.id" @click="testServer(svr)">测试</el-button>
          <el-button size="small" plain @click="openEditDialog(svr)">编辑</el-button>
          <el-popconfirm
            title="确定删除？"
            confirm-button-text="删除"
            cancel-button-text="取消"
            @confirm="deleteServer(svr)"
          >
            <template #reference>
              <el-button size="small" type="danger" plain>删除</el-button>
            </template>
          </el-popconfirm>
        </div>
      </article>
    </div>

    <!-- Add / Edit Dialog -->
    <el-dialog
      v-model="formDialogVisible"
      :title="isEditing ? '编辑 MCP Server' : '新增 MCP Server'"
      width="580px"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <!-- Type selector only shown when adding -->
      <div v-if="!isEditing" class="type-selector">
        <el-radio-group v-model="formKind" size="large">
          <el-radio-button value="http">
            <span class="type-radio-label">🌐 HTTP</span>
            <span class="type-radio-sub">SSE / Streamable（自动探测）</span>
          </el-radio-button>
          <el-radio-button value="stdio">
            <span class="type-radio-label">🖥 Stdio</span>
            <span class="type-radio-sub">本地命令进程</span>
          </el-radio-button>
        </el-radio-group>
      </div>

      <!-- HTTP Form -->
      <el-form
        v-if="formKind === 'http'"
        ref="httpFormRef"
        :model="httpForm"
        :rules="httpFormRules"
        label-position="top"
        class="mcp-form"
      >
        <el-form-item label="名称" prop="name">
          <el-input v-model="httpForm.name" placeholder="例如：My Local MCP" maxlength="100" />
        </el-form-item>
        <el-form-item label="URL" prop="url">
          <el-input v-model="httpForm.url" placeholder="例如：http://localhost:8001/sse" />
        </el-form-item>
        <el-form-item label="API Key（可选）" prop="api_key">
          <el-input v-model="httpForm.api_key" type="password" show-password placeholder="留空则不设置" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="httpForm.enabled" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>

      <!-- Stdio Form -->
      <el-form
        v-else
        ref="stdioFormRef"
        :model="stdioForm"
        :rules="stdioFormRules"
        label-position="top"
        class="mcp-form"
      >
        <el-form-item label="名称" prop="name">
          <el-input v-model="stdioForm.name" placeholder="例如：Filesystem MCP" maxlength="100" />
        </el-form-item>
        <el-form-item label="命令" prop="command">
          <el-input v-model="stdioForm.command" placeholder="例如：npx" />
        </el-form-item>
        <el-form-item label="参数（每行一个）">
          <el-input
            v-model="stdioForm.argsText"
            type="textarea"
            :rows="3"
            placeholder="-y&#10;@modelcontextprotocol/server-filesystem&#10;/tmp"
          />
        </el-form-item>
        <el-form-item label="工作目录（可选）">
          <el-input v-model="stdioForm.cwd" placeholder="留空使用默认" />
        </el-form-item>
        <el-form-item label="环境变量">
          <div class="env-editor">
            <div v-for="(row, idx) in stdioForm.envRows" :key="idx" class="env-row">
              <el-input v-model="row.key" placeholder="KEY" size="small" class="env-key" />
              <span class="env-eq">=</span>
              <el-input v-model="row.value" placeholder="VALUE" size="small" class="env-val" />
              <el-button size="small" type="danger" plain circle @click="removeEnvRow(idx)">✕</el-button>
            </div>
            <el-button size="small" plain @click="addEnvRow">＋ 添加</el-button>
          </div>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="stdioForm.enabled" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="formDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">
          {{ isEditing ? '保存修改' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import type { MCPUnifiedServer, MCPServerInfo, MCPStdioServerInfo, MCPServerTestResult } from '../types'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

const loading = ref(false)
const submitting = ref(false)
const testingId = ref<string | null>(null)
const servers = ref<MCPUnifiedServer[]>([])
const testResults = ref<Record<string, MCPServerTestResult>>({})

const formDialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref<string | null>(null)
const formKind = ref<'http' | 'stdio'>('http')

const httpFormRef = ref<FormInstance | null>(null)
const stdioFormRef = ref<FormInstance | null>(null)

const httpForm = reactive({ name: '', url: '', api_key: '', enabled: true })
const httpFormRules: FormRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  url: [{ required: true, message: '请输入 URL', trigger: 'blur' }],
}

interface EnvRow { key: string; value: string }
const stdioForm = reactive({
  name: '',
  command: '',
  argsText: '',
  cwd: '',
  envRows: [] as EnvRow[],
  enabled: true,
})
const stdioFormRules: FormRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  command: [{ required: true, message: '请输入命令', trigger: 'blur' }],
}

const enabledCount = computed(() => servers.value.filter((s) => s.enabled).length)
const httpCount = computed(() => servers.value.filter((s) => s.kind === 'http').length)
const stdioCount = computed(() => servers.value.filter((s) => s.kind === 'stdio').length)

const addEnvRow = () => stdioForm.envRows.push({ key: '', value: '' })
const removeEnvRow = (idx: number) => stdioForm.envRows.splice(idx, 1)

const fetchServers = async () => {
  loading.value = true
  try {
    const [httpRes, stdioRes] = await Promise.all([
      fetch('/v1/mcp/http-servers'),
      fetch('/v1/mcp/stdio-servers'),
    ])
    const httpList: MCPServerInfo[] = httpRes.ok ? await httpRes.json() : []
    const stdioList: MCPStdioServerInfo[] = stdioRes.ok ? await stdioRes.json() : []
    const combined: MCPUnifiedServer[] = [
      ...httpList.map((s) => ({ ...s, kind: 'http' as const })),
      ...stdioList.map((s) => ({ ...s, kind: 'stdio' as const })),
    ]
    combined.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    servers.value = combined
  } catch {
    ElMessage.error('获取 MCP 服务器列表失败')
  } finally {
    loading.value = false
  }
}

const testServer = async (svr: MCPUnifiedServer) => {
  testingId.value = svr.id
  testResults.value[svr.id] = undefined as any
  const url = svr.kind === 'stdio'
    ? `/v1/mcp/stdio-servers/${svr.id}/test`
    : `/v1/mcp/http-servers/${svr.id}/test`
  try {
    const res = await fetch(url, { method: 'POST' })
    testResults.value[svr.id] = res.ok ? await res.json() : { status: 'error', message: '请求失败' }
  } catch {
    testResults.value[svr.id] = { status: 'error', message: '网络错误' }
  } finally {
    testingId.value = null
  }
}

const deleteServer = async (svr: MCPUnifiedServer) => {
  const url = svr.kind === 'stdio'
    ? `/v1/mcp/stdio-servers/${svr.id}`
    : `/v1/mcp/http-servers/${svr.id}`
  try {
    const res = await fetch(url, { method: 'DELETE' })
    if (res.ok) {
      servers.value = servers.value.filter((s) => s.id !== svr.id)
      delete testResults.value[svr.id]
      ElMessage.success('已删除')
    } else {
      ElMessage.error('删除失败')
    }
  } catch {
    ElMessage.error('网络错误')
  }
}

const openAddDialog = () => {
  isEditing.value = false
  editingId.value = null
  formKind.value = 'http'
  httpForm.name = ''; httpForm.url = ''; httpForm.api_key = ''; httpForm.enabled = true
  stdioForm.name = ''; stdioForm.command = ''; stdioForm.argsText = ''; stdioForm.cwd = ''; stdioForm.envRows = []; stdioForm.enabled = true
  formDialogVisible.value = true
}

const openEditDialog = (svr: MCPUnifiedServer) => {
  isEditing.value = true
  editingId.value = svr.id
  formKind.value = svr.kind
  if (svr.kind === 'http') {
    httpForm.name = svr.name; httpForm.url = svr.url; httpForm.api_key = svr.api_key || ''; httpForm.enabled = svr.enabled
  } else {
    stdioForm.name = svr.name; stdioForm.command = svr.command
    stdioForm.argsText = svr.args.join('\n'); stdioForm.cwd = svr.cwd || ''
    stdioForm.envRows = Object.entries(svr.env).map(([key, value]) => ({ key, value }))
    stdioForm.enabled = svr.enabled
  }
  formDialogVisible.value = true
}

const submitForm = async () => {
  if (formKind.value === 'http') {
    const valid = await httpFormRef.value?.validate().catch(() => false)
    if (!valid) return
    await submitHttpForm()
  } else {
    const valid = await stdioFormRef.value?.validate().catch(() => false)
    if (!valid) return
    await submitStdioForm()
  }
}

const submitHttpForm = async () => {
  submitting.value = true
  try {
    const payload: Record<string, unknown> = { name: httpForm.name, url: httpForm.url, enabled: httpForm.enabled }
    if (httpForm.api_key) payload.api_key = httpForm.api_key
    if (isEditing.value && editingId.value) {
      const existing = servers.value.find((s) => s.id === editingId.value)
      if (!httpForm.api_key && existing && existing.kind === 'http' && existing.api_key) payload.api_key = null
      const res = await fetch(`/v1/mcp/http-servers/${editingId.value}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      })
      if (res.ok) {
        const updated: MCPServerInfo = await res.json()
        const idx = servers.value.findIndex((s) => s.id === editingId.value)
        if (idx >= 0) servers.value[idx] = { ...updated, kind: 'http' }
        delete testResults.value[editingId.value]
        ElMessage.success('已更新'); formDialogVisible.value = false
      } else { ElMessage.error(`更新失败: ${await res.text()}`) }
    } else {
      const res = await fetch('/v1/mcp/http-servers', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      })
      if (res.ok) {
        const created: MCPServerInfo = await res.json()
        servers.value.unshift({ ...created, kind: 'http' })
        ElMessage.success('已创建'); formDialogVisible.value = false
      } else { ElMessage.error(`创建失败: ${await res.text()}`) }
    }
  } catch { ElMessage.error('网络错误') }
  finally { submitting.value = false }
}

const submitStdioForm = async () => {
  submitting.value = true
  try {
    const args = stdioForm.argsText.split('\n').map((s) => s.trim()).filter(Boolean)
    const env = stdioForm.envRows
      .filter((r) => r.key.trim())
      .reduce<Record<string, string>>((acc, r) => { acc[r.key.trim()] = r.value; return acc }, {})
    const payload: Record<string, unknown> = {
      name: stdioForm.name, command: stdioForm.command,
      args, env, enabled: stdioForm.enabled,
    }
    if (stdioForm.cwd.trim()) payload.cwd = stdioForm.cwd.trim()

    if (isEditing.value && editingId.value) {
      const res = await fetch(`/v1/mcp/stdio-servers/${editingId.value}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      })
      if (res.ok) {
        const updated: MCPStdioServerInfo = await res.json()
        const idx = servers.value.findIndex((s) => s.id === editingId.value)
        if (idx >= 0) servers.value[idx] = { ...updated, kind: 'stdio' }
        delete testResults.value[editingId.value]
        ElMessage.success('已更新'); formDialogVisible.value = false
      } else { ElMessage.error(`更新失败: ${await res.text()}`) }
    } else {
      const res = await fetch('/v1/mcp/stdio-servers', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      })
      if (res.ok) {
        const created: MCPStdioServerInfo = await res.json()
        servers.value.unshift({ ...created, kind: 'stdio' })
        ElMessage.success('已创建'); formDialogVisible.value = false
      } else { ElMessage.error(`创建失败: ${await res.text()}`) }
    }
  } catch { ElMessage.error('网络错误') }
  finally { submitting.value = false }
}

const formatTime = (iso: string) => {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

defineExpose({ fetchServers })
onMounted(fetchServers)
</script>

<style scoped>
.mcp-page {
  padding: var(--space-5) var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-height: 100%;
}
.mcp-header {
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
.mcp-header-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.mcp-kicker {
  font-size: 0.7rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-gold-600);
  font-weight: 600;
}
.mcp-header-left h2 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--color-navy-900);
}
.mcp-header-stats {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.mcp-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
}
.mcp-stat-value {
  font-size: 1rem;
  font-weight: 700;
  color: var(--color-navy-800);
}
.mcp-stat-label {
  font-size: 0.68rem;
  color: var(--color-slate-400);
}
.mcp-stat-dot {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: var(--color-slate-300);
}
.mcp-header-actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  color: var(--color-slate-400);
  gap: var(--space-2);
  border: 2px dashed var(--color-slate-200);
  border-radius: var(--radius-2xl);
  background: var(--color-white);
}
.empty-icon { font-size: 2.5rem; }
.empty-state h3 { margin: 0; color: var(--color-slate-500); font-weight: 600; }
.empty-state p { margin: 0; font-size: 0.9rem; color: var(--color-slate-400); }
.mcp-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-3);
}
.mcp-panel {
  background: var(--color-white);
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-xl);
  padding: var(--space-4);
  box-shadow: var(--shadow-xs);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  transition: all var(--transition-normal);
}
.mcp-panel:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--color-gold-200);
  transform: translateY(-1px);
}
.mcp-panel--disabled { opacity: 0.65; }
.mcp-panel--disabled:hover { opacity: 0.85; }
.mcp-panel-top {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.mcp-panel-status-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.mcp-panel-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot-on { background: var(--color-success); box-shadow: 0 0 6px rgba(16, 185, 129, 0.4); }
.dot-off { background: var(--color-slate-300); }
.mcp-panel-name {
  margin: 0;
  flex: 1;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--color-navy-900);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kind-badge { font-size: 0.7rem !important; font-weight: 700 !important; }
.transport-badge { font-size: 0.65rem !important; color: var(--color-slate-500) !important; }
.mcp-panel-url {
  margin: 0;
  font-size: 0.78rem;
  color: var(--color-slate-400);
  font-family: var(--font-mono);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mcp-panel-details {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) 0;
  border-top: 1px solid var(--color-slate-100);
  border-bottom: 1px solid var(--color-slate-100);
}
.mcp-panel-detail {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.mcp-detail-key {
  font-size: 0.75rem;
  color: var(--color-slate-400);
}
.mcp-detail-val {
  font-size: 0.82rem;
  color: var(--color-navy-700);
}
.mcp-detail-mono {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mcp-panel-test {
  font-size: 0.78rem;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
  margin-top: var(--space-1);
}
.test-ok {
  background: var(--color-success-bg);
  border: 1px solid #A7F3D0;
  color: #065F46;
}
.test-err {
  background: var(--color-error-bg);
  border: 1px solid #FECACA;
  color: #991B1B;
}
.mcp-panel-actions {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

/* Dialog */
.type-selector {
  display: flex;
  justify-content: center;
  margin-bottom: var(--space-4);
}
.type-selector :deep(.el-radio-button__inner) {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px 28px;
  gap: 2px;
}
.type-radio-label { font-size: 0.95rem; font-weight: 600; }
.type-radio-sub { font-size: 0.72rem; color: var(--color-slate-400); font-weight: 400; }
.mcp-form { margin-top: var(--space-2); }

/* Env editor */
.env-editor { display: flex; flex-direction: column; gap: var(--space-2); width: 100%; }
.env-row { display: flex; align-items: center; gap: var(--space-1); }
.env-key { flex: 1; }
.env-val { flex: 2; }
.env-eq { font-size: 0.9rem; color: var(--color-slate-400); flex-shrink: 0; }

@media (max-width: 1024px) {
  .mcp-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 640px) {
  .mcp-grid { grid-template-columns: 1fr; }
  .mcp-header { flex-direction: column; align-items: stretch; }
  .mcp-header-stats { justify-content: center; }
  .mcp-header-actions { justify-content: center; }
}
</style>
