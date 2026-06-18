<template>
  <div class="vm-page" :class="{ 'vm-page--terminal': activeVM }">

    <!-- ================================================================ -->
    <!-- [模式 A] 列表模式 — 展示所有 VM 卡片 -->
    <!-- ================================================================ -->
    <template v-if="!activeVM">
      <!-- 顶栏 -->
      <div class="vm-header">
        <div class="vm-header-left">
          <div class="vm-kicker">Virtual Machines</div>
          <h2>虚拟机管理</h2>
        </div>
        <div class="vm-header-stats">
          <div class="vm-stat">
            <span class="vm-stat-value">{{ vms.length }}</span>
            <span class="vm-stat-label">总数</span>
          </div>
          <span class="vm-stat-div"></span>
          <div class="vm-stat">
            <span class="vm-stat-value" style="color: var(--color-success)">{{ connectedCount }}</span>
            <span class="vm-stat-label">已连接</span>
          </div>
          <span class="vm-stat-div"></span>
          <div class="vm-stat">
            <span class="vm-stat-value" style="color: var(--color-error)">{{ errorCount }}</span>
            <span class="vm-stat-label">异常</span>
          </div>
        </div>
        <div class="vm-header-actions">
          <el-button size="small" type="primary" @click="openAddDialog">＋ 新增</el-button>
          <el-button size="small" plain @click="fetchVMs" :loading="loading">⟳</el-button>
        </div>
      </div>

      <!-- 操作结果横幅 -->
      <div v-if="actionResult" class="vm-result" :class="actionResult.type">
        <span>{{ actionResult.message }}</span>
        <button class="vm-result-close" @click="actionResult = null">×</button>
      </div>

      <!-- 空状态 -->
      <div v-if="loading && !vms.length" class="empty-state"><p>加载中...</p></div>
      <div v-else-if="!vms.length" class="empty-state">
        <div class="empty-icon">🖥️</div>
        <h3>暂无虚拟机</h3>
        <p>点击「＋ 新增」注册你的第一台虚拟机</p>
      </div>

      <!-- VM 卡片网格 -->
      <div v-else class="vm-grid">
        <article
          v-for="vm in vms"
          :key="vm.vm_id"
          class="vm-card"
          :class="[`vm-card--${vm.status}`, { 'vm-card--animated': animatedCards.has(vm.vm_id) }]"
          @click="openTerminal(vm)"
        >
          <div class="vm-card-head">
            <div class="vm-card-status-row">
              <span class="vm-card-dot" :class="`vm-card-dot--${vm.status}`">
                <span v-if="vm.status === 'connecting'" class="vm-card-dot-ring"></span>
              </span>
              <span class="vm-card-status-label" :class="`vm-card-status-label--${vm.status}`">
                {{ statusLabel(vm.status) }}
              </span>
              <span v-if="vm.status === 'error' && vm.error_message" class="vm-card-error-tip" :title="vm.error_message">⚠</span>
            </div>
            <h3 class="vm-card-name">{{ vm.vm_id }}</h3>
          </div>
          <div class="vm-card-body">
            <div class="vm-card-info-row">
              <span class="vm-card-info-icon">👤</span>
              <span class="vm-card-info-text">{{ vm.username }}</span>
            </div>
            <div class="vm-card-info-row">
              <span class="vm-card-info-icon">🔗</span>
              <span class="vm-card-info-text vm-card-info-text--mono">{{ vm.host }}:{{ vm.port }}</span>
            </div>
            <div v-if="vm.description" class="vm-card-desc">{{ vm.description }}</div>
            <div v-if="vm.last_connected_at" class="vm-card-time">
              <span class="vm-card-time-icon">🕐</span>
              <span>{{ formatTime(vm.last_connected_at) }}</span>
            </div>
            <div v-if="vm.status === 'error' && vm.error_message" class="vm-card-errmsg">
              {{ vm.error_message }}
            </div>
          </div>
          <!-- 卡片底部操作（阻止冒泡） -->
          <div class="vm-card-actions" @click.stop>
            <template v-if="vm.status === 'connected'">
              <el-button size="small" plain :loading="disconnectingId === vm.vm_id" @click="disconnectVM(vm)">断开</el-button>
            </template>
            <template v-else-if="vm.status === 'connecting'">
              <el-button size="small" loading disabled>连接中</el-button>
            </template>
            <template v-else>
              <el-button size="small" plain :loading="connectingId === vm.vm_id" :disabled="connectingId === vm.vm_id" @click="connectVM(vm)">🔌 连接</el-button>
            </template>
            <el-button size="small" plain @click="openEditDialog(vm)">编辑</el-button>
            <el-popconfirm
              title="确定删除此虚拟机？"
              confirm-button-text="删除"
              cancel-button-text="取消"
              :disabled="vm.status === 'connected'"
              @confirm="deleteVM(vm)"
            >
              <template #reference>
                <el-button size="small" type="danger" plain :disabled="vm.status === 'connected'" @click.stop>删除</el-button>
              </template>
            </el-popconfirm>
          </div>
        </article>
      </div>
    </template>

    <!-- ================================================================ -->
    <!-- [模式 B] 全屏终端模式 — 覆盖整个右侧区域 -->
    <!-- ================================================================ -->
    <template v-else>
      <!-- 顶部状态栏 -->
      <div class="vm-topbar">
        <button class="vm-topbar-back" @click="closeTerminal" title="返回列表">
          <span class="vm-topbar-back-arrow">←</span>
          <span class="vm-topbar-back-label">返回</span>
        </button>
        <span class="vm-topbar-dot" :class="`vm-topbar-dot--${activeVM.status}`"></span>
        <span class="vm-topbar-name">{{ activeVM.vm_id }}</span>
        <span class="vm-topbar-host">{{ activeVM.username }}@{{ activeVM.host }}:{{ activeVM.port }}</span>
        <span class="vm-topbar-status" :class="`vm-topbar-status--${activeVM.status}`">{{ statusLabel(activeVM.status) }}</span>

        <div class="vm-topbar-spacer"></div>

        <el-button v-if="activeVM.status === 'connected'" size="small" plain @click="openLogDialog(activeVM)">📋 日志</el-button>
        <el-button
          v-if="activeVM.status === 'connected'"
          size="small"
          plain
          :loading="disconnectingId === activeVM.vm_id"
          @click="disconnectCurrentVM"
        >断开</el-button>
        <el-button
          v-else-if="activeVM.status === 'disconnected'"
          size="small"
          plain
          :loading="connectingId === activeVM.vm_id"
          @click="connectCurrentVM"
        >🔌 连接</el-button>
        <el-button size="small" plain @click="openEditDialog(activeVM)">编辑</el-button>
      </div>

      <!-- 终端主体（flex:1 填满剩余空间） -->
      <div class="vm-terminal-wrap">
        <!-- xterm.js 终端挂载点 -->
        <div ref="xtermRef" class="xterm-container"></div>

        <!-- 审批等待（覆盖在终端之上） -->
        <div v-if="execState === 'approval'" class="vm-approval-overlay">
          <div class="vm-approval-box">
            <div class="vm-approval-icon">🔒</div>
            <div class="vm-approval-text">该命令匹配了危险模式，需要审批后才能执行</div>
            <div class="vm-approval-cmd">{{ pendingCommand }}</div>
            <div class="vm-approval-actions">
              <el-button type="danger" @click="rejectExecution">❌ 拒绝执行</el-button>
              <el-button type="primary" @click="approveExecution">✅ 批准执行</el-button>
            </div>
          </div>
        </div>

        <!-- 空状态（无输出时的引导提示） -->
        <div v-if="!hasOutput && execState === 'idle'" class="vm-terminal-empty">
          <div class="vm-terminal-empty-icon">⎈</div>
          <p>输入命令后按 <kbd>Enter</kbd> 执行</p>
        </div>
      </div>

    </template>

    <!-- ================================================================ -->
    <!-- 新增 / 编辑 弹窗 -->
    <!-- ================================================================ -->
    <el-dialog
      v-model="formDialogVisible"
      :title="isEditing ? '编辑虚拟机' : '新增虚拟机'"
      width="560px"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-form ref="formRef" :model="formData" :rules="formRules" label-position="top" class="vm-form">
        <el-form-item label="名称（vm_id）" prop="vm_id">
          <el-input v-model="formData.vm_id" placeholder="例如：ubuntu-dev" :disabled="isEditing" maxlength="64" />
          <div class="vm-form-tip" v-if="!isEditing">自定义名称，用于标识这台机器</div>
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="16">
            <el-form-item label="主机地址" prop="host"><el-input v-model="formData.host" placeholder="IP 或域名" /></el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="端口" prop="port"><el-input-number v-model="formData.port" :min="1" :max="65535" style="width:100%" /></el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="用户名" prop="username"><el-input v-model="formData.username" placeholder="例如：root" /></el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="formData.password" type="password" show-password :placeholder="isEditing ? '留空则不修改密码' : 'SSH 登录密码'" />
        </el-form-item>
        <el-form-item label="描述（可选）" prop="description">
          <el-input v-model="formData.description" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" placeholder="这台机器的用途说明..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">{{ isEditing ? '保存修改' : '创建' }}</el-button>
      </template>
    </el-dialog>

    <!-- ================================================================ -->
    <!-- 日志查看弹窗 -->
    <!-- ================================================================ -->
    <el-dialog
      v-model="logDialogVisible"
      :title="'📋 终端日志 — ' + (logVM?.vm_id || '')"
      width="780px"
      destroy-on-close
      class="log-dialog"
    >
      <div class="log-bar">
        <span class="log-bar-label">日志文件：{{ logVM?.host || '' }}.log</span>
        <span class="log-bar-total">共 {{ logTotalLines }} 行</span>
        <el-button size="small" plain @click="refreshLog" :loading="logLoading">⟳ 刷新</el-button>
      </div>
      <div class="log-terminal">
        <!-- xterm.js 日志终端渲染 -->
        <div ref="logXtermRef" class="log-xterm"></div>
        <!-- 加载/空状态覆盖 -->
        <div v-if="logLoading && !logHasContent" class="log-status">加载中...</div>
        <div v-else-if="!logHasContent" class="log-status log-status--empty">
          <p>暂无日志内容</p>
          <p class="log-status-sub">连接并执行命令后将在此显示终端记录</p>
        </div>
      </div>
      <template #footer>
        <div class="log-footer">
          <span class="log-footer-connect" :class="logConnected ? 'log-footer-connect--on' : 'log-footer-connect--off'">
            <span class="log-footer-dot"></span>{{ logConnected ? '已连接' : '已断开' }}
          </span>
          <el-button @click="logDialogVisible = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>

  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import type { VMListResponseItem, VMRegisterRequest } from '../types'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'

// ── 状态 ──────────────────────────────────────────
const loading = ref(false)
const vms = ref<VMListResponseItem[]>([])
const actionResult = ref<{ type: string; message: string } | null>(null)
const animatedCards = ref(new Set<string>())
const connectingId = ref<string | null>(null)
const disconnectingId = ref<string | null>(null)

const connectedCount = computed(() => vms.value.filter((v) => v.status === 'connected').length)
const errorCount = computed(() => vms.value.filter((v) => v.status === 'error').length)

const statusLabel = (s: string): string => ({
  disconnected: '未连接', connecting: '连接中', connected: '已连接', error: '异常',
}[s] || s)

// ── 终端模式状态 ──────────────────────────────────
const activeVM = ref<VMListResponseItem | null>(null)
const promptStr = ref('$ ')

const execState = ref<'idle' | 'approval' | 'running' | 'done' | 'error'>('idle')
const execAbort = ref<AbortController | null>(null)
const hasOutput = ref(false)

const pendingCommand = ref('')
const pendingSessionId = ref('')
const pendingToolCallId = ref('')

// ── xterm.js ──
const xtermRef = ref<HTMLElement | null>(null)
let term: Terminal | null = null
let fitAddon: FitAddon | null = null

// ══════════════════════════════════════════════════════════════════
// xterm.js 终端生命周期
// ══════════════════════════════════════════════════════════════════

function initTerminal(vm: VMListResponseItem) {
  disposeTerminal()
  if (!xtermRef.value) return

  fitAddon = new FitAddon()
  term = new Terminal({
    // disableStdin: true, ← 删掉这行，默认就是 false，开启输入
    cursorBlink: true,
    cursorStyle: 'block',
    fontSize: 14,
    fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace",
    theme: {
      background: '#0F172A',
      foreground: '#E2E8F0',
      cursor: '#EAB308',
      selectionBackground: '#334155',
      black: '#1E293B',
      red: '#EF4444',
      green: '#10B981',
      yellow: '#EAB308',
      blue: '#6366F1',
      magenta: '#A78BFA',
      cyan: '#22D3EE',
      white: '#E2E8F0',
      brightBlack: '#475569',
      brightRed: '#F87171',
      brightGreen: '#34D399',
      brightYellow: '#FBBF24',
      brightBlue: '#818CF8',
      brightMagenta: '#C4B5FD',
      brightCyan: '#67E8F9',
      brightWhite: '#F8FAFC',
    },
    allowTransparency: false,
    // rows: 30, ← 删掉这行，交给 fit 自动计算
  })

  term.loadAddon(fitAddon)
  term.open(xtermRef.value)

  // 先适配尺寸，再做后续操作
  requestAnimationFrame(() => {
    fitAddon?.fit()
    // 尺寸稳定后再聚焦，避免焦点丢失
    term?.focus()
  })

  // ── 居中欢迎信息 ──
  const gray = '\x1b[90m'
  const gold = '\x1b[33m'
  const reset = '\x1b[0m'
  const cols = term?.cols ?? 80
  const center = (text: string) => ' '.repeat(Math.max(0, Math.floor((cols - text.length) / 2)))

  const deco = '──────────────────────────────────'
  const titleLine = '  ⎈ 虚拟机终端'
  const hostLine = `  ${vm.username}@${vm.host}:${vm.port}`
  const hintLine = '  输入命令后按 Enter 执行'

  term.writeln('')
  term.write(gray)
  term.writeln(center(deco) + deco)
  term.write(center(titleLine) + '  ')
  term.write(gold + '⎈' + gray)
  term.writeln(' 虚拟机终端')
  term.writeln(center(hostLine) + hostLine)
  term.writeln(center(hintLine) + hintLine)
  term.writeln(center(deco) + deco + reset)

  // ── 注册键盘输入处理 ──
  inputBuffer = ''
  term.onData(handleTerminalInput)

  // 点击终端容器 → 用官方 API 聚焦（更稳定）
  const clickHandler = () => term?.focus()
  xtermRef.value.addEventListener('click', clickHandler)
}

/** 加载历史日志并写入终端，结束后显示提示符 */
const loadTerminalHistory = async (vmId: string) => {
  try {
    const res = await fetch(`/v1/vm/${vmId}/log?lines=200`)
    if (!res.ok) return
    const data = await res.json()
    const lines: string[] = data.lines || []
    if (lines.length === 0) return
    for (const line of lines) {
      term?.writeln(line)
    }
    hasOutput.value = true
  } catch { /* 静默 */ }
  finally {
    writePrompt()
    term?.focus()
  }
}

function disposeTerminal() {
  if (term) {
    term.dispose()
    term = null
    fitAddon = null
  }
}

function fitTerminal() {
  try { fitAddon?.fit() } catch { /* 容器不可见时忽略 */ }
}

let resizeObserver: ResizeObserver | null = null

function setupResizeObserver() {
  teardownResizeObserver()
  if (!xtermRef.value) return
  resizeObserver = new ResizeObserver(() => fitTerminal())
  resizeObserver.observe(xtermRef.value)
}

function teardownResizeObserver() {
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
}

// ══════════════════════════════════════════════════════════════════
// xterm.js 键盘输入处理（替代底部输入栏）
// ══════════════════════════════════════════════════════════════════

let inputBuffer = ''

function handleTerminalInput(data: string) {
  if (!term) return

  const code = data.charCodeAt(0)

  // Ctrl+C → 中断（任何状态下都允许）
  if (code === 3) {
    inputBuffer = ''
    // 如果在审批状态，退出审批并关闭覆盖层
    if (execState.value === 'approval') {
      execState.value = 'idle'
      pendingCommand.value = ''
    }
    interruptExecution()
    term.write('\r\n^C')
    writePrompt()
    return
  }

  // 运行中或审批中，除 Ctrl+C 外不处理其他输入
  if (execState.value === 'running' || execState.value === 'approval') return

  // Enter → 发送命令
  if (code === 13) {
    const cmd = inputBuffer.trim()
    inputBuffer = ''
    term.write('\r\n')
    if (cmd) {
      sendCommand(cmd)
      // sendCommand 执行完后自动写 prompt
    } else {
      writePrompt()
    }
    return
  }

  // Backspace → 删除前一字符
  if (code === 127) {
    if (inputBuffer.length > 0) {
      inputBuffer = inputBuffer.slice(0, -1)
      term.write('\b \b')
    }
    return
  }

  // 可打印字符
  if (code >= 32) {
    inputBuffer += data
    term.write(data)
  }
}

/** 在终端中写入提示符 (user@host:~$ ) */
function writePrompt() {
  term?.write(promptStr.value)
}

// ── 表单状态 ──────────────────────────────────────
const formDialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref<string | null>(null)
const submitting = ref(false)
const formRef = ref<FormInstance | null>(null)
const formData = reactive({ vm_id: '', host: '', port: 22, username: '', password: '', description: '' })
const formRules: FormRules = {
  vm_id: [
    { required: true, message: '请输入名称', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_-]+$/, message: '仅允许字母、数字、下划线和中划线', trigger: 'blur' },
  ],
  host: [{ required: true, message: '请输入主机地址', trigger: 'blur' }],
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ validator: (_: unknown, value: string) => isEditing.value || value ? Promise.resolve() : Promise.reject(new Error('请输入密码')), trigger: 'blur' }],
}

// ── 日志状态 ──────────────────────────────────────
const logDialogVisible = ref(false)
const logVM = ref<VMListResponseItem | null>(null)
const logLoading = ref(false)
const logTotalLines = ref(0)
const logConnected = ref(false)
const logHasContent = ref(false)
const logXtermRef = ref<HTMLElement | null>(null)
let logTerm: Terminal | null = null
let logFitAddon: FitAddon | null = null

// ══════════════════════════════════════════════════════════════════
// VM 列表操作
// ══════════════════════════════════════════════════════════════════

const showResult = (type: 'success' | 'error', message: string) => {
  actionResult.value = { type, message }
  setTimeout(() => { actionResult.value = null }, 5000)
}

const fetchVMs = async () => {
  loading.value = true
  actionResult.value = null
  try {
    const res = await fetch('/v1/vm/list')
    if (res.ok) vms.value = await res.json()
    else showResult('error', '获取列表失败')
  } catch { showResult('error', '网络错误') }
  finally { loading.value = false }
}

const connectVM = async (vm: VMListResponseItem) => {
  connectingId.value = vm.vm_id
  vm.status = 'connecting'
  try {
    const res = await fetch(`/v1/vm/${vm.vm_id}/connect`, { method: 'POST' })
    if (res.ok) {
      const updated: VMListResponseItem = await res.json()
      Object.assign(vm, updated)
      ElMessage.success(`「${vm.vm_id}」连接成功`)
    } else {
      vm.status = 'disconnected'
      showResult('error', `连接失败: ${await res.text()}`)
    }
  } catch {
    vm.status = 'disconnected'
    showResult('error', '连接失败: 网络错误')
  } finally { connectingId.value = null }
}

const disconnectVM = async (vm: VMListResponseItem) => {
  disconnectingId.value = vm.vm_id
  try {
    const res = await fetch(`/v1/vm/${vm.vm_id}/disconnect`, { method: 'POST' })
    if (res.ok) {
      vm.status = 'disconnected'; vm.last_connected_at = null; vm.error_message = null
      ElMessage.success(`「${vm.vm_id}」已断开`)
    } else showResult('error', `断开失败: ${await res.text()}`)
  } catch { showResult('error', '断开失败: 网络错误') }
  finally { disconnectingId.value = null }
}

const deleteVM = async (vm: VMListResponseItem) => {
  try {
    const res = await fetch(`/v1/vm/${vm.vm_id}`, { method: 'DELETE' })
    if (res.ok) { vms.value = vms.value.filter((v) => v.vm_id !== vm.vm_id); ElMessage.success('已删除') }
    else ElMessage.error(`删除失败: ${await res.text()}`)
  } catch { ElMessage.error('网络错误') }
}

// ══════════════════════════════════════════════════════════════════
// 全屏终端 进入 / 退出
// ══════════════════════════════════════════════════════════════════

const openTerminal = async (vm: VMListResponseItem) => {
  // 重置终端状态
  activeVM.value = vm
  execState.value = 'idle'
  execAbort.value = null
  hasOutput.value = false
  pendingCommand.value = ''
  pendingSessionId.value = ''
  pendingToolCallId.value = ''
  promptStr.value = `${vm.username}@${vm.host}:~$ `

  // 如果未连接，自动尝试连接
  if (vm.status === 'disconnected') {
    vm.status = 'connecting'
    try {
      const res = await fetch(`/v1/vm/${vm.vm_id}/connect`, { method: 'POST' })
      if (res.ok) {
        const updated: VMListResponseItem = await res.json()
        Object.assign(vm, updated)
      } else {
        vm.status = 'disconnected'
        ElMessage.warning('连接失败，可手动点击「连接」按钮重试')
      }
    } catch {
      vm.status = 'disconnected'
    }
  }

  await nextTick()
  // 初始化 xterm.js 终端
  initTerminal(vm)
  setupResizeObserver()
  // 加载历史日志
  loadTerminalHistory(vm.vm_id)
}

const closeTerminal = () => {
  if (execState.value === 'running' || execState.value === 'approval') {
    execAbort.value?.abort()
  }
  execAbort.value = null
  execState.value = 'idle'
  hasOutput.value = false
  teardownResizeObserver()
  disposeTerminal()
  activeVM.value = null
}

const connectCurrentVM = () => {
  if (activeVM.value) connectVM(activeVM.value)
}
const disconnectCurrentVM = () => {
  if (activeVM.value) disconnectVM(activeVM.value)
}

// ══════════════════════════════════════════════════════════════════
// 命令执行（SSE 流式读取，实时显示输出）
// ══════════════════════════════════════════════════════════════════

/** 解析 SSE data 行中的 JSON 事件 */
function parseSSEEvent(data: string): Record<string, unknown> | null {
  try { return JSON.parse(data) as Record<string, unknown> } catch { return null }
}

const sendCommand = async (cmd?: string) => {
  const command = (cmd ?? '').trim()
  if (!command || !activeVM.value || execState.value === 'running') return

  const vm = activeVM.value

  // 如果未连接，先尝试连接
  if (vm.status !== 'connected') {
    try {
      vm.status = 'connecting'
      const res = await fetch(`/v1/vm/${vm.vm_id}/connect`, { method: 'POST' })
      if (res.ok) {
        const updated: VMListResponseItem = await res.json()
        Object.assign(vm, updated)
      } else {
        vm.status = 'disconnected'
        term?.writeln('[31m❌ 连接失败，无法执行命令[0m')
        writePrompt()
        return
      }
    } catch {
      vm.status = 'disconnected'
      term?.writeln('[31m❌ 连接失败: 网络错误[0m')
      writePrompt()
      return
    }
  }

  execState.value = 'running'
  execAbort.value = new AbortController()

  try {
    const res = await fetch(`/v1/vm/${vm.vm_id}/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command, timeout: 30 }),
      signal: execAbort.value.signal,
    })
    if (!res.ok) {
      term?.writeln(`[31m❌ 请求失败: ${await res.text()}[0m`)
      execState.value = 'idle'
      writePrompt()
      return
    }

    // ── 读取 SSE 流 ──────────────────────────────────────
    const reader = res.body?.getReader()
    if (!reader) {
      term?.writeln('[31m❌ 无法读取响应流[0m')
      execState.value = 'idle'
      writePrompt()
      return
    }

    const decoder = new TextDecoder()
    let buffer = ''
    let shouldStop = false
    const outputChunks: string[] = []
    let cmdExitCode = -1

    while (!shouldStop) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // SSE 消息以 分割
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || '' // 保留未完成的部分

      for (const part of parts) {
        for (const line of part.split('\n')) {
          if (line.startsWith('data: ')) {
            const event = parseSSEEvent(line.slice(6))
            if (!event) continue
            const type = event.type as string
            switch (type) {
              case 'stdout':
                term?.write(event.content as string)
                outputChunks.push(event.content as string)
                hasOutput.value = true
                break
              case 'approval':
                execState.value = 'approval'
                pendingCommand.value = (event.command as string) || ''
                pendingSessionId.value = (event.session_id as string) || ''
                pendingToolCallId.value = (event.tool_call_id as string) || ''
                break
              case 'exit_code':
                cmdExitCode = event.code as number
                break
              case 'done':
                term?.writeln('')
                hasOutput.value = true
                shouldStop = true
                break
              case 'error':
                term?.writeln(`\x1b[31m❌ ${event.message as string || '命令执行出错'}\x1b[0m`)
                hasOutput.value = true
                shouldStop = true
                break
            }
          }
        }
        if (shouldStop) break
      }
    }

    // 🖊 前端主动保存日志
    if (command) {
      saveCommandLog(vm.vm_id, promptStr.value + command, outputChunks.join(''), cmdExitCode)
    }
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      // 用户中断 — 不做额外处理
    } else {
      term?.writeln(`[31m❌ 命令执行异常: ${error}[0m`)
    }
  } finally {
    execAbort.value = null
    // 如果处于审批状态(SSE 流因等待审批而暂停)，不要重置 execState
    if (execState.value === 'approval') {
      return
    }
    execState.value = 'idle'
    writePrompt()
    term?.focus()
  }
}


const approveExecution = async () => {
  if (!pendingSessionId.value || !pendingToolCallId.value) return
  try {
    await fetch('/v1/chat/stream/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: pendingSessionId.value,
        approvals: { [pendingToolCallId.value]: true },
      }),
    })
    // 切换到运行状态，关闭审批覆盖层；SSE 流会继续输出 stdout
    execState.value = 'running'
  } catch { showResult('error', '审批请求失败') }
}

/** 拒绝危险命令 */
const rejectExecution = async () => {
  if (!pendingSessionId.value || !pendingToolCallId.value) return
  try {
    await fetch('/v1/chat/stream/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: pendingSessionId.value,
        approvals: { [pendingToolCallId.value]: false },
      }),
    })
    execState.value = 'idle'
    term?.writeln('\x1b[31m❌ 命令已被拒绝执行\x1b[0m')
    writePrompt()
    // 中断 SSE 流清理
    execAbort.value?.abort()
  } catch { showResult('error', '审批请求失败') }
}

const interruptExecution = () => {
  execAbort.value?.abort()
}

/** 前端主动保存命令执行日志到后端 */
const saveCommandLog = async (
  vmId: string,
  command: string,
  output: string,
  exitCode: number,
) => {
  try {
    await fetch(`/v1/vm/${vmId}/log/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command, output, exit_code: exitCode }),
    })
  } catch {
    // 静默失败，日志保存不应影响用户体验
  }
}

// ══════════════════════════════════════════════════════════════════
// 新增 / 编辑
// ══════════════════════════════════════════════════════════════════

const openAddDialog = () => {
  isEditing.value = false; editingId.value = null
  formData.vm_id = ''; formData.host = ''; formData.port = 22
  formData.username = ''; formData.password = ''; formData.description = ''
  formDialogVisible.value = true
}

const openEditDialog = (vm: VMListResponseItem) => {
  isEditing.value = true; editingId.value = vm.vm_id
  formData.vm_id = vm.vm_id; formData.host = vm.host; formData.port = vm.port
  formData.username = vm.username; formData.password = ''; formData.description = vm.description
  formDialogVisible.value = true
}

const submitForm = async () => {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (isEditing.value && editingId.value) {
      const payload: Record<string, unknown> = {}
      const orig = vms.value.find((v) => v.vm_id === editingId.value)
      if (formData.host !== orig?.host) payload.host = formData.host
      if (formData.port !== orig?.port) payload.port = formData.port
      if (formData.username !== orig?.username) payload.username = formData.username
      if (formData.password) payload.password = formData.password
      if (formData.description !== orig?.description) payload.description = formData.description
      if (Object.keys(payload).length === 0) { showResult('success', '无变更'); formDialogVisible.value = false; return }
      const res = await fetch(`/v1/vm/${editingId.value}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      if (res.ok) { showResult('success', '已更新'); formDialogVisible.value = false; await fetchVMs() }
      else showResult('error', `更新失败: ${await res.text()}`)
    } else {
      const payload: VMRegisterRequest = { vm_id: formData.vm_id, host: formData.host, port: formData.port, username: formData.username, password: formData.password, description: formData.description }
      const res = await fetch('/v1/vm/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      if (res.ok) { showResult('success', '已注册'); formDialogVisible.value = false; await fetchVMs() }
      else showResult('error', `注册失败: ${await res.text()}`)
    }
  } catch { showResult('error', '网络错误') }
  finally { submitting.value = false }
}

// ══════════════════════════════════════════════════════════════════
// 日志查看（xterm.js 渲染）
// ══════════════════════════════════════════════════════════════════

function initLogTerminal() {
  disposeLogTerminal()
  if (!logXtermRef.value) return

  logFitAddon = new FitAddon()
  logTerm = new Terminal({
    disableStdin: true,
    cursorBlink: false,
    cursorStyle: 'block',
    fontSize: 13,
    fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace",
    theme: {
      background: '#0F172A',
      foreground: '#E2E8F0',
      cursor: '#EAB308',
      selectionBackground: '#334155',
      black: '#1E293B',
      red: '#EF4444',
      green: '#10B981',
      yellow: '#EAB308',
      blue: '#6366F1',
      magenta: '#A78BFA',
      cyan: '#22D3EE',
      white: '#E2E8F0',
      brightBlack: '#475569',
      brightRed: '#F87171',
      brightGreen: '#34D399',
      brightYellow: '#FBBF24',
      brightBlue: '#818CF8',
      brightMagenta: '#C4B5FD',
      brightCyan: '#67E8F9',
      brightWhite: '#F8FAFC',
    },
    rows: 20,
    cols: 80,
  })
  logTerm.loadAddon(logFitAddon)
  logTerm.open(logXtermRef.value)
  requestAnimationFrame(() => logFitAddon?.fit())
}

function disposeLogTerminal() {
  if (logTerm) {
    logTerm.dispose()
    logTerm = null
    logFitAddon = null
  }
}

function writeLogContent(lines: string[]) {
  if (!logTerm || lines.length === 0) return
  logTerm.write(lines.join('\n'))
  logTerm.write('\n')
  logHasContent.value = true
}

const openLogDialog = async (vm: VMListResponseItem) => {
  logVM.value = vm
  logTotalLines.value = 0
  logConnected.value = false
  logHasContent.value = false
  logDialogVisible.value = true
  // 等待 dialog 渲染完成后再初始化 xterm
  await nextTick()
  initLogTerminal()
  await fetchLog(vm.vm_id)
}

const fetchLog = async (vmId: string) => {
  logLoading.value = true
  try {
    const res = await fetch(`/v1/vm/${vmId}/log?lines=200`)
    if (res.ok) {
      const data = await res.json()
      const lines: string[] = data.lines || []
      logTotalLines.value = data.total_lines || 0
      logConnected.value = data.connected || false
      writeLogContent(lines)
    }
  } catch { /* ignore */ }
  finally {
    logLoading.value = false
  }
}
const refreshLog = () => {
  if (!logVM.value || !logTerm) return
  // 清除旧内容重新写入
  logTerm.reset()
  logHasContent.value = false
  fetchLog(logVM.value.vm_id)
}

// ── 工具 ──────────────────────────────────────────
const formatTime = (iso: string | null): string => {
  if (!iso) return '-'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '-'
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

// 日志弹窗关闭时销毁 xterm 实例（destroy-on-close 会移除 DOM）
watch(logDialogVisible, (visible) => {
  if (!visible) disposeLogTerminal()
})

// ── 生命周期 ──────────────────────────────────────
onMounted(fetchVMs)
onUnmounted(() => {
  disposeTerminal()
  teardownResizeObserver()
})
</script>

<style scoped>
/* ================================================================
   VM Page — 双模式：列表 / 全屏终端
   ================================================================ */

.vm-page {
  padding: var(--space-5) var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-height: 100%;
  transition: all var(--transition-slow);
}

/* ── 全屏终端模式：零 padding，填满父容器 ── */
.vm-page--terminal {
  padding: 0;
  gap: 0;
  height: 100%;
  overflow: hidden;
  background: var(--color-navy-900);
}

/* ════════════════════════════════════════════════════════════════
   列表模式样式
   ════════════════════════════════════════════════════════════════ */

.vm-header {
  display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;
  gap: var(--space-3); padding: var(--space-4) var(--space-5);
  background: var(--color-white); border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-2xl); box-shadow: var(--shadow-sm);
}
.vm-header-left { display: flex; flex-direction: column; gap: 2px; }
.vm-kicker { font-size: 0.7rem; letter-spacing: 0.1em; text-transform: uppercase; color: var(--color-gold-600); font-weight: 600; }
.vm-header-left h2 { margin: 0; font-size: 1.1rem; font-weight: 600; color: var(--color-navy-900); }
.vm-header-stats { display: flex; align-items: center; gap: var(--space-3); }
.vm-stat { display: flex; flex-direction: column; align-items: center; gap: 1px; }
.vm-stat-value { font-size: 1rem; font-weight: 700; color: var(--color-navy-800); }
.vm-stat-label { font-size: 0.68rem; color: var(--color-slate-400); }
.vm-stat-div { width: 3px; height: 3px; border-radius: 50%; background: var(--color-slate-300); }
.vm-header-actions { display: flex; gap: var(--space-2); flex-wrap: wrap; }

.vm-result {
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--space-3) var(--space-4); border-radius: var(--radius-lg);
  font-size: 0.9rem; line-height: 1.5; animation: vm-result-in 0.25s ease;
}
.vm-result.success { background: var(--color-success-bg); border: 1px solid #A7F3D0; color: #065F46; }
.vm-result.error { background: var(--color-error-bg); border: 1px solid #FECACA; color: #991B1B; }
.vm-result-close { background: none; border: none; font-size: 1.1rem; cursor: pointer; color: inherit; opacity: 0.6; padding: 0 4px; line-height: 1; }
.vm-result-close:hover { opacity: 1; }
@keyframes vm-result-in { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: translateY(0); } }

.empty-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 48px; color: var(--color-slate-400); gap: var(--space-2);
  border: 2px dashed var(--color-slate-200); border-radius: var(--radius-2xl); background: var(--color-white);
}
.empty-icon { font-size: 2.5rem; }
.empty-state h3 { margin: 0; color: var(--color-slate-500); font-weight: 600; }
.empty-state p { margin: 0; font-size: 0.9rem; color: var(--color-slate-400); }

/* ── VM 卡片 ── */
.vm-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-4); }

.vm-card {
  background: var(--color-white); border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-xl); overflow: visible;
  box-shadow: var(--shadow-xs); transition: all var(--transition-normal);
  display: flex; flex-direction: column;
  cursor: pointer;
}
.vm-card:hover { box-shadow: var(--shadow-md); border-color: var(--color-gold-300); transform: translateY(-2px); }

/* 状态左侧彩色边框 */
.vm-card--connected { border-left: 4px solid var(--color-success); }
.vm-card--error { border-left: 4px solid var(--color-error); }
.vm-card--connecting { border-left: 4px solid var(--color-warning); }
.vm-card--disconnected { border-left: 4px solid var(--color-slate-300); }

.vm-card--animated { animation: vm-card-flash 0.6s ease; }
@keyframes vm-card-flash { 0% { background: var(--color-slate-50); } 50% { background: var(--color-gold-50); } 100% { background: var(--color-white); } }

.vm-card-head { padding: var(--space-4) var(--space-4) var(--space-2); display: flex; flex-direction: column; gap: var(--space-2); }
.vm-card-status-row { display: flex; align-items: center; gap: 6px; }

.vm-card-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; position: relative; }
.vm-card-dot--connected { background: var(--color-success); box-shadow: 0 0 6px rgba(16,185,129,0.5); }
.vm-card-dot--disconnected { background: var(--color-slate-300); }
.vm-card-dot--connecting { background: var(--color-warning); }
.vm-card-dot--error { background: var(--color-error); }
.vm-card-dot-ring { position: absolute; inset: -4px; border-radius: 50%; border: 2px solid var(--color-warning); animation: vm-pulse-ring 1.2s ease-out infinite; }
@keyframes vm-pulse-ring { 0% { transform: scale(0.8); opacity: 1; } 100% { transform: scale(1.6); opacity: 0; } }

.vm-card-status-label { font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
.vm-card-status-label--connected { color: var(--color-success); }
.vm-card-status-label--disconnected { color: var(--color-slate-400); }
.vm-card-status-label--connecting { color: var(--color-warning); }
.vm-card-status-label--error { color: var(--color-error); }
.vm-card-error-tip { margin-left: auto; font-size: 0.85rem; cursor: help; color: var(--color-error); }

.vm-card-name { margin: 0; font-size: 1.05rem; font-weight: 700; color: var(--color-navy-900); font-family: var(--font-mono); letter-spacing: -0.01em; }
.vm-card-body { padding: var(--space-2) var(--space-4) var(--space-3); display: flex; flex-direction: column; gap: var(--space-1); flex: 1; }
.vm-card-info-row { display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: var(--color-navy-700); }
.vm-card-info-icon { width: 18px; text-align: center; flex-shrink: 0; font-size: 0.8rem; }
.vm-card-info-text--mono { font-family: var(--font-mono); font-size: 0.82rem; color: var(--color-navy-600); }
.vm-card-desc { margin: var(--space-1) 0 0; font-size: 0.82rem; color: var(--color-slate-500); line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; line-clamp: 2; }
.vm-card-time { margin-top: auto; padding-top: var(--space-1); font-size: 0.75rem; color: var(--color-slate-400); display: flex; align-items: center; gap: 4px; }
.vm-card-time-icon { font-size: 0.75rem; }
.vm-card-errmsg { margin-top: var(--space-1); padding: var(--space-1) var(--space-2); background: var(--color-error-bg); border: 1px solid #FECACA; border-radius: var(--radius-sm); font-size: 0.75rem; color: #991B1B; line-height: 1.4; max-height: 40px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.vm-card-actions { padding: var(--space-2) var(--space-4) var(--space-4); display: flex; flex-wrap: wrap; gap: 6px; border-top: 1px solid var(--color-slate-100); padding-top: var(--space-3); }

/* ════════════════════════════════════════════════════════════════
   全屏终端模式样式
   ════════════════════════════════════════════════════════════════ */

/* 顶部状态栏（亮色，紧凑） */
.vm-topbar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-4);
  background: var(--color-navy-800);
  border-bottom: 1px solid var(--color-navy-700);
  flex-shrink: 0;
  min-height: 44px;
}
.vm-topbar-back {
  display: flex; align-items: center; gap: 4px;
  background: none; border: 1px solid transparent;
  color: var(--color-slate-300); font-size: 0.82rem; cursor: pointer;
  padding: 4px 8px; border-radius: var(--radius-sm);
  transition: all var(--transition-fast); font-family: inherit;
}
.vm-topbar-back:hover { background: rgba(255,255,255,0.06); color: var(--color-white); }
.vm-topbar-back-arrow { font-size: 1rem; }
.vm-topbar-back-label { }
.vm-topbar-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.vm-topbar-dot--connected { background: var(--color-success); box-shadow: 0 0 6px rgba(16,185,129,0.5); }
.vm-topbar-dot--disconnected { background: var(--color-slate-400); }
.vm-topbar-dot--connecting { background: var(--color-warning); }
.vm-topbar-dot--error { background: var(--color-error); }
.vm-topbar-name { font-weight: 600; font-size: 0.9rem; color: var(--color-white); font-family: var(--font-mono); }
.vm-topbar-host { font-size: 0.78rem; color: var(--color-slate-400); font-family: var(--font-mono); }
.vm-topbar-status { font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
.vm-topbar-status--connected { color: var(--color-success); }
.vm-topbar-status--disconnected { color: var(--color-slate-400); }
.vm-topbar-status--connecting { color: var(--color-warning); }
.vm-topbar-status--error { color: var(--color-error); }
.vm-topbar-spacer { flex: 1; }
.vm-topbar :deep(.el-button) { --el-button-text-color: var(--color-slate-300); --el-button-border-color: var(--color-navy-600); --el-button-bg-color: transparent; }
.vm-topbar :deep(.el-button:hover) { --el-button-text-color: var(--color-white); --el-button-border-color: var(--color-slate-400); }

/* 终端包裹器 — xterm.js 容器 */
.vm-terminal-wrap {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
  background: var(--color-navy-900);
}

/* xterm.js 挂载点：填满容器 */
.xterm-container {
  flex: 1;
  min-height: 0;
  padding: var(--space-1) 0;
}
.xterm-container :deep(.xterm) {
  height: 100%;
  padding: 0 var(--space-3);
}

/* 终端空状态（覆盖在 xterm 之上，无输出时显示） */
.vm-terminal-empty {
  position: absolute;
  inset: 0;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  color: var(--color-slate-500); gap: var(--space-2);
  pointer-events: none;
}
.vm-terminal-empty-icon { font-size: 2rem; opacity: 0.3; }
.vm-terminal-empty p { margin: 0; font-size: 0.88rem; }
.vm-terminal-empty kbd {
  display: inline-block;
  padding: 1px 7px;
  font-size: 0.78rem;
  font-family: var(--font-mono);
  background: var(--color-navy-700);
  border: 1px solid var(--color-navy-600);
  border-radius: 4px;
  color: var(--color-slate-300);
}

/* ── 审批覆盖层（盖在 xterm 之上） ── */
.vm-approval-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: var(--space-8) var(--space-4);
  background: rgba(15, 23, 42, 0.85);
  z-index: 10;
}
.vm-approval-box {
  background: var(--color-navy-800);
  border: 1px solid var(--color-warning);
  border-radius: var(--radius-xl);
  padding: var(--space-6) var(--space-8);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  max-width: 520px;
  width: 100%;
  text-align: center;
}
.vm-approval-icon { font-size: 2.5rem; }
.vm-approval-text { font-family: var(--font-sans); font-size: 0.9rem; color: var(--color-warning); font-weight: 500; }
.vm-approval-cmd {
  font-family: var(--font-mono);
  font-size: 0.88rem;
  color: var(--color-gold-400);
  background: rgba(255,255,255,0.06);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-md);
  width: 100%;
  word-break: break-all;
}
.vm-approval-actions { display: flex; gap: var(--space-3); margin-top: var(--space-2); }


/* ════════════════════════════════════════════════════════════════
   弹窗样式
   ════════════════════════════════════════════════════════════════ */

.vm-form { margin-top: var(--space-2); }
.vm-form-tip { font-size: 0.75rem; color: var(--color-slate-400); margin-top: 4px; line-height: 1.4; }

/* 日志弹窗 — xterm.js 渲染 */
.log-bar { display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-3); padding: var(--space-2) var(--space-3); background: var(--color-slate-50); border: 1px solid var(--color-slate-200); border-radius: var(--radius-md); font-size: 0.82rem; }
.log-bar-label { font-weight: 600; color: var(--color-navy-700); font-family: var(--font-mono); }
.log-bar-total { margin-left: auto; color: var(--color-slate-400); font-size: 0.78rem; }

.log-terminal {
  position: relative;
  background: var(--color-navy-900);
  border: 1px solid var(--color-navy-700);
  border-radius: var(--radius-lg);
  height: 480px;
  overflow: hidden;
}
.log-xterm {
  height: 100%;
  padding: var(--space-1) 0;
}
.log-xterm :deep(.xterm) {
  height: 100%;
  padding: 0 var(--space-2);
}
.log-status {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-10);
  color: var(--color-slate-500);
  pointer-events: none;
}
.log-status--empty p { margin: 0; font-size: 0.9rem; }
.log-status--empty .log-status-sub { font-size: 0.78rem; color: var(--color-slate-600); margin-top: var(--space-1); }

.log-footer { display: flex; justify-content: space-between; align-items: center; width: 100%; }
.log-footer-connect { display: flex; align-items: center; gap: 6px; font-size: 0.78rem; }
.log-footer-dot { width: 8px; height: 8px; border-radius: 50%; }
.log-footer-connect--on { color: var(--color-success); }
.log-footer-connect--on .log-footer-dot { background: var(--color-success); box-shadow: 0 0 6px rgba(16,185,129,0.5); }
.log-footer-connect--off { color: var(--color-slate-400); }
.log-footer-connect--off .log-footer-dot { background: var(--color-slate-400); }

/* ── 响应式 ── */
@media (max-width: 1180px) { .vm-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 768px) {
  .vm-grid { grid-template-columns: 1fr; }
  .vm-header { flex-direction: column; align-items: stretch; }
  .vm-header-stats { justify-content: center; }
  .vm-header-actions { justify-content: center; }
}
</style>
