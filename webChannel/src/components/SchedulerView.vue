<template>
  <div class="scheduler-page">
    <!-- ======== 紧凑顶栏 ======== -->
    <div class="scheduler-header">
      <div class="scheduler-header-left">
        <div class="scheduler-kicker">Scheduled Tasks</div>
        <h2>定时任务管理</h2>
      </div>
      <div class="scheduler-header-stats">
        <div class="scheduler-stat">
          <span class="scheduler-stat-value">{{ jobs.length }}</span>
          <span class="scheduler-stat-label">任务总数</span>
        </div>
        <span class="scheduler-stat-dot"></span>
        <div class="scheduler-stat">
          <span class="scheduler-stat-value" style="color: var(--color-success)">{{ activeCount }}</span>
          <span class="scheduler-stat-label">运行中</span>
        </div>
        <span class="scheduler-stat-dot"></span>
        <div class="scheduler-stat">
          <span class="scheduler-stat-value" style="color: var(--color-slate-400)">{{ jobs.length - activeCount }}</span>
          <span class="scheduler-stat-label">已暂停</span>
        </div>
      </div>
      <div class="scheduler-header-actions">
        <el-button size="small" type="primary" @click="openCreateDialog">＋ 新增</el-button>
        <el-button size="small" plain @click="checkHealth">❤ 健康</el-button>
        <el-button size="small" plain @click="fetchJobs" :loading="loading">⟳</el-button>
      </div>
    </div>

    <!-- 操作结果提示 -->
    <div v-if="actionResult" class="scheduler-result" :class="actionResult.type">
      {{ actionResult.message }}
    </div>

    <!-- ======== 加载 / 空状态 ======== -->
    <div v-if="loading && !jobs.length" class="empty-state"><p>加载中...</p></div>
    <div v-else-if="!jobs.length" class="empty-state">
      <div class="empty-icon">⏰</div>
      <h3>暂无定时任务</h3>
      <p>点击上方按钮创建你的第一个定时任务</p>
    </div>

    <!-- ======== 看板三栏 ======== -->
    <div v-else class="kanban-board">
      <!-- 运行中 -->
      <section class="kanban-column">
        <div class="kanban-column-header">
          <span class="kanban-column-dot" style="background: var(--color-success)"></span>
          <span class="kanban-column-title">运行中</span>
          <span class="kanban-column-count">{{ jobs.filter(j => j.enabled && !isJobEnded(j)).length }}</span>
        </div>
        <div class="kanban-column-body">
          <div v-for="job in jobs.filter(j => j.enabled && !isJobEnded(j))" :key="job.job_id" class="kanban-card">
            <div class="kanban-card-name">{{ job.name }}</div>
            <div class="kanban-card-prompt" :title="job.prompt">{{ job.prompt }}</div>
            <div class="kanban-card-meta">
              <el-tag size="small" effect="plain" type="default">{{ job.trigger_type }}</el-tag>
              <code class="kanban-card-expr">{{ job.trigger_expr }}</code>
            </div>
            <div class="kanban-card-next">
              <template v-if="job.next_run_time">{{ formatTime(job.next_run_time) }}</template>
              <template v-else>等待调度…</template>
            </div>
            <div class="kanban-card-actions">
              <el-button size="small" text @click="showJobDetail(job)">详情</el-button>
              <el-button size="small" text @click="showExecutions(job)">记录</el-button>
              <el-button size="small" text :loading="pausingId === job.job_id" @click="pauseJob(job)">暂停</el-button>
              <el-popconfirm title="确定删除？" confirm-button-text="删除" cancel-button-text="取消" @confirm="deleteJob(job)">
                <template #reference><el-button size="small" text type="danger" @click.stop>删除</el-button></template>
              </el-popconfirm>
            </div>
          </div>
        </div>
      </section>

      <!-- 已暂停 -->
      <section class="kanban-column">
        <div class="kanban-column-header">
          <span class="kanban-column-dot" style="background: var(--color-slate-400)"></span>
          <span class="kanban-column-title">已暂停</span>
          <span class="kanban-column-count">{{ jobs.filter(j => !j.enabled && !isJobEnded(j)).length }}</span>
        </div>
        <div class="kanban-column-body">
          <div v-for="job in jobs.filter(j => !j.enabled && !isJobEnded(j))" :key="job.job_id" class="kanban-card kanban-card--paused">
            <div class="kanban-card-name">{{ job.name }}</div>
            <div class="kanban-card-prompt" :title="job.prompt">{{ job.prompt }}</div>
            <div class="kanban-card-meta">
              <el-tag size="small" effect="plain" type="default">{{ job.trigger_type }}</el-tag>
              <code class="kanban-card-expr">{{ job.trigger_expr }}</code>
            </div>
            <div class="kanban-card-next">—</div>
            <div class="kanban-card-actions">
              <el-button size="small" text @click="showJobDetail(job)">详情</el-button>
              <el-button size="small" text @click="showExecutions(job)">记录</el-button>
              <el-button size="small" text :loading="resumingId === job.job_id" @click="resumeJob(job)">恢复</el-button>
              <el-popconfirm title="确定删除？" confirm-button-text="删除" cancel-button-text="取消" @confirm="deleteJob(job)">
                <template #reference><el-button size="small" text type="danger" @click.stop>删除</el-button></template>
              </el-popconfirm>
            </div>
          </div>
        </div>
      </section>

      <!-- 已结束 -->
      <section class="kanban-column">
        <div class="kanban-column-header">
          <span class="kanban-column-dot" style="background: var(--color-slate-300)"></span>
          <span class="kanban-column-title">已结束</span>
          <span class="kanban-column-count">{{ jobs.filter(j => isJobEnded(j)).length }}</span>
        </div>
        <div class="kanban-column-body">
          <div v-for="job in jobs.filter(j => isJobEnded(j))" :key="job.job_id" class="kanban-card kanban-card--ended">
            <div class="kanban-card-name">{{ job.name }}</div>
            <div class="kanban-card-prompt" :title="job.prompt">{{ job.prompt }}</div>
            <div class="kanban-card-meta">
              <el-tag size="small" effect="plain" type="default">{{ job.trigger_type }}</el-tag>
              <code class="kanban-card-expr">{{ job.trigger_expr }}</code>
            </div>
            <div class="kanban-card-next">已结束</div>
            <div class="kanban-card-actions">
              <el-button size="small" text @click="showJobDetail(job)">详情</el-button>
              <el-button size="small" text @click="showExecutions(job)">记录</el-button>
              <el-popconfirm title="确定删除？" confirm-button-text="删除" cancel-button-text="取消" @confirm="deleteJob(job)">
                <template #reference><el-button size="small" text type="danger" @click.stop>删除</el-button></template>
              </el-popconfirm>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- ======== 健康检查弹窗 ======== -->
    <el-dialog
      v-model="healthDialogVisible"
      title="调度器健康状态"
      width="480px"
      destroy-on-close
    >
      <template v-if="healthStatus">
        <div class="health-status">
          <div class="health-row">
            <span class="health-label">运行状态</span>
            <el-tag :type="healthStatus.running ? 'success' : 'danger'" effect="light">
              {{ healthStatus.running ? '运行中' : '未运行' }}
            </el-tag>
          </div>
          <div class="health-row">
            <span class="health-label">已注册任务</span>
            <span class="health-value">{{ healthStatus.jobs?.length ?? 0 }} 个</span>
          </div>
        </div>
      </template>
      <div v-else class="empty-state">
        <p>正在获取健康状态…</p>
      </div>
    </el-dialog>

    <!-- ======== 任务详情弹窗 ======== -->
    <el-dialog
      v-model="detailDialogVisible"
      :title="'📋 ' + (selectedJob?.name || '任务详情')"
      width="640px"
      destroy-on-close
    >
      <template v-if="selectedJob">
        <div class="dialog-section">
          <h4 class="dialog-label">基本信息</h4>
          <div class="dialog-info-grid">
            <div class="dialog-info-item">
              <span class="dialog-info-key">名称</span>
              <span class="dialog-info-val">{{ selectedJob.name }}</span>
            </div>
            <div class="dialog-info-item">
              <span class="dialog-info-key">任务 ID</span>
              <span class="dialog-info-val"><code>{{ selectedJob.job_id }}</code></span>
            </div>
            <div class="dialog-info-item">
              <span class="dialog-info-key">状态</span>
              <el-tag :type="jobStatusType(selectedJob)" effect="light" size="small">
                {{ jobStatusLabel(selectedJob) }}
              </el-tag>
            </div>
          </div>
        </div>
        <div class="dialog-section">
          <h4 class="dialog-label">触发配置</h4>
          <div class="dialog-info-grid">
            <div class="dialog-info-item">
              <span class="dialog-info-key">触发器类型</span>
              <el-tag size="small" effect="plain" type="default">{{ selectedJob.trigger_type }}</el-tag>
            </div>
            <div class="dialog-info-item">
              <span class="dialog-info-key">触发器表达式</span>
              <span class="dialog-info-val"><code>{{ selectedJob.trigger_expr }}</code></span>
            </div>
            <div class="dialog-info-item" v-if="selectedJob.timezone">
              <span class="dialog-info-key">时区</span>
              <span class="dialog-info-val">{{ selectedJob.timezone }}</span>
            </div>
            <div class="dialog-info-item">
              <span class="dialog-info-key">下次执行</span>
              <span class="dialog-info-val">
                <template v-if="isJobEnded(selectedJob)">已结束</template>
                <template v-else-if="selectedJob.next_run_time">{{ formatTime(selectedJob.next_run_time) }}</template>
                <template v-else-if="selectedJob.enabled">等待调度…</template>
                <template v-else>—</template>
              </span>
            </div>
          </div>
        </div>
        <div class="dialog-section">
          <h4 class="dialog-label">提示词</h4>
          <div class="dialog-content-box">
            <pre class="dialog-pre">{{ selectedJob.prompt }}</pre>
          </div>
        </div>
        <div class="dialog-section">
          <h4 class="dialog-label">时间信息</h4>
          <div class="dialog-info-grid">
            <div class="dialog-info-item">
              <span class="dialog-info-key">创建时间</span>
              <span class="dialog-info-val">{{ formatTime(selectedJob.created_at) }}</span>
            </div>
            <div class="dialog-info-item" v-if="selectedJob.updated_at">
              <span class="dialog-info-key">更新时间</span>
              <span class="dialog-info-val">{{ formatTime(selectedJob.updated_at) }}</span>
            </div>
            <div class="dialog-info-item">
              <span class="dialog-info-key">创建者</span>
              <span class="dialog-info-val">{{ selectedJob.created_by }}</span>
            </div>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- ======== 执行记录弹窗 ======== -->
    <el-dialog
      v-model="execDialogVisible"
      :title="'📊 执行记录 — ' + (execJobName || '')"
      width="720px"
      destroy-on-close
      class="exec-dialog"
    >
      <template v-if="executions.length > 0">
        <div class="exec-table-wrapper">
          <table class="exec-table">
            <thead>
              <tr>
                <th>#</th>
                <th>状态</th>
                <th>触发时间</th>
                <th>完成时间</th>
                <th>输出/错误</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(exec, idx) in executions" :key="exec.id">
                <td class="exec-idx">{{ idx + 1 }}</td>
                <td>
                  <el-tag
                    :type="exec.status === 'completed' ? 'success' : exec.status === 'failed' ? 'danger' : 'warning'"
                    effect="light"
                    size="small"
                  >
                    {{ exec.status === 'completed' ? '成功' : exec.status === 'failed' ? '失败' : exec.status === 'running' ? '运行中' : exec.status }}
                  </el-tag>
                </td>
                <td class="exec-time">{{ formatTime(exec.triggered_at) }}</td>
                <td class="exec-time">{{ exec.finished_at ? formatTime(exec.finished_at) : '—' }}</td>
                <td class="exec-output">
                  <template v-if="exec.output">
                    <el-popover
                      placement="bottom"
                      :width="400"
                      trigger="click"
                    >
                      <template #reference>
                        <el-button size="small" text type="primary">查看输出</el-button>
                      </template>
                      <pre class="exec-popover-content">{{ exec.output }}</pre>
                    </el-popover>
                  </template>
                  <template v-else-if="exec.error_message">
                    <el-popover
                      placement="bottom"
                      :width="400"
                      trigger="click"
                    >
                      <template #reference>
                        <el-button size="small" text type="danger">查看错误</el-button>
                      </template>
                      <pre class="exec-popover-content exec-error">{{ exec.error_message }}</pre>
                    </el-popover>
                  </template>
                  <span v-else class="exec-empty">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
      <div v-else class="empty-state">
        <p>暂无执行记录</p>
      </div>
    </el-dialog>

    <!-- ======== 新增任务弹窗 ======== -->
    <el-dialog
      v-model="createDialogVisible"
      title="新增定时任务"
      width="560px"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-form
        ref="createFormRef"
        :model="createForm"
        :rules="createFormRules"
        label-position="top"
        class="scheduler-form"
      >
        <el-form-item label="任务名称" prop="name">
          <el-input
            v-model="createForm.name"
            placeholder="例如：每日AI简报"
            maxlength="100"
          />
        </el-form-item>

        <el-form-item label="提示词" prop="prompt">
          <el-input
            v-model="createForm.prompt"
            type="textarea"
            :autosize="{ minRows: 3, maxRows: 8 }"
            placeholder="任务触发时发送给 AI 的提示词"
          />
        </el-form-item>

        <el-form-item label="触发器类型" prop="trigger_type">
          <el-radio-group v-model="createForm.trigger_type">
            <el-radio value="cron">Cron 表达式</el-radio>
            <el-radio value="interval">间隔秒数</el-radio>
            <el-radio value="date">特定日期</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="触发器表达式" prop="trigger_expr">
          <template v-if="createForm.trigger_type === 'cron'">
            <el-input
              v-model="createForm.trigger_expr"
              placeholder="例如：0 9 * * *（每天9点）"
            />
            <div class="form-tip">
              Cron 格式：分 时 日 月 周 （5 位，用空格分隔）
            </div>
          </template>
          <template v-else-if="createForm.trigger_type === 'interval'">
            <el-input-number
              v-model="createForm.trigger_expr"
              :min="1"
              :max="86400"
              :step="60"
              style="width: 100%"
            />
            <div class="form-tip">间隔时间，单位：秒（例如 3600 = 每小时）</div>
          </template>
          <template v-else>
            <el-input
              v-model="createForm.trigger_expr"
              placeholder="例如：2026-07-01 09:00:00"
            />
            <div class="form-tip">日期格式：YYYY-MM-DD HH:mm:ss</div>
          </template>
        </el-form-item>

        <el-form-item label="时区（可选）" prop="timezone">
          <el-input
            v-model="createForm.timezone"
            placeholder="默认为 Asia/Shanghai"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">
          创建
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import type {
  SchedulerJob,
  SchedulerExecution,
  SchedulerExecutionResponse,
  SchedulerHealthResponse,
  SchedulerCreateResponse,
} from '../types'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

// ── 状态 ──────────────────────────────────────────
const loading = ref(false)
const jobs = ref<SchedulerJob[]>([])
const actionResult = ref<{ type: string; message: string } | null>(null)

// ── 操作 loading 状态 ─────────────────────────────
const pausingId = ref<string | null>(null)
const resumingId = ref<string | null>(null)

const activeCount = computed(() => jobs.value.filter((j) => j.enabled).length)

// ── 健康检查 ──────────────────────────────────────
const healthDialogVisible = ref(false)
const healthStatus = ref<SchedulerHealthResponse | null>(null)

const checkHealth = async () => {
  healthDialogVisible.value = true
  healthStatus.value = null
  try {
    const res = await fetch('/v1/scheduler/health')
    if (res.ok) {
      healthStatus.value = await res.json()
    } else {
      healthStatus.value = { running: false, jobs: [] }
    }
  } catch {
    healthStatus.value = { running: false, jobs: [] }
  }
}

// ── 任务详情 ──────────────────────────────────────
const detailDialogVisible = ref(false)
const selectedJob = ref<SchedulerJob | null>(null)

const showJobDetail = async (job: SchedulerJob) => {
  selectedJob.value = null
  detailDialogVisible.value = true
  // 尝试获取最新详情
  try {
    const res = await fetch(`/v1/scheduler/jobs/${job.job_id}`)
    if (res.ok) {
      selectedJob.value = await res.json()
    } else {
      selectedJob.value = job
    }
  } catch {
    selectedJob.value = job
  }
}

// ── 执行记录 ──────────────────────────────────────
const execDialogVisible = ref(false)
const executions = ref<SchedulerExecution[]>([])
const execJobName = ref('')

const showExecutions = async (job: SchedulerJob) => {
  execJobName.value = job.name
  executions.value = []
  execDialogVisible.value = true
  try {
    const res = await fetch(`/v1/scheduler/jobs/${job.job_id}/executions?limit=50`)
    if (res.ok) {
      const data: SchedulerExecutionResponse = await res.json()
      executions.value = data.executions
    } else {
      ElMessage.error('获取执行记录失败')
    }
  } catch {
    ElMessage.error('网络错误')
  }
}

// ── 暂停 / 恢复 ──────────────────────────────────
const pauseJob = async (job: SchedulerJob) => {
  pausingId.value = job.job_id
  try {
    const res = await fetch(`/v1/scheduler/jobs/${job.job_id}/pause`, { method: 'PATCH' })
    if (res.ok) {
      job.enabled = false
      ElMessage.success('任务已暂停')
    } else {
      const err = await res.text()
      ElMessage.error(`暂停失败: ${err}`)
    }
  } catch {
    ElMessage.error('网络错误')
  } finally {
    pausingId.value = null
  }
}

const resumeJob = async (job: SchedulerJob) => {
  resumingId.value = job.job_id
  try {
    const res = await fetch(`/v1/scheduler/jobs/${job.job_id}/resume`, { method: 'PATCH' })
    if (res.ok) {
      job.enabled = true
      ElMessage.success('任务已恢复')
    } else {
      const err = await res.text()
      ElMessage.error(`恢复失败: ${err}`)
    }
  } catch {
    ElMessage.error('网络错误')
  } finally {
    resumingId.value = null
  }
}

// ── 删除 ──────────────────────────────────────────
const deleteJob = async (job: SchedulerJob) => {
  try {
    const res = await fetch(`/v1/scheduler/jobs/${job.job_id}`, { method: 'DELETE' })
    if (res.ok) {
      jobs.value = jobs.value.filter((j) => j.job_id !== job.job_id)
      ElMessage.success('任务已删除')
    } else {
      ElMessage.error('删除失败')
    }
  } catch {
    ElMessage.error('网络错误')
  }
}

// ── 新增任务 ──────────────────────────────────────
const createDialogVisible = ref(false)
const creating = ref(false)
const createFormRef = ref<FormInstance | null>(null)
const createForm = reactive({
  name: '',
  prompt: '',
  trigger_type: 'cron',
  trigger_expr: '',
  timezone: '',
})

const createFormRules: FormRules = {
  name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }],
  prompt: [{ required: true, message: '请输入提示词', trigger: 'blur' }],
  trigger_type: [{ required: true, message: '请选择触发器类型', trigger: 'change' }],
  trigger_expr: [{ required: true, message: '请输入触发器表达式', trigger: 'blur' }],
}

const openCreateDialog = () => {
  createForm.name = ''
  createForm.prompt = ''
  createForm.trigger_type = 'cron'
  createForm.trigger_expr = ''
  createForm.timezone = ''
  createDialogVisible.value = true
}

const submitCreate = async () => {
  const valid = await createFormRef.value?.validate().catch(() => false)
  if (!valid) return

  creating.value = true
  actionResult.value = null
  try {
    const payload: Record<string, unknown> = {
      name: createForm.name,
      prompt: createForm.prompt,
      trigger_type: createForm.trigger_type,
      trigger_expr: String(createForm.trigger_expr),
    }
    if (createForm.timezone.trim()) payload.timezone = createForm.timezone

    const res = await fetch('/v1/scheduler/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (res.ok) {
      const data: SchedulerCreateResponse = await res.json()
      actionResult.value = {
        type: 'success',
        message: data.message || `定时任务「${data.name}」已创建`,
      }
      createDialogVisible.value = false
      await fetchJobs()
    } else {
      const err = await res.text()
      actionResult.value = { type: 'error', message: `创建失败: ${err}` }
    }
  } catch {
    actionResult.value = { type: 'error', message: '网络错误，创建失败' }
  } finally {
    creating.value = false
  }
}

// ── 获取任务列表 ──────────────────────────────────
const fetchJobs = async () => {
  loading.value = true
  actionResult.value = null
  try {
    const res = await fetch('/v1/scheduler/jobs')
    if (res.ok) {
      const data = await res.json()
      jobs.value = data.jobs || []
    } else {
      ElMessage.error('获取任务列表失败')
    }
  } catch {
    ElMessage.error('网络错误')
  } finally {
    loading.value = false
  }
}

// ── 工具 ──────────────────────────────────────────
const formatTime = (iso: string) => {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

/** 判断 date 类型的定时任务是否已过期 */
const isDateExpired = (triggerExpr: string): boolean => {
  const d = new Date(triggerExpr)
  return !isNaN(d.getTime()) && d.getTime() < Date.now()
}

/** 判断任务是否已结束（date 触发器且时间已过） */
const isJobEnded = (job: SchedulerJob): boolean =>
  job.trigger_type === 'date' && isDateExpired(job.trigger_expr)

/** 任务状态标签文本 */
const jobStatusLabel = (job: SchedulerJob): string => {
  if (isJobEnded(job)) return '已结束'
  return job.enabled ? '运行中' : '已暂停'
}

/** 任务状态标签类型 */
const jobStatusType = (job: SchedulerJob): string => {
  if (isJobEnded(job)) return 'info'
  return job.enabled ? 'success' : 'info'
}

// ── 生命周期 ──────────────────────────────────────
defineExpose({ fetchJobs, jobs })

onMounted(() => {
  fetchJobs()
})
</script>

<style scoped>
.scheduler-page {
  padding: var(--space-5) var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-height: 100%;
}

/* ── 紧凑顶栏 ── */
.scheduler-header {
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
.scheduler-header-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.scheduler-kicker {
  font-size: 0.7rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-gold-600);
  font-weight: 600;
}
.scheduler-header-left h2 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--color-navy-900);
}
.scheduler-header-stats {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.scheduler-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
}
.scheduler-stat-value {
  font-size: 1rem;
  font-weight: 700;
  color: var(--color-navy-800);
}
.scheduler-stat-label {
  font-size: 0.68rem;
  color: var(--color-slate-400);
}
.scheduler-stat-dot {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: var(--color-slate-300);
}
.scheduler-header-actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

/* ── 操作结果 ── */
.scheduler-result {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  font-size: 0.9rem;
  line-height: 1.5;
}
.scheduler-result.success {
  background: var(--color-success-bg);
  border: 1px solid #A7F3D0;
  color: #065F46;
}
.scheduler-result.error {
  background: var(--color-error-bg);
  border: 1px solid #FECACA;
  color: #991B1B;
}

/* ── 空状态 ── */
.empty-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 48px; color: var(--color-slate-400); gap: var(--space-2);
  border: 2px dashed var(--color-slate-200); border-radius: var(--radius-2xl); background: var(--color-white);
}
.empty-icon { font-size: 2.5rem; }
.empty-state h3 { margin: 0; color: var(--color-slate-500); font-weight: 600; }
.empty-state p { margin: 0; font-size: 0.9rem; color: var(--color-slate-400); }

/* ── 看板 ── */
.kanban-board {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
  min-height: 0;
}
.kanban-column {
  display: flex;
  flex-direction: column;
  background: var(--color-slate-50);
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-xl);
  overflow: hidden;
}
.kanban-column-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--color-white);
  border-bottom: 1px solid var(--color-slate-200);
  flex-shrink: 0;
}
.kanban-column-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.kanban-column-title {
  flex: 1;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--color-navy-700);
}
.kanban-column-count {
  font-size: 0.72rem;
  color: var(--color-slate-400);
  background: var(--color-slate-100);
  padding: 0 6px;
  border-radius: var(--radius-full);
}
.kanban-column-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-2);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.kanban-card {
  background: var(--color-white);
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-lg);
  padding: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  box-shadow: var(--shadow-xs);
  transition: all var(--transition-fast);
}
.kanban-card:hover {
  box-shadow: var(--shadow-sm);
  border-color: var(--color-gold-200);
}
.kanban-card--paused {
  opacity: 0.75;
}
.kanban-card--ended {
  opacity: 0.5;
}
.kanban-card-name {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--color-navy-900);
}
.kanban-card-prompt {
  font-size: 0.78rem;
  color: var(--color-slate-500);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kanban-card-meta {
  display: flex;
  align-items: center;
  gap: 4px;
}
.kanban-card-expr {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  background: var(--color-slate-100);
  padding: 1px 5px;
  border-radius: 3px;
  color: var(--color-navy-600);
}
.kanban-card-next {
  font-size: 0.75rem;
  color: var(--color-slate-400);
}
.kanban-card-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
  padding-top: var(--space-1);
  border-top: 1px solid var(--color-slate-100);
}

/* ── 看板卡片 MCP 标签 ── */
.kanban-card-mcp {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
}

/* ── Dialog MCP 标签 ── */
.dialog-mcp-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

/* ── 表单 ── */
.scheduler-form { margin-top: var(--space-2); }
.form-tip {
  font-size: 0.78rem;
  color: var(--color-slate-400);
  margin-top: 4px;
  line-height: 1.4;
}

/* ── Dialog ── */
.dialog-section { margin-bottom: var(--space-5); }
.dialog-label {
  font-size: 0.9rem;
  color: var(--color-navy-900);
  margin: 0 0 var(--space-2);
  font-weight: 600;
}
.dialog-info-grid { display: flex; flex-direction: column; gap: var(--space-3); }
.dialog-info-item { display: flex; align-items: center; gap: var(--space-3); }
.dialog-info-key { font-size: 0.85rem; color: var(--color-slate-400); min-width: 80px; flex-shrink: 0; }
.dialog-info-val { color: var(--color-navy-800); }
.dialog-content-box {
  border: 1px solid var(--color-slate-200); border-radius: var(--radius-lg); overflow: hidden;
  background: var(--color-slate-50);
}
.dialog-pre {
  margin: 0; padding: var(--space-4);
  max-height: 200px; overflow: auto;
  font-size: 0.85rem; line-height: 1.7;
  white-space: pre-wrap; word-break: break-word;
  color: var(--color-navy-800);
}

/* ── 健康状态 ── */
.health-status {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: var(--space-2) 0;
}
.health-row {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}
.health-label {
  font-size: 0.9rem;
  color: var(--color-slate-500);
  min-width: 100px;
}
.health-value {
  font-size: 0.9rem;
  color: var(--color-navy-800);
  font-weight: 600;
}

/* ── 执行记录 ── */
.exec-table-wrapper {
  max-height: 480px;
  overflow-y: auto;
}
.exec-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}
.exec-table th {
  background: var(--color-slate-100);
  color: var(--color-navy-700);
  font-weight: 600;
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid var(--color-slate-200);
  position: sticky;
  top: 0;
  z-index: 1;
}
.exec-table td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--color-slate-100);
  color: var(--color-navy-700);
}
.exec-idx {
  color: var(--color-slate-400);
  font-size: 0.8rem;
}
.exec-time {
  white-space: nowrap;
  font-size: 0.82rem;
  color: var(--color-slate-500);
}
.exec-output {
  min-width: 100px;
}
.exec-empty {
  color: var(--color-slate-300);
}
.exec-popover-content {
  margin: 0;
  max-height: 300px;
  overflow: auto;
  font-size: 0.82rem;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
  color: var(--color-navy-800);
}
.exec-popover-content.exec-error {
  color: var(--color-error);
}

/* ── 响应式 ── */
@media (max-width: 768px) {
  .grid-cards {
    grid-template-columns: 1fr;
  }
  .hero-card {
    flex-direction: column;
  }
  .hero-stats {
    min-width: 0;
  }
}
</style>
