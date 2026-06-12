<template>
  <el-dialog
    v-model="visible"
    title="🔑 API Key 管理"
    width="680px"
    destroy-on-close
    :close-on-click-modal="false"
    @open="fetchKeys"
  >
    <!-- 操作结果提示 -->
    <div v-if="actionResult" class="ak-result" :class="actionResult.type">
      {{ actionResult.message }}
    </div>

    <!-- 加载 / 空状态 -->
    <div v-if="loading && !keys.length" class="ak-loading">加载中...</div>
    <div v-else-if="!keys.length" class="ak-empty">
      <div class="ak-empty-icon">🔑</div>
      <h3>暂无 API Key</h3>
      <p>点击下方按钮创建你的第一个 API Key</p>
    </div>

    <!-- Key 列表表格 -->
    <template v-else>
      <div class="ak-table-wrap">
        <table class="ak-table">
          <thead>
            <tr>
              <th class="ak-col-name">名称</th>
              <th class="ak-col-id">Key ID</th>
              <th class="ak-col-status">状态</th>
              <th class="ak-col-time">创建时间</th>
              <th class="ak-col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="key in keys" :key="key.id">
              <td class="ak-col-name">
                <span class="ak-key-name">{{ key.name || '(未命名)' }}</span>
              </td>
              <td class="ak-col-id">
                <code class="ak-key-id">{{ key.id }}</code>
              </td>
              <td class="ak-col-status">
                <el-switch
                  :model-value="key.enabled"
                  size="small"
                  :loading="togglingId === key.id"
                  @change="(val: boolean) => toggleKey(key, val)"
                />
              </td>
              <td class="ak-col-time">{{ formatTime(key.created_at) }}</td>
              <td class="ak-col-actions">
                <el-popconfirm
                  title="确定删除此 API Key？此操作不可撤销。"
                  confirm-button-text="删除"
                  cancel-button-text="取消"
                  @confirm="deleteKey(key)"
                >
                  <template #reference>
                    <el-button size="small" type="danger" plain @click.stop>删除</el-button>
                  </template>
                </el-popconfirm>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- 底部操作栏 -->
    <template #footer>
      <div class="ak-footer">
        <span v-if="keys.length > 0" class="ak-footer-count">共 {{ keys.length }} 个 Key</span>
        <div class="ak-footer-actions">
          <el-button @click="visible = false">关闭</el-button>
          <el-button type="primary" :loading="creating" @click="openCreateDialog">
            ＋ 新建 API Key
          </el-button>
        </div>
      </div>
    </template>

    <!-- ======== 新建 Key 弹窗（第二级） ======== -->
    <el-dialog
      v-model="createDialogVisible"
      title="新建 API Key"
      width="520px"
      destroy-on-close
      :close-on-click-modal="false"
      append-to-body
    >
      <template v-if="!createdKey">
        <el-form
          ref="createFormRef"
          :model="createForm"
          label-position="top"
          class="ak-create-form"
          @keydown.enter.prevent="submitCreate"
        >
          <el-form-item label="名称（可选）" prop="name">
            <el-input
              v-model="createForm.name"
              placeholder="例如：开发环境、生产环境"
              maxlength="100"
              clearable
            />
          </el-form-item>
        </el-form>
      </template>

      <!-- 创建成功 → 展示原始 Key（仅此一次） -->
      <template v-else>
        <div class="ak-created-box">
          <div class="ak-created-header">
            <span class="ak-created-icon">✅</span>
            <span>API Key 创建成功！</span>
          </div>
          <p class="ak-created-warning">
            ⚠️ 这是<strong>唯一一次</strong>看到完整 Key，关闭后无法再次查看。请立即复制并妥善保存。
          </p>
          <div class="ak-created-key-wrap">
            <code class="ak-created-key">{{ createdKey.key }}</code>
            <el-button
              size="small"
              type="primary"
              plain
              @click="copyToClipboard(createdKey.key)"
            >
              {{ copied ? '已复制' : '复制' }}
            </el-button>
          </div>
          <div class="ak-created-meta">
            <span>Key ID：<code>{{ createdKey.id }}</code></span>
            <span>名称：{{ createdKey.name || '(未命名)' }}</span>
          </div>
        </div>
      </template>

      <template #footer>
        <template v-if="!createdKey">
          <el-button @click="createDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="creating" @click="submitCreate">创建</el-button>
        </template>
        <template v-else>
          <el-button @click="closeCreateDone">关闭</el-button>
        </template>
      </template>
    </el-dialog>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import type { ApiKeyItem, ApiKeyCreatedResponse } from '../types'
import { ElMessage } from 'element-plus'
import type { FormInstance } from 'element-plus'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

// ── 主弹窗状态 ──────────────────────────────────
const visible = ref(false)
const loading = ref(false)
const keys = ref<ApiKeyItem[]>([])
const actionResult = ref<{ type: string; message: string } | null>(null)
const togglingId = ref<string | null>(null)
const creating = ref(false)

// 同步 visible ↔ modelValue
watch(() => props.modelValue, (val) => { visible.value = val })
watch(visible, (val) => emit('update:modelValue', val))

// ── 二级弹窗状态 ──────────────────────────────────
const createDialogVisible = ref(false)
const createFormRef = ref<FormInstance | null>(null)
const createForm = reactive({ name: '' })
const createdKey = ref<ApiKeyCreatedResponse | null>(null)
const copied = ref(false)

// ── 获取列表 ──────────────────────────────────────
const fetchKeys = async () => {
  loading.value = true
  actionResult.value = null
  try {
    const res = await fetch('/v1/api-keys')
    if (res.ok) {
      const data = await res.json()
      keys.value = data.keys || []
    } else {
      ElMessage.error('获取 API Key 列表失败')
    }
  } catch {
    ElMessage.error('网络错误')
  } finally {
    loading.value = false
  }
}

// ── 启用/禁用 ─────────────────────────────────────
const toggleKey = async (key: ApiKeyItem, enabled: boolean) => {
  togglingId.value = key.id
  try {
    const res = await fetch(`/v1/api-keys/${key.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    })
    if (res.ok) {
      key.enabled = enabled
      ElMessage.success(enabled ? '已启用' : '已禁用')
    } else {
      ElMessage.error('操作失败')
    }
  } catch {
    ElMessage.error('网络错误')
  } finally {
    togglingId.value = null
  }
}

// ── 删除 ──────────────────────────────────────────
const deleteKey = async (key: ApiKeyItem) => {
  try {
    const res = await fetch(`/v1/api-keys/${key.id}`, { method: 'DELETE' })
    if (res.ok) {
      keys.value = keys.value.filter((k) => k.id !== key.id)
      ElMessage.success('已删除')
    } else {
      ElMessage.error('删除失败')
    }
  } catch {
    ElMessage.error('网络错误')
  }
}

// ── 新建 ──────────────────────────────────────────
const openCreateDialog = () => {
  createForm.name = ''
  createdKey.value = null
  copied.value = false
  createDialogVisible.value = true
}

const submitCreate = async () => {
  creating.value = true
  try {
    const res = await fetch('/v1/api-keys', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: createForm.name.trim() }),
    })
    if (res.ok) {
      const data: ApiKeyCreatedResponse = await res.json()
      createdKey.value = data
      // 添加到列表（如果不在列表中）
      if (!keys.value.find((k) => k.id === data.id)) {
        keys.value.push({ id: data.id, name: data.name, enabled: data.enabled, created_at: data.created_at, updated_at: data.updated_at })
      }
    } else {
      const err = await res.text()
      ElMessage.error(`创建失败: ${err}`)
    }
  } catch {
    ElMessage.error('网络错误')
  } finally {
    creating.value = false
  }
}

const closeCreateDone = () => {
  createDialogVisible.value = false
  createdKey.value = null
}

// ── 复制 ──────────────────────────────────────────
const copyToClipboard = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text)
    copied.value = true
    setTimeout(() => { copied.value = false }, 3000)
  } catch {
    ElMessage.error('复制失败')
  }
}

// ── 工具 ──────────────────────────────────────────
const formatTime = (iso: string) => {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
</script>

<style scoped>
/* ── 操作结果 ── */
.ak-result {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  font-size: 0.9rem;
  line-height: 1.5;
  margin-bottom: var(--space-3);
}
.ak-result.success {
  background: var(--color-success-bg);
  border: 1px solid #A7F3D0;
  color: #065F46;
}
.ak-result.error {
  background: var(--color-error-bg);
  border: 1px solid #FECACA;
  color: #991B1B;
}

/* ── 加载 / 空状态 ── */
.ak-loading,
.ak-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  color: var(--color-slate-400);
  gap: var(--space-2);
}
.ak-empty-icon { font-size: 2.5rem; }
.ak-empty h3 { margin: 0; color: var(--color-slate-500); font-weight: 600; }
.ak-empty p { margin: 0; font-size: 0.9rem; }

/* ── 表格 ── */
.ak-table-wrap {
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-lg);
}
.ak-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}
.ak-table th {
  text-align: left;
  padding: var(--space-3) var(--space-4);
  font-weight: 600;
  color: var(--color-slate-500);
  background: var(--color-slate-50);
  border-bottom: 1px solid var(--color-slate-200);
  white-space: nowrap;
  position: sticky;
  top: 0;
  z-index: 1;
}
.ak-table td {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-slate-100);
  color: var(--color-navy-700);
}
.ak-table tbody tr:hover {
  background: var(--color-slate-50);
}
.ak-table tbody tr:last-child td {
  border-bottom: none;
}
.ak-col-name { min-width: 120px; }
.ak-col-id { min-width: 180px; }
.ak-col-status { width: 80px; text-align: center; }
.ak-col-time { width: 150px; }
.ak-col-actions { width: 80px; text-align: center; }

.ak-key-name {
  font-weight: 600;
  color: var(--color-navy-900);
}
.ak-key-id {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  background: var(--color-slate-100);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  color: var(--color-navy-600);
}

/* ── 底部操作栏 ── */
.ak-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}
.ak-footer-count {
  font-size: 0.82rem;
  color: var(--color-slate-400);
}
.ak-footer-actions {
  display: flex;
  gap: var(--space-2);
}

/* ── 新建表单 ── */
.ak-create-form { margin-top: var(--space-2); }

/* ── 创建成功展示 ── */
.ak-created-box {
  padding: var(--space-4);
  background: var(--color-slate-50);
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.ak-created-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-success);
}
.ak-created-icon { font-size: 1.3rem; }
.ak-created-warning {
  margin: 0;
  font-size: 0.88rem;
  color: #C2410C;
  background: var(--color-warning-bg);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  border: 1px solid #FDE68A;
  line-height: 1.5;
}
.ak-created-key-wrap {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  background: var(--color-navy-900);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
}
.ak-created-key {
  flex: 1;
  font-family: var(--font-mono);
  font-size: 0.82rem;
  color: var(--color-gold-400);
  word-break: break-all;
  line-height: 1.5;
}
.ak-created-meta {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-size: 0.85rem;
  color: var(--color-slate-500);
}
.ak-created-meta code {
  font-family: var(--font-mono);
  font-size: 0.82rem;
  background: var(--color-slate-100);
  padding: 1px 5px;
  border-radius: var(--radius-sm);
  color: var(--color-navy-700);
}
</style>
