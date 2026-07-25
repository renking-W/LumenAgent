<template>
  <section class="users-view">
    <div class="users-heading">
      <div>
        <span class="users-heading__date">{{ overview.usage_date || '今日' }}</span>
        <h2>用户管理</h2>
      </div>
      <el-button type="primary" @click="openCreate">创建用户</el-button>
    </div>

    <div class="metrics-strip" aria-label="账号概览">
      <div class="metric">
        <span>账号总数</span>
        <strong>{{ overview.total_users }}</strong>
      </div>
      <div class="metric">
        <span>启用账号</span>
        <strong>{{ overview.enabled_users }}</strong>
      </div>
      <div class="metric">
        <span>无限额度</span>
        <strong>{{ overview.unlimited_users }}</strong>
      </div>
      <div class="metric">
        <span>今日对话</span>
        <strong>{{ overview.used_rounds_today }}</strong>
      </div>
    </div>

    <div class="users-toolbar">
      <el-input
        v-model="searchText"
        class="users-search"
        clearable
        maxlength="64"
        placeholder="搜索用户名"
        @keyup.enter="applyFilters"
        @clear="applyFilters"
      />
      <el-select v-model="statusFilter" class="status-filter" @change="applyFilters">
        <el-option label="全部状态" value="all" />
        <el-option label="已启用" value="enabled" />
        <el-option label="已禁用" value="disabled" />
      </el-select>
      <el-button @click="applyFilters">查询</el-button>
    </div>

    <div v-loading="loading" class="users-table-wrap">
      <el-table :data="users" row-key="id" empty-text="没有符合条件的账号">
        <el-table-column label="账号" min-width="180">
          <template #default="{ row }">
            <div class="account-cell">
              <strong>{{ row.username }}</strong>
              <span>{{ shortId(row.id) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="角色" width="104">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'warning' : 'info'" effect="plain">
              {{ row.role === 'admin' ? '管理员' : '普通用户' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="今日额度" width="132">
          <template #default="{ row }">
            <span class="quota-value">{{ quotaLabel(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="session_count" label="会话" width="86" />
        <el-table-column label="状态" width="96">
          <template #default="{ row }">
            <span class="state-label" :class="{ 'state-label--off': !row.enabled }">
              <i aria-hidden="true"></i>
              {{ row.enabled ? '启用' : '禁用' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="最近登录" min-width="158">
          <template #default="{ row }">
            <span class="time-value">{{ formatTime(row.last_login_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="246" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button link @click="openSessions(row)">会话</el-button>
              <el-button link @click="openEdit(row)">编辑</el-button>
              <el-button link @click="openPassword(row)">重置密码</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="users-pagination">
      <span>共 {{ overview.total }} 个账号</span>
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="overview.total"
        layout="prev, pager, next"
        @current-change="loadUsers"
      />
    </div>

    <el-dialog v-model="createVisible" title="创建用户" width="min(480px, calc(100vw - 32px))">
      <el-form label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="createForm.username" maxlength="64" autocomplete="off" />
        </el-form-item>
        <el-form-item label="初始密码">
          <el-input
            v-model="createForm.password"
            type="password"
            maxlength="256"
            autocomplete="new-password"
            show-password
          />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="角色">
            <el-select v-model="createForm.role">
              <el-option label="普通用户" value="user" />
              <el-option label="管理员" value="admin" />
            </el-select>
          </el-form-item>
          <el-form-item label="每日轮次">
            <el-input-number
              v-model="createForm.daily_round_limit"
              :min="0"
              :max="10000"
              :disabled="createForm.unlimited"
              controls-position="right"
            />
          </el-form-item>
        </div>
        <el-form-item label="无限额度">
          <el-switch v-model="createForm.unlimited" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="createSubmitting" @click="submitCreate">
          创建
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editVisible" title="编辑用户" width="min(480px, calc(100vw - 32px))">
      <div v-if="editingUser" class="dialog-account">
        <strong>{{ editingUser.username }}</strong>
        <span>{{ editingUser.id }}</span>
      </div>
      <el-form label-position="top">
        <div class="form-grid">
          <el-form-item label="角色">
            <el-select v-model="editForm.role" :disabled="editingSelf">
              <el-option label="普通用户" value="user" />
              <el-option label="管理员" value="admin" />
            </el-select>
          </el-form-item>
          <el-form-item label="每日轮次">
            <el-input-number
              v-model="editForm.daily_round_limit"
              :min="0"
              :max="10000"
              :disabled="editForm.unlimited"
              controls-position="right"
            />
          </el-form-item>
        </div>
        <div class="switch-row">
          <div>
            <strong>无限额度</strong>
            <span>不计入每日轮次限制</span>
          </div>
          <el-switch v-model="editForm.unlimited" />
        </div>
        <div class="switch-row">
          <div>
            <strong>账号启用</strong>
            <span>禁用后无法继续通过身份校验</span>
          </div>
          <el-switch v-model="editForm.enabled" :disabled="editingSelf" />
        </div>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSubmitting" @click="submitEdit">
          保存更改
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="passwordVisible" title="重置密码" width="min(420px, calc(100vw - 32px))">
      <div v-if="passwordUser" class="dialog-account">
        <strong>{{ passwordUser.username }}</strong>
        <span>新密码至少 8 位</span>
      </div>
      <el-form label-position="top">
        <el-form-item label="新密码">
          <el-input
            v-model="newPassword"
            type="password"
            maxlength="256"
            autocomplete="new-password"
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="passwordVisible = false">取消</el-button>
        <el-button type="primary" :loading="passwordSubmitting" @click="submitPassword">
          重置密码
        </el-button>
      </template>
    </el-dialog>

    <el-drawer
      v-model="sessionsVisible"
      :title="sessionUser ? sessionUser.username + ' 的会话' : '用户会话'"
      size="min(620px, 92vw)"
    >
      <div v-loading="sessionsLoading" class="session-list">
        <article v-for="session in sessionResult.sessions" :key="session.id" class="session-row">
          <div>
            <strong>{{ session.title || '未命名会话' }}</strong>
            <span>{{ session.id }}</span>
          </div>
          <div class="session-row__meta">
            <el-tag size="small" effect="plain">
              {{ session.kind === 1 ? '定时任务' : '普通会话' }}
            </el-tag>
            <time>{{ formatTime(session.updated_at) }}</time>
          </div>
        </article>
        <el-empty
          v-if="!sessionsLoading && sessionResult.sessions.length === 0"
          description="该用户暂无会话"
        />
      </div>
      <div v-if="sessionResult.total > sessionPageSize" class="drawer-pagination">
        <el-pagination
          v-model:current-page="sessionPage"
          :page-size="sessionPageSize"
          :total="sessionResult.total"
          layout="prev, pager, next"
          @current-change="loadSessions"
        />
      </div>
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  createAdminUser,
  listAdminUsers,
  listAdminUserSessions,
  resetAdminUserPassword,
  updateAdminUser,
  type AdminRole,
  type AdminUser,
  type AdminUserList,
  type AdminUserSessionList,
} from '../services/admin'
import { authState } from '../services/auth'

// 用户列表、筛选条件与顶部概览共享同一次分页请求。
const pageSize = 20
const loading = ref(false)
const users = ref<AdminUser[]>([])
const currentPage = ref(1)
const searchText = ref('')
const appliedSearch = ref('')
const statusFilter = ref<'all' | 'enabled' | 'disabled'>('all')
const overview = reactive<Omit<AdminUserList, 'users'>>({
  total: 0,
  total_users: 0,
  enabled_users: 0,
  unlimited_users: 0,
  used_rounds_today: 0,
  usage_date: '',
})

const loadUsers = async () => {
  loading.value = true
  try {
    const enabled = statusFilter.value === 'all'
      ? undefined
      : statusFilter.value === 'enabled'
    const result = await listAdminUsers({
      limit: pageSize,
      offset: (currentPage.value - 1) * pageSize,
      query: appliedSearch.value,
      enabled,
    })
    users.value = result.users
    overview.total = result.total
    overview.total_users = result.total_users
    overview.enabled_users = result.enabled_users
    overview.unlimited_users = result.unlimited_users
    overview.used_rounds_today = result.used_rounds_today
    overview.usage_date = result.usage_date
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '无法读取用户列表')
  } finally {
    loading.value = false
  }
}

const applyFilters = () => {
  appliedSearch.value = searchText.value.trim()
  currentPage.value = 1
  void loadUsers()
}

// 创建账号弹窗状态。
const createVisible = ref(false)
const createSubmitting = ref(false)
const createForm = reactive({
  username: '',
  password: '',
  role: 'user' as AdminRole,
  daily_round_limit: 3,
  unlimited: false,
})

const resetCreateForm = () => {
  createForm.username = ''
  createForm.password = ''
  createForm.role = 'user'
  createForm.daily_round_limit = 3
  createForm.unlimited = false
}

const openCreate = () => {
  resetCreateForm()
  createVisible.value = true
}

const submitCreate = async () => {
  if (!createForm.username.trim()) {
    ElMessage.warning('请输入用户名')
    return
  }
  if (createForm.password.length < 8) {
    ElMessage.warning('密码至少需要 8 位')
    return
  }
  createSubmitting.value = true
  try {
    await createAdminUser({
      username: createForm.username.trim(),
      password: createForm.password,
      role: createForm.role,
      daily_round_limit: createForm.daily_round_limit,
      unlimited: createForm.unlimited,
    })
    createVisible.value = false
    ElMessage.success('用户已创建')
    await loadUsers()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '创建用户失败')
  } finally {
    createSubmitting.value = false
  }
}

// 权限编辑状态；当前管理员的角色和启用状态在前后端双重保护。
const editVisible = ref(false)
const editSubmitting = ref(false)
const editingUser = ref<AdminUser | null>(null)
const editForm = reactive({
  role: 'user' as AdminRole,
  daily_round_limit: 3,
  unlimited: false,
  enabled: true,
})
const editingSelf = computed(
  () => editingUser.value?.id === authState.user.value?.id,
)

const openEdit = (user: AdminUser) => {
  editingUser.value = user
  editForm.role = user.role
  editForm.daily_round_limit = user.daily_round_limit
  editForm.unlimited = user.unlimited
  editForm.enabled = user.enabled
  editVisible.value = true
}

const submitEdit = async () => {
  if (!editingUser.value) return
  editSubmitting.value = true
  try {
    await updateAdminUser(editingUser.value.id, {
      role: editForm.role,
      daily_round_limit: editForm.daily_round_limit,
      unlimited: editForm.unlimited,
      enabled: editForm.enabled,
    })
    editVisible.value = false
    ElMessage.success('用户配置已更新')
    await loadUsers()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '更新用户失败')
  } finally {
    editSubmitting.value = false
  }
}

// 密码重置独立提交，避免与权限配置互相覆盖。
const passwordVisible = ref(false)
const passwordSubmitting = ref(false)
const passwordUser = ref<AdminUser | null>(null)
const newPassword = ref('')

const openPassword = (user: AdminUser) => {
  passwordUser.value = user
  newPassword.value = ''
  passwordVisible.value = true
}

const submitPassword = async () => {
  if (!passwordUser.value) return
  if (newPassword.value.length < 8) {
    ElMessage.warning('密码至少需要 8 位')
    return
  }
  passwordSubmitting.value = true
  try {
    await resetAdminUserPassword(passwordUser.value.id, newPassword.value)
    passwordVisible.value = false
    newPassword.value = ''
    ElMessage.success('密码已重置')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '重置密码失败')
  } finally {
    passwordSubmitting.value = false
  }
}

// 会话抽屉按用户独立分页加载。
const sessionsVisible = ref(false)
const sessionsLoading = ref(false)
const sessionUser = ref<AdminUser | null>(null)
const sessionPage = ref(1)
const sessionPageSize = 20
const sessionResult = reactive<AdminUserSessionList>({
  total: 0,
  sessions: [],
})

const openSessions = (user: AdminUser) => {
  sessionUser.value = user
  sessionPage.value = 1
  sessionResult.total = 0
  sessionResult.sessions = []
  sessionsVisible.value = true
  void loadSessions()
}

const loadSessions = async () => {
  if (!sessionUser.value) return
  sessionsLoading.value = true
  try {
    const result = await listAdminUserSessions(
      sessionUser.value.id,
      sessionPageSize,
      (sessionPage.value - 1) * sessionPageSize,
    )
    sessionResult.total = result.total
    sessionResult.sessions = result.sessions
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '无法读取用户会话')
  } finally {
    sessionsLoading.value = false
  }
}

const shortId = (value: string) => value.length > 16
  ? value.slice(0, 8) + '…' + value.slice(-4)
  : value

const quotaLabel = (user: AdminUser) => {
  if (user.role === 'admin') return '管理员'
  if (user.unlimited) return '不限'
  return user.used_rounds + ' / ' + user.daily_round_limit
}

const formatTime = (value: string | null) => {
  if (!value) return '从未登录'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}

onMounted(() => {
  void loadUsers()
})
</script>

<style scoped>
.users-view {
  min-width: 0;
}

.users-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
}

.users-heading__date {
  color: #758078;
  font-family: Bahnschrift, Consolas, monospace;
  font-size: 0.68rem;
}

.users-heading h2 {
  margin: 5px 0 0;
  font-size: 1.12rem;
  letter-spacing: 0;
}

.metrics-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-top: 20px;
  border-top: 1px solid #cfd8d1;
  border-bottom: 1px solid #cfd8d1;
  background: rgba(255, 255, 255, 0.52);
}

.metric {
  min-width: 0;
  padding: 19px 22px;
  border-right: 1px solid #dce3dd;
}

.metric:last-child {
  border-right: 0;
}

.metric span {
  display: block;
  color: #6e7b72;
  font-size: 0.72rem;
}

.metric strong {
  display: block;
  margin-top: 8px;
  font-family: Bahnschrift, Consolas, monospace;
  font-size: 1.55rem;
  line-height: 1;
}

.users-toolbar {
  display: flex;
  gap: 10px;
  margin-top: 24px;
}

.users-search {
  width: min(320px, 100%);
}

.status-filter {
  width: 138px;
}

.users-table-wrap {
  min-height: 320px;
  margin-top: 14px;
  overflow-x: auto;
  border: 1px solid #d7dfd8;
  border-radius: 6px;
  background: #ffffff;
}

.account-cell {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.account-cell strong {
  overflow: hidden;
  color: #1e2b22;
  font-size: 0.84rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.account-cell span,
.dialog-account span,
.session-row span,
.time-value {
  color: #78847b;
  font-family: Bahnschrift, Consolas, monospace;
  font-size: 0.7rem;
  letter-spacing: 0;
}

.quota-value {
  font-family: Bahnschrift, Consolas, monospace;
  font-size: 0.8rem;
}

.state-label {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #2f6b45;
  font-size: 0.76rem;
}

.state-label i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
}

.state-label--off {
  color: #8a9690;
}

.row-actions {
  display: flex;
  align-items: center;
  white-space: nowrap;
}

.users-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 58px;
  color: #758078;
  font-size: 0.76rem;
}

.form-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 14px;
}

.form-grid :deep(.el-select),
.form-grid :deep(.el-input-number) {
  width: 100%;
}

.dialog-account {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: -2px 0 20px;
  padding-bottom: 14px;
  border-bottom: 1px solid #e0e6e1;
}

.switch-row {
  min-height: 58px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  border-top: 1px solid #e3e8e4;
}

.switch-row > div {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.switch-row strong {
  font-size: 0.82rem;
}

.switch-row span {
  color: #7a867d;
  font-size: 0.72rem;
}

.session-list {
  min-height: 220px;
}

.session-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 15px 2px;
  border-bottom: 1px solid #e0e6e1;
}

.session-row > div:first-child {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.session-row strong,
.session-row span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-row strong {
  font-size: 0.82rem;
}

.session-row__meta {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 10px;
}

.session-row time {
  min-width: 78px;
  color: #748078;
  font-family: Bahnschrift, Consolas, monospace;
  font-size: 0.68rem;
}

.drawer-pagination {
  display: flex;
  justify-content: flex-end;
  padding-top: 18px;
}

:deep(.el-button--primary) {
  --el-button-bg-color: #2f6b45;
  --el-button-border-color: #2f6b45;
  --el-button-hover-bg-color: #285c3c;
  --el-button-hover-border-color: #285c3c;
  --el-button-active-bg-color: #214d32;
  --el-button-active-border-color: #214d32;
}

:deep(.el-table) {
  --el-table-header-bg-color: #f5f7f5;
  --el-table-row-hover-bg-color: #f7faf7;
  --el-table-border-color: #e0e6e1;
  color: #26342a;
}

:deep(.el-table th.el-table__cell) {
  height: 44px;
  color: #657168;
  font-size: 0.72rem;
  font-weight: 600;
}

:deep(.el-table td.el-table__cell) {
  height: 56px;
}

@media (max-width: 760px) {
  .metrics-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .metric:nth-child(2) {
    border-right: 0;
  }

  .metric:nth-child(-n + 2) {
    border-bottom: 1px solid #dce3dd;
  }

  .users-toolbar {
    flex-wrap: wrap;
  }

  .users-search {
    width: 100%;
  }

  .users-pagination > span {
    display: none;
  }

  .users-pagination {
    justify-content: flex-end;
  }

  .form-grid {
    grid-template-columns: 1fr;
    gap: 0;
  }

  .session-row {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>