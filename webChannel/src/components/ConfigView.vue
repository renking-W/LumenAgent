<template>
  <div class="config-page">
    <!-- ======== 紧凑顶栏 ======== -->
    <div class="config-header">
      <div class="config-header-left">
        <div class="config-kicker">System Config</div>
        <h2>系统配置</h2>
      </div>
      <div class="config-header-stats">
        <div class="config-stat">
          <span class="config-stat-value">{{ totalCount }}</span>
          <span class="config-stat-label">配置项</span>
        </div>
        <span class="config-stat-div"></span>
        <div class="config-stat">
          <span class="config-stat-value" style="color: var(--color-gold-600)">{{ basicItems.length }}</span>
          <span class="config-stat-label">基本</span>
        </div>
        <span class="config-stat-div"></span>
        <div class="config-stat">
          <span class="config-stat-value" style="color: var(--color-slate-400)">{{ advancedItems.length }}</span>
          <span class="config-stat-label">高级</span>
        </div>
      </div>
      <div class="config-header-actions">
        <el-button size="small" plain @click="fetchConfigs" :loading="loading">⟳ 刷新</el-button>
      </div>
    </div>

    <!-- 操作结果提示 -->
    <div v-if="resultMessage" class="config-result" :class="resultMessage.type">
      <span>{{ resultMessage.text }}</span>
      <button class="config-result-close" @click="resultMessage = null">×</button>
    </div>

    <!-- ======== 加载 / 空 / 错误状态 ======== -->
    <div v-if="loading && !basicItems.length && !advancedItems.length" class="config-empty">
      <p>加载配置中...</p>
    </div>

    <div v-else-if="fetchError" class="config-empty">
      <div class="config-empty-icon">⚠️</div>
      <h3>加载失败</h3>
      <p>{{ fetchError }}</p>
      <el-button size="small" type="primary" plain @click="fetchConfigs">重试</el-button>
    </div>

    <div v-else-if="totalCount === 0" class="config-empty">
      <div class="config-empty-icon">⚙️</div>
      <h3>无可编辑配置</h3>
      <p>当前系统没有可编辑的配置项</p>
    </div>

    <!-- ======== 配置列表 ======== -->
    <template v-else>
      <!-- 基本配置 -->
      <section class="config-group">
        <div class="config-group-header">
          <div class="config-group-title-row">
            <span class="config-group-badge">★</span>
            <span class="config-group-title">基本配置</span>
            <span class="config-group-count">{{ basicItems.length }}</span>
          </div>
          <p class="config-group-desc">日常使用最频繁的系统参数，修改后即时生效</p>
        </div>
        <div class="config-cards">
          <div
            v-for="item in basicItems"
            :key="item.key"
            class="config-card config-card--basic"
          >
            <div class="config-card-body">
              <div class="config-card-key-row">
                <span class="config-card-key">{{ item.key }}</span>
                <el-tag size="small" effect="plain" type="warning" class="config-card-cat-tag">basic</el-tag>
              </div>
              <div class="config-card-value-row">
                <!-- Boolean: 内联开关 -->
                <template v-if="typeof item.value === 'boolean'">
                  <el-switch
                    :model-value="item.value as boolean"
                    size="small"
                    :loading="togglingKey === item.key"
                    @change="(val: boolean) => handleBooleanToggle(item, val)"
                  />
                  <span class="config-card-bool-label">{{ item.value ? '开启' : '关闭' }}</span>
                </template>
                <!-- 数值 -->
                <template v-else-if="typeof item.value === 'number'">
                  <span class="config-card-value config-card-value--num">{{ item.value }}</span>
                </template>
                <!-- 对象 -->
                <template v-else-if="typeof item.value === 'object' && item.value !== null">
                  <span class="config-card-value config-card-value--obj">{{ formatObjectValue(item.value) }}</span>
                </template>
                <!-- 字符串（含敏感键） -->
                <template v-else>
                  <span
                    class="config-card-value config-card-value--str"
                    :class="{ 'config-card-value--masked': isSensitiveKey(item.key) }"
                  >
                    {{ displayValue(item) }}
                  </span>
                </template>
              </div>
            </div>
            <div class="config-card-actions">
              <!-- Boolean 类型直接内联编辑，不需要编辑按钮 -->
              <template v-if="typeof item.value !== 'boolean'">
                <el-button size="small" text type="primary" @click="openEdit(item)">编辑</el-button>
              </template>
              <el-button size="small" text type="info" @click="showDetail(item)">详情</el-button>
            </div>
          </div>
        </div>
      </section>

      <!-- 高级配置（可折叠） -->
      <section class="config-group config-group--advanced">
        <div
          class="config-group-header config-group-header--clickable"
          :class="{ 'config-group-header--open': advancedOpen }"
          @click="advancedOpen = !advancedOpen"
        >
          <div class="config-group-title-row">
            <span class="config-group-collapse-icon">{{ advancedOpen ? '▼' : '▶' }}</span>
            <span class="config-group-badge config-group-badge--adv">⚙</span>
            <span class="config-group-title">高级配置</span>
            <span class="config-group-count">{{ advancedItems.length }}</span>
          </div>
          <p class="config-group-desc">较少调整的系统参数，修改前请确认参数含义</p>
        </div>
        <transition name="adv-collapse">
          <div v-show="advancedOpen" class="config-cards config-cards--adv">
            <div
              v-for="item in advancedItems"
              :key="item.key"
              class="config-card config-card--advanced"
            >
              <div class="config-card-body">
                <div class="config-card-key-row">
                  <span class="config-card-key">{{ item.key }}</span>
                  <el-tag size="small" effect="plain" type="info" class="config-card-cat-tag">advanced</el-tag>
                </div>
                <div class="config-card-value-row">
                  <template v-if="typeof item.value === 'boolean'">
                    <el-switch
                      :model-value="item.value as boolean"
                      size="small"
                      :loading="togglingKey === item.key"
                      @change="(val: boolean) => handleBooleanToggle(item, val)"
                    />
                    <span class="config-card-bool-label">{{ item.value ? '开启' : '关闭' }}</span>
                  </template>
                  <template v-else-if="typeof item.value === 'number'">
                    <span class="config-card-value config-card-value--num">{{ item.value }}</span>
                  </template>
                  <template v-else-if="typeof item.value === 'object' && item.value !== null">
                    <span class="config-card-value config-card-value--obj">{{ formatObjectValue(item.value) }}</span>
                  </template>
                  <template v-else>
                    <span
                      class="config-card-value config-card-value--str"
                      :class="{ 'config-card-value--masked': isSensitiveKey(item.key) }"
                    >
                      {{ displayValue(item) }}
                    </span>
                  </template>
                </div>
              </div>
              <div class="config-card-actions">
                <template v-if="typeof item.value !== 'boolean'">
                  <el-button size="small" text type="primary" @click="openEdit(item)">编辑</el-button>
                </template>
                <el-button size="small" text type="info" @click="showDetail(item)">详情</el-button>
              </div>
            </div>
          </div>
        </transition>
      </section>
    </template>

    <!-- ======== 编辑弹窗 ======== -->
    <el-dialog
      v-model="editDialogVisible"
      :title="'编辑配置: ' + (editingItem?.key || '')"
      width="520px"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <template v-if="editingItem">
        <div class="edit-form">
          <div class="edit-form-field">
            <label class="edit-form-label">配置键</label>
            <div class="edit-form-key">{{ editingItem.key }}</div>
          </div>

          <div class="edit-form-field">
            <label class="edit-form-label">
              配置值
              <span class="edit-form-type">({{ valueTypeLabel(editingItem) }})</span>
            </label>
            <!-- 布尔值：开关 -->
            <template v-if="typeof editingItem.value === 'boolean'">
              <el-switch v-model="editValueBool" size="large" />
            </template>
            <!-- 数值 -->
            <template v-else-if="typeof editingItem.value === 'number'">
              <el-input-number
                v-model="editValueNum"
                :min="0"
                :max="999999"
                :step="isInt(editingItem.value) ? 1 : 0.1"
                style="width: 100%"
              />
            </template>
            <!-- 对象 JSON -->
            <template v-else-if="typeof editingItem.value === 'object' && editingItem.value !== null">
              <el-input
                v-model="editValueStr"
                type="textarea"
                :autosize="{ minRows: 4, maxRows: 12 }"
                placeholder="JSON 对象"
              />
            </template>
            <!-- 字符串 -->
            <template v-else>
              <el-input
                v-model="editValueStr"
                :type="isSensitiveKey(editingItem.key) ? 'password' : 'text'"
                :show-password="isSensitiveKey(editingItem.key)"
                :placeholder="String(editingItem.value ?? '')"
              />
              <p v-if="isSensitiveKey(editingItem.key)" class="edit-form-hint">
                包含敏感信息，输入时将自动隐藏
              </p>
            </template>
          </div>
        </div>
      </template>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- ======== 详情弹窗 ======== -->
    <el-dialog
      v-model="detailDialogVisible"
      title="配置详情"
      width="520px"
      destroy-on-close
    >
      <template v-if="detailItem">
        <div class="detail-grid">
          <div class="detail-row">
            <span class="detail-key">配置键</span>
            <code class="detail-val detail-val--mono">{{ detailItem.key }}</code>
          </div>
          <div class="detail-row">
            <span class="detail-key">类别</span>
            <el-tag
              :type="detailItem.category === 'basic' ? 'warning' : 'info'"
              effect="light"
              size="small"
            >
              {{ detailItem.category === 'basic' ? '基本配置' : '高级配置' }}
            </el-tag>
          </div>
          <div class="detail-row">
            <span class="detail-key">值类型</span>
            <span class="detail-val">{{ valueTypeLabel(detailItem) }}</span>
          </div>
          <div class="detail-row detail-row--full">
            <span class="detail-key">当前值</span>
            <pre class="detail-pre">{{ formatDetailValue(detailItem) }}</pre>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import type { ConfigItem, ConfigListResponse, UpdateConfigResponse } from '../types'
import { ElMessage } from 'element-plus'

// ── 状态 ──────────────────────────────────────────
const loading = ref(false)
const fetchError = ref('')
const basicItems = ref<ConfigItem[]>([])
const advancedItems = ref<ConfigItem[]>([])
const advancedOpen = ref(false)
const togglingKey = ref<string | null>(null)

const resultMessage = ref<{ type: string; text: string } | null>(null)

const totalCount = computed(() => basicItems.value.length + advancedItems.value.length)

// ── 编辑弹窗 ──────────────────────────────────────
const editDialogVisible = ref(false)
const editingItem = ref<ConfigItem | null>(null)
const saving = ref(false)

const editValueStr = ref('')
const editValueNum = ref(0)
const editValueBool = ref(false)

// ── 详情弹窗 ──────────────────────────────────────
const detailDialogVisible = ref(false)
const detailItem = ref<ConfigItem | null>(null)

// ── 敏感键检测 ────────────────────────────────────
const SENSITIVE_PATTERNS = /^(LLM_API_KEY|EMBEDDING_API_KEY|API_KEY|SECRET|TOKEN|PASSWORD)/i

const isSensitiveKey = (key: string): boolean => SENSITIVE_PATTERNS.test(key)

// ── 值展示 ────────────────────────────────────────
const displayValue = (item: ConfigItem): string => {
  if (item.value === null || item.value === undefined) return '(未设置)'
  if (isSensitiveKey(item.key)) return '••••••••'
  return String(item.value)
}

const formatObjectValue = (value: unknown): string => {
  try {
    const str = JSON.stringify(value)
    return str.length > 60 ? str.slice(0, 58) + '…' : str
  } catch {
    return String(value)
  }
}

const formatDetailValue = (item: ConfigItem): string => {
  if (item.value === null || item.value === undefined) return '(未设置)'
  if (typeof item.value === 'object') return JSON.stringify(item.value, null, 2)
  return String(item.value)
}

const valueTypeLabel = (item: ConfigItem): string => {
  if (item.value === null) return 'null'
  if (Array.isArray(item.value)) return 'array'
  return typeof item.value
}

const isInt = (value: number): boolean => Number.isInteger(value)

// ── API ───────────────────────────────────────────
const fetchConfigs = async () => {
  loading.value = true
  fetchError.value = ''
  resultMessage.value = null
  try {
    const res = await fetch('/v1/configs')
    if (!res.ok) {
      fetchError.value = `请求失败 (${res.status})`
      return
    }
    const data: ConfigListResponse = await res.json()
    basicItems.value = data.basic || []
    advancedItems.value = data.advanced || []
  } catch (e) {
    fetchError.value = '无法连接到后端，请确认服务是否运行'
  } finally {
    loading.value = false
  }
}

const updateConfig = async (key: string, value: string): Promise<boolean> => {
  try {
    const res = await fetch('/v1/configs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key, value }),
    })
    if (res.ok) {
      const data: UpdateConfigResponse = await res.json()
      showResult('success', data.note || `配置「${key}」已更新`)
      return true
    }
    if (res.status === 403) {
      showResult('error', '该配置项受系统保护，不允许修改')
    } else {
      const err = await res.text()
      showResult('error', `更新失败: ${err}`)
    }
    return false
  } catch {
    showResult('error', '网络错误，更新失败')
    return false
  }
}

const showResult = (type: 'success' | 'error', text: string) => {
  resultMessage.value = { type, text }
  setTimeout(() => { resultMessage.value = null }, 5000)
}

// ── 布尔值内联切换 ────────────────────────────────
const handleBooleanToggle = async (item: ConfigItem, val: boolean) => {
  togglingKey.value = item.key
  const ok = await updateConfig(item.key, val ? 'true' : 'false')
  if (ok) {
    item.value = val
  }
  togglingKey.value = null
}

// ── 编辑操作 ──────────────────────────────────────
const openEdit = (item: ConfigItem) => {
  editingItem.value = item
  editValueStr.value = item.value !== null && item.value !== undefined ? String(item.value) : ''
  editValueNum.value = typeof item.value === 'number' ? item.value : 0
  editValueBool.value = item.value === true
  editDialogVisible.value = true
}

const submitEdit = async () => {
  if (!editingItem.value) return
  saving.value = true

  let newValueStr = ''
  const item = editingItem.value

  if (typeof item.value === 'boolean') {
    newValueStr = editValueBool.value ? 'true' : 'false'
  } else if (typeof item.value === 'number') {
    newValueStr = String(editValueNum.value)
  } else if (typeof item.value === 'object' && item.value !== null) {
    newValueStr = editValueStr.value
  } else {
    newValueStr = editValueStr.value
  }

  const ok = await updateConfig(item.key, newValueStr)
  if (ok) {
    // 更新本地值并刷新
    editDialogVisible.value = false
    await fetchConfigs()
  }
  saving.value = false
}

// ── 详情操作 ──────────────────────────────────────
const showDetail = (item: ConfigItem) => {
  detailItem.value = item
  detailDialogVisible.value = true
}

// ── 生命周期 ──────────────────────────────────────
onMounted(fetchConfigs)
</script>

<style scoped>
.config-page {
  padding: var(--space-5) var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-height: 100%;
}

/* ── 紧凑顶栏 ── */
.config-header {
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
.config-header-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.config-kicker {
  font-size: 0.7rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-gold-600);
  font-weight: 600;
}
.config-header-left h2 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--color-navy-900);
}
.config-header-stats {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.config-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
}
.config-stat-value {
  font-size: 1rem;
  font-weight: 700;
  color: var(--color-navy-800);
}
.config-stat-label {
  font-size: 0.68rem;
  color: var(--color-slate-400);
}
.config-stat-div {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: var(--color-slate-300);
}
.config-header-actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

/* ── 操作结果横幅 ── */
.config-result {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  font-size: 0.9rem;
  line-height: 1.5;
  animation: result-slide-in 0.25s ease;
}
.config-result.success {
  background: var(--color-success-bg);
  border: 1px solid #A7F3D0;
  color: #065F46;
}
.config-result.error {
  background: var(--color-error-bg);
  border: 1px solid #FECACA;
  color: #991B1B;
}
.config-result-close {
  background: none;
  border: none;
  font-size: 1.1rem;
  cursor: pointer;
  color: inherit;
  opacity: 0.6;
  padding: 0 4px;
  line-height: 1;
}
.config-result-close:hover {
  opacity: 1;
}
@keyframes result-slide-in {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ── 空/错误状态 ── */
.config-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 64px 24px;
  color: var(--color-slate-400);
  gap: var(--space-2);
  border: 2px dashed var(--color-slate-200);
  border-radius: var(--radius-2xl);
  background: var(--color-white);
}
.config-empty-icon { font-size: 2.5rem; }
.config-empty h3 { margin: 0; color: var(--color-slate-500); font-weight: 600; font-size: 1.1rem; }
.config-empty p { margin: 0; font-size: 0.9rem; color: var(--color-slate-400); }

/* ── 配置分组 ── */
.config-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.config-group--advanced {
  margin-top: var(--space-1);
}

.config-group-header {
  padding: var(--space-4) var(--space-5);
  background: var(--color-white);
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xs);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.config-group-header--clickable {
  cursor: pointer;
  transition: all var(--transition-fast);
  user-select: none;
}
.config-group-header--clickable:hover {
  border-color: var(--color-gold-200);
  box-shadow: var(--shadow-md);
}
.config-group-header--open {
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
  border-color: var(--color-slate-200);
}

.config-group-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.config-group-badge {
  font-size: 1rem;
  color: var(--color-gold-500);
}
.config-group-badge--adv {
  color: var(--color-slate-400);
  font-size: 1rem;
}
.config-group-collapse-icon {
  font-size: 0.65rem;
  color: var(--color-slate-400);
  width: 14px;
  flex-shrink: 0;
  transition: transform 0.2s ease;
}
.config-group-title {
  flex: 1;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--color-navy-800);
}
.config-group-count {
  font-size: 0.72rem;
  color: var(--color-slate-400);
  background: var(--color-slate-100);
  padding: 1px 8px;
  border-radius: var(--radius-full);
}
.config-group-desc {
  margin: 0;
  font-size: 0.78rem;
  color: var(--color-slate-400);
  padding-left: calc(1rem + var(--space-2));
}

/* ── 配置卡片列表 ── */
.config-cards {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.config-cards--adv {
  background: var(--color-white);
  border: 1px solid var(--color-slate-200);
  border-top: none;
  border-radius: 0 0 var(--radius-xl) var(--radius-xl);
  padding: var(--space-2);
  margin-top: -1px;
}

/* ── 单个配置卡片 ── */
.config-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--color-white);
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-lg);
  transition: all var(--transition-fast);
  box-shadow: var(--shadow-xs);
}
.config-card:hover {
  border-color: var(--color-gold-200);
  box-shadow: var(--shadow-sm);
}
.config-card--basic {
  border-left: 3px solid var(--color-gold-500);
  padding-left: calc(var(--space-4) - 2px);
}
.config-card--advanced {
  border: none;
  border-radius: var(--radius-md);
  box-shadow: none;
  margin-bottom: 1px;
}
.config-card--advanced:hover {
  background: var(--color-slate-50);
  border-color: transparent;
}
.config-card + .config-card {
  margin-top: 2px;
}

.config-card-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.config-card-key-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.config-card-key {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--color-navy-900);
  letter-spacing: -0.01em;
}
.config-card-cat-tag {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  text-transform: uppercase;
}
.config-card-value-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding-left: 0;
}
.config-card-value {
  font-family: var(--font-mono);
  font-size: 0.82rem;
  color: var(--color-navy-600);
  word-break: break-all;
  line-height: 1.4;
}
.config-card-value--str {
  color: var(--color-navy-700);
}
.config-card-value--num {
  color: var(--color-indigo-600);
  font-weight: 600;
}
.config-card-value--obj {
  color: var(--color-slate-400);
  font-style: italic;
  font-size: 0.78rem;
}
.config-card-value--masked {
  letter-spacing: 2px;
  font-size: 0.9rem;
  color: var(--color-slate-400);
}
.config-card-bool-label {
  font-size: 0.78rem;
  color: var(--color-navy-500);
}

.config-card-actions {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
  align-items: center;
}

/* ── 折叠动画 ── */
.adv-collapse-enter-active {
  animation: adv-slide-down 0.25s ease-out;
}
.adv-collapse-leave-active {
  animation: adv-slide-down 0.2s ease-in reverse;
}
@keyframes adv-slide-down {
  from {
    max-height: 0;
    opacity: 0;
  }
  to {
    max-height: 2000px;
    opacity: 1;
  }
}

/* ── 编辑表单 ── */
.edit-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  padding: var(--space-2) 0;
}
.edit-form-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.edit-form-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--color-navy-700);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.edit-form-type {
  font-weight: 400;
  font-size: 0.75rem;
  color: var(--color-slate-400);
}
.edit-form-key {
  font-family: var(--font-mono);
  font-size: 0.9rem;
  padding: var(--space-2) var(--space-3);
  background: var(--color-slate-50);
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-md);
  color: var(--color-navy-800);
  user-select: all;
}
.edit-form-hint {
  margin: 4px 0 0;
  font-size: 0.75rem;
  color: var(--color-warning);
}

/* ── 详情弹窗 ── */
.detail-grid {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-2) 0;
}
.detail-row {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}
.detail-row--full {
  flex-direction: column;
  align-items: stretch;
  gap: var(--space-2);
}
.detail-key {
  font-size: 0.85rem;
  color: var(--color-slate-400);
  min-width: 72px;
  flex-shrink: 0;
}
.detail-val {
  font-size: 0.88rem;
  color: var(--color-navy-800);
}
.detail-val--mono {
  font-family: var(--font-mono);
  background: var(--color-slate-100);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 0.82rem;
}
.detail-pre {
  margin: 0;
  padding: var(--space-3);
  background: var(--color-slate-50);
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-md);
  font-family: var(--font-mono);
  font-size: 0.82rem;
  line-height: 1.5;
  max-height: 300px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--color-navy-800);
}

/* ── 响应式 ── */
@media (max-width: 768px) {
  .config-header {
    flex-direction: column;
    align-items: stretch;
  }
  .config-header-stats {
    justify-content: center;
  }
  .config-header-actions {
    justify-content: center;
  }
  .config-card {
    flex-direction: column;
    align-items: stretch;
  }
  .config-card-actions {
    justify-content: flex-end;
    padding-top: var(--space-2);
    border-top: 1px solid var(--color-slate-100);
  }
}
</style>
