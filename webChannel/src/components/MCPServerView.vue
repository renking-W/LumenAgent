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
          <span class="mcp-stat-label">服务器</span>
        </div>
        <span class="mcp-stat-dot"></span>
        <div class="mcp-stat">
          <span class="mcp-stat-value" style="color: var(--color-success)">{{ enabledCount }}</span>
          <span class="mcp-stat-label">已启用</span>
        </div>
        <span class="mcp-stat-dot"></span>
        <div class="mcp-stat">
          <span class="mcp-stat-value" style="color: var(--color-slate-400)">{{ servers.length - enabledCount }}</span>
          <span class="mcp-stat-label">已禁用</span>
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
            <el-tag :type="svr.enabled ? 'success' : 'info'" effect="light" size="small">
              {{ svr.enabled ? '启用' : '禁用' }}
            </el-tag>
          </div>
          <p class="mcp-panel-url" :title="svr.url">{{ svr.url }}</p>
        </div>

        <div class="mcp-panel-details">
          <div class="mcp-panel-detail">
            <span class="mcp-detail-key">API Key</span>
            <span class="mcp-detail-val">{{ svr.api_key ? '••••••••' : '未设置' }}</span>
          </div>
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
          <el-button size="small" plain :loading="testingId === svr.id" @click="testServer(svr.id)">测试</el-button>
          <el-button size="small" plain @click="openEditDialog(svr)">编辑</el-button>
          <el-popconfirm
            title="确定删除？"
            confirm-button-text="删除"
            cancel-button-text="取消"
            @confirm="deleteServer(svr.id)"
          >
            <template #reference>
              <el-button size="small" type="danger" plain>删除</el-button>
            </template>
          </el-popconfirm>
        </div>
      </article>
    </div>

    <el-dialog
      v-model="formDialogVisible"
      :title="isEditing ? '编辑 MCP Server' : '新增 MCP Server'"
      width="560px"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-position="top"
        class="mcp-form"
      >
        <el-form-item label="名称" prop="name">
          <el-input v-model="formData.name" placeholder="例如：My Local MCP" maxlength="100" />
        </el-form-item>
        <el-form-item label="URL" prop="url">
          <el-input v-model="formData.url" placeholder="例如：http://localhost:8001/sse" />
        </el-form-item>
        <el-form-item label="API Key（可选）" prop="api_key">
          <el-input v-model="formData.api_key" type="password" show-password placeholder="留空则不设置" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="formData.enabled" active-text="启用" inactive-text="禁用" />
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
import { ref, reactive, onMounted } from 'vue'
import type { MCPServerInfo, MCPServerTestResult } from '../types'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

const loading = ref(false)
const submitting = ref(false)
const testingId = ref<string | null>(null)
const servers = ref<MCPServerInfo[]>([])
const testResults = ref<Record<string, MCPServerTestResult>>({})

const formDialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref<string | null>(null)
const formRef = ref<FormInstance | null>(null)

const formData = reactive({
  name: '',
  url: '',
  api_key: '',
  enabled: true,
})

const formRules: FormRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  url: [{ required: true, message: '请输入 URL', trigger: 'blur' }],
}

const enabledCount = ref(0)

const updateStats = () => {
  enabledCount.value = servers.value.filter((s) => s.enabled).length
}

const fetchServers = async () => {
  loading.value = true
  try {
    const res = await fetch('/v1/mcp/servers')
    if (res.ok) {
      servers.value = await res.json()
      updateStats()
    }
  } catch {
    ElMessage.error('获取 MCP 服务器列表失败')
  } finally {
    loading.value = false
  }
}

const testServer = async (id: string) => {
  testingId.value = id
  testResults.value[id] = undefined as any
  try {
    const res = await fetch(`/v1/mcp/servers/${id}/test`, { method: 'POST' })
    if (res.ok) {
      testResults.value[id] = await res.json()
    } else {
      testResults.value[id] = { status: 'error', message: '请求失败' }
    }
  } catch {
    testResults.value[id] = { status: 'error', message: '网络错误' }
  } finally {
    testingId.value = null
  }
}

const deleteServer = async (id: string) => {
  try {
    const res = await fetch(`/v1/mcp/servers/${id}`, { method: 'DELETE' })
    if (res.ok) {
      servers.value = servers.value.filter((s) => s.id !== id)
      delete testResults.value[id]
      updateStats()
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
  formData.name = ''
  formData.url = ''
  formData.api_key = ''
  formData.enabled = true
  formDialogVisible.value = true
}

const openEditDialog = (svr: MCPServerInfo) => {
  isEditing.value = true
  editingId.value = svr.id
  formData.name = svr.name
  formData.url = svr.url
  formData.api_key = svr.api_key || ''
  formData.enabled = svr.enabled
  formDialogVisible.value = true
}

const submitForm = async () => {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (isEditing.value && editingId.value) {
      const payload: Record<string, unknown> = { name: formData.name, url: formData.url, enabled: formData.enabled }
      if (formData.api_key) payload.api_key = formData.api_key
      if (!formData.api_key && (servers.value.find(s => s.id === editingId.value)?.api_key)) {
        payload.api_key = null
      }
      const res = await fetch(`/v1/mcp/servers/${editingId.value}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      })
      if (res.ok) {
        const updated = await res.json()
        const idx = servers.value.findIndex((s) => s.id === editingId.value)
        if (idx >= 0) servers.value[idx] = updated
        updateStats()
        ElMessage.success('已更新')
        formDialogVisible.value = false
        delete testResults.value[editingId.value]
      } else {
        const err = await res.text()
        ElMessage.error(`更新失败: ${err}`)
      }
    } else {
      const payload: Record<string, unknown> = { name: formData.name, url: formData.url, enabled: formData.enabled }
      if (formData.api_key) payload.api_key = formData.api_key
      const res = await fetch('/v1/mcp/servers', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      })
      if (res.ok) {
        const created = await res.json()
        servers.value.push(created)
        updateStats()
        ElMessage.success('已创建')
        formDialogVisible.value = false
      } else {
        const err = await res.text()
        ElMessage.error(`创建失败: ${err}`)
      }
    }
  } catch {
    ElMessage.error('网络错误')
  } finally {
    submitting.value = false
  }
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
.mcp-panel--disabled {
  opacity: 0.65;
}
.mcp-panel--disabled:hover {
  opacity: 0.85;
}
.mcp-panel-top {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.mcp-panel-status-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
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
}
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
.mcp-form { margin-top: var(--space-2); }
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
