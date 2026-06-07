<template>
  <div class="catalog-pane">
    <!-- ======== Hero ======== -->
    <div class="hero-card">
      <div>
        <div class="hero-kicker">MCP Servers</div>
        <h2>MCP 服务器管理</h2>
        <p>管理 MCP Server 连接配置，在对话中选择要携带的 MCP 服务器</p>
      </div>
      <div class="hero-stats">
        <div class="stat-box">
          <span class="stat-label">服务器数</span>
          <span class="stat-value">{{ servers.length }}</span>
        </div>
        <div class="stat-box">
          <span class="stat-label">已启用</span>
          <span class="stat-value ok">{{ enabledCount }}</span>
        </div>
        <div class="stat-box">
          <span class="stat-label">已禁用</span>
          <span class="stat-value bad">{{ servers.length - enabledCount }}</span>
        </div>
      </div>
    </div>

    <!-- ======== 操作栏 ======== -->
    <div class="action-bar">
      <el-button type="primary" @click="openAddDialog">
        ＋ 新增 MCP Server
      </el-button>
      <el-button plain @click="fetchServers" :loading="loading">
        ⟳ 刷新
      </el-button>
    </div>

    <!-- ======== 加载 / 空状态 ======== -->
    <div v-if="loading && !servers.length" class="empty-state">
      <p>加载中...</p>
    </div>
    <div v-else-if="!servers.length" class="empty-state">
      <div class="empty-icon">🔌</div>
      <h3>暂无 MCP 服务器</h3>
      <p>点击上方按钮添加你的第一个 MCP Server</p>
    </div>

    <!-- ======== 卡片网格 ======== -->
    <div v-else class="grid-cards">
      <article
        v-for="svr in servers"
        :key="svr.id"
        class="card"
        :class="{ 'card--disabled': !svr.enabled }"
      >
        <div class="card-top">
          <div>
            <h3>{{ svr.name }}</h3>
            <p class="card-url" :title="svr.url">{{ svr.url }}</p>
          </div>
          <div class="card-top-actions">
            <el-tag
              :type="svr.enabled ? 'success' : 'info'"
              effect="light"
              size="small"
            >
              {{ svr.enabled ? '启用' : '禁用' }}
            </el-tag>
          </div>
        </div>

        <div class="meta-row">
          <span class="meta-key">API Key</span>
          <span class="meta-val">{{ svr.api_key ? '••••••••' : '未设置' }}</span>
        </div>
        <div class="meta-row">
          <span class="meta-key">更新时间</span>
          <span class="meta-val">{{ formatTime(svr.updated_at) }}</span>
        </div>

        <!-- 测试结果 -->
        <div
          v-if="testResults[svr.id]"
          class="test-result"
          :class="testResults[svr.id].status === 'ok' ? 'test-ok' : 'test-err'"
        >
          <template v-if="testResults[svr.id].status === 'ok'">
            ✅ 连接成功 — {{ testResults[svr.id].tools_count }} 个工具
          </template>
          <template v-else>
            ❌ 连接失败 — {{ testResults[svr.id].message }}
          </template>
        </div>

        <!-- 操作按钮 -->
        <div class="card-actions">
          <el-button
            size="small"
            plain
            :loading="testingId === svr.id"
            @click="testServer(svr.id)"
          >
            测试
          </el-button>
          <el-button size="small" plain @click="openEditDialog(svr)">
            编辑
          </el-button>
          <el-popconfirm
            title="确定删除此 MCP Server？"
            confirm-button-text="删除"
            cancel-button-text="取消"
            @confirm="deleteServer(svr.id)"
          >
            <template #reference>
              <el-button size="small" type="danger" plain @click.stop>
                删除
              </el-button>
            </template>
          </el-popconfirm>
        </div>
      </article>
    </div>

    <!-- ======== 新增/编辑对话框 ======== -->
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
          <el-input
            v-model="formData.name"
            placeholder="例如：My Local MCP"
            maxlength="100"
          />
        </el-form-item>
        <el-form-item label="URL" prop="url">
          <el-input
            v-model="formData.url"
            placeholder="例如：http://localhost:8001/sse"
          />
        </el-form-item>
        <el-form-item label="API Key（可选）" prop="api_key">
          <el-input
            v-model="formData.api_key"
            type="password"
            show-password
            placeholder="留空则不设置"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch
            v-model="formData.enabled"
            active-text="启用"
            inactive-text="禁用"
          />
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

// ── 状态 ──────────────────────────────────────────
const loading = ref(false)
const submitting = ref(false)
const testingId = ref<string | null>(null)
const servers = ref<MCPServerInfo[]>([])
const testResults = ref<Record<string, MCPServerTestResult>>({})

// ── 表单 ──────────────────────────────────────────
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

// ── 计算 ──────────────────────────────────────────
const enabledCount = ref(0)

const updateStats = () => {
  enabledCount.value = servers.value.filter((s) => s.enabled).length
}

// ── API ───────────────────────────────────────────
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

// ── 新增 ──────────────────────────────────────────
const openAddDialog = () => {
  isEditing.value = false
  editingId.value = null
  formData.name = ''
  formData.url = ''
  formData.api_key = ''
  formData.enabled = true
  formDialogVisible.value = true
}

// ── 编辑 ──────────────────────────────────────────
const openEditDialog = (svr: MCPServerInfo) => {
  isEditing.value = true
  editingId.value = svr.id
  formData.name = svr.name
  formData.url = svr.url
  formData.api_key = svr.api_key || ''
  formData.enabled = svr.enabled
  formDialogVisible.value = true
}

// ── 提交 ──────────────────────────────────────────
const submitForm = async () => {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (isEditing.value && editingId.value) {
      const payload: Record<string, unknown> = {
        name: formData.name,
        url: formData.url,
        enabled: formData.enabled,
      }
      if (formData.api_key) payload.api_key = formData.api_key
      // 如果 api_key 清空了，显式设为 null
      if (!formData.api_key && (servers.value.find(s => s.id === editingId.value)?.api_key)) {
        payload.api_key = null
      }

      const res = await fetch(`/v1/mcp/servers/${editingId.value}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
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
      const payload: Record<string, unknown> = {
        name: formData.name,
        url: formData.url,
        enabled: formData.enabled,
      }
      if (formData.api_key) payload.api_key = formData.api_key

      const res = await fetch('/v1/mcp/servers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
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

// ── 工具 ──────────────────────────────────────────
const formatTime = (iso: string) => {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// ── 生命周期 ──────────────────────────────────────
defineExpose({ fetchServers })

onMounted(fetchServers)
</script>

<style scoped>
.catalog-pane {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100%;
}

/* ── Hero ── */
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
.hero-card p { margin: 8px 0 0; color: #6b7280; font-size: 0.9rem; }
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
.stat-value.ok { color: #059669; }
.stat-value.bad { color: #dc2626; }

/* ── 操作栏 ── */
.action-bar {
  display: flex;
  gap: 10px;
  align-items: center;
}

/* ── 空状态 ── */
.empty-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 48px; color: #9ca3af; gap: 8px;
  border: 2px dashed #e5e7eb; border-radius: 24px; background: #ffffff;
}
.empty-icon { font-size: 2.5rem; }
.empty-state h3 { margin: 0; color: #6b7280; font-weight: 600; }
.empty-state p { margin: 0; font-size: 0.9rem; color: #9ca3af; }

/* ── 卡片网格 ── */
.grid-cards { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.card {
  background: #ffffff; border: 1px solid #e5e7eb; border-radius: 22px;
  padding: 18px; box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
  display: flex; flex-direction: column; gap: 12px;
}
.card--disabled {
  opacity: 0.7;
  background: #f9fafb;
}
.card-top {
  display: flex; justify-content: space-between; gap: 12px;
  align-items: start; flex-shrink: 0; overflow: hidden;
}
.card h3 { margin: 0; color: #111827; font-size: 1rem; }
.card-url {
  margin: 6px 0 0; color: #6b7280; font-size: 0.85rem; line-height: 1.5;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.card-top > div { min-width: 0; overflow: hidden; }
.card-top-actions { display: flex; flex-direction: column; align-items: flex-end; gap: 8px; flex-shrink: 0; }

/* ── 元数据 ── */
.meta-row { display: flex; flex-direction: column; gap: 3px; }
.meta-key { font-size: 0.78rem; color: #6b7280; }
.meta-val { color: #111827; word-break: break-all; line-height: 1.5; font-size: 0.88rem; }

/* ── 测试结果 ── */
.test-result {
  padding: 8px 12px;
  border-radius: 10px;
  font-size: 0.82rem;
  line-height: 1.4;
}
.test-ok {
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  color: #065f46;
}
.test-err {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
}

/* ── 卡片操作按钮 ── */
.card-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  padding-top: 4px;
  border-top: 1px solid #f3f4f6;
}

/* ── 弹窗表单 ── */
.mcp-form { margin-top: 8px; }
</style>
