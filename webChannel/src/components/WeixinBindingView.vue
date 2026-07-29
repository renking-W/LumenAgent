<template>
  <section class="weixin-view">
    <header class="weixin-view__intro">
      <div>
        <p class="weixin-view__eyebrow">Personal channel</p>
        <h2>微信接入</h2>
        <p>绑定后，微信消息会进入 LumenAgent 的完整对话链路，并共享记忆、工具和技能能力。</p>
      </div>
      <div class="weixin-view__state" :class="stateClass">
        <span class="weixin-view__state-dot" aria-hidden="true"></span>
        {{ phaseLabel }}
      </div>
    </header>

    <LoadingState
      v-if="loading && !status"
      label="正在读取微信通道"
      detail="检查本地绑定状态与消息循环"
      size="page"
    />

    <div v-else class="weixin-view__workspace">
      <div class="weixin-view__binding">
        <div v-if="showQrCode" class="weixin-view__qr">
          <img v-if="qrCodeDataUrl" :src="qrCodeDataUrl" alt="微信绑定二维码" />
          <div v-else class="weixin-view__qr-loading">
            <LoaderCircle :size="28" aria-hidden="true" />
          </div>
        </div>
        <div v-else class="weixin-view__symbol" :class="{ 'weixin-view__symbol--error': status?.phase === 'error' }">
          <CircleCheckBig v-if="status?.bound" :size="42" aria-hidden="true" />
          <MessageCircleMore v-else :size="42" aria-hidden="true" />
        </div>

        <div class="weixin-view__binding-copy">
          <h3>{{ bindingTitle }}</h3>
          <p>{{ bindingDescription }}</p>
          <p v-if="status?.account_id" class="weixin-view__account">
            微信账号标识 <code>{{ status.account_id }}</code>
          </p>
          <p v-if="status?.last_error" class="weixin-view__error">{{ status.last_error }}</p>
          <div class="weixin-view__actions">
            <el-button
              v-if="!status?.bound && !showQrCode"
              type="primary"
              :loading="actionLoading"
              @click="beginBinding"
            >
              <QrCode :size="16" aria-hidden="true" />
              生成绑定二维码
            </el-button>
            <el-button
              v-if="status?.bound || showQrCode"
              type="danger"
              plain
              :loading="actionLoading"
              @click="unbind"
            >
              <Unlink :size="16" aria-hidden="true" />
              {{ status?.bound ? '解除绑定' : '取消绑定' }}
            </el-button>
          </div>
        </div>
      </div>

      <div class="weixin-view__facts">
        <div>
          <span>运行方式</span>
          <strong>后端常驻托管</strong>
        </div>
        <div>
          <span>Agent 权限</span>
          <strong>工具直接执行</strong>
        </div>
        <div>
          <span>会话标识</span>
          <strong>wechat-personal</strong>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CircleCheckBig, LoaderCircle, MessageCircleMore, QrCode, Unlink } from 'lucide-vue-next'
import QRCode from 'qrcode'
import LoadingState from './LoadingState.vue'

type ChannelPhase = 'unbound' | 'waiting_scan' | 'scanned' | 'bound' | 'running' | 'error'

interface WeixinChannelStatus {
  phase: ChannelPhase
  bound: boolean
  running: boolean
  qrcode_url?: string | null
  account_id?: string | null
  last_error?: string | null
}

const status = ref<WeixinChannelStatus | null>(null)
const loading = ref(true)
const actionLoading = ref(false)
const qrCodeDataUrl = ref('')
let pollingTimer: number | null = null

const showQrCode = computed(() =>
  Boolean(status.value?.qrcode_url)
  && (status.value?.phase === 'waiting_scan' || status.value?.phase === 'scanned'),
)

const phaseLabel = computed(() => {
  const labels: Record<ChannelPhase, string> = {
    unbound: '未绑定',
    waiting_scan: '等待扫码',
    scanned: '已扫码，等待确认',
    bound: '已绑定',
    running: '运行中',
    error: '通道异常',
  }
  return status.value ? labels[status.value.phase] : '读取中'
})

const stateClass = computed(() => ({
  'weixin-view__state--active': status.value?.running,
  'weixin-view__state--waiting': showQrCode.value,
  'weixin-view__state--error': status.value?.phase === 'error',
}))

const bindingTitle = computed(() => {
  if (status.value?.running) return '微信通道正在运行'
  if (status.value?.bound) return '微信账号已绑定'
  if (status.value?.phase === 'scanned') return '请在微信中确认'
  if (status.value?.phase === 'waiting_scan') return '使用微信扫描二维码'
  if (status.value?.phase === 'error') return '微信通道暂时不可用'
  return '尚未绑定微信'
})

const bindingDescription = computed(() => {
  if (status.value?.running) return '后台正在持续接收微信消息，无需手动运行额外命令。'
  if (status.value?.bound) return '登录凭据已保存，消息循环正在准备启动。'
  if (status.value?.phase === 'scanned') return '二维码已经识别，请回到微信完成最后确认。'
  if (status.value?.phase === 'waiting_scan') return '二维码有效期有限，过期后后台会自动刷新。'
  if (status.value?.phase === 'error') return '请查看下方错误信息，修复后可重新发起绑定。'
  return '绑定操作仅对管理员开放，凭据保存在服务器的持久化目录中。'
})

/** 从管理员接口读取当前通道状态，轮询期间不打断页面操作。 */
async function loadStatus(silent = false): Promise<void> {
  if (!silent) loading.value = true
  try {
    const response = await fetch('/v1/admin/weixin/status')
    if (!response.ok) throw new Error(await responseDetail(response, '无法读取微信通道状态'))
    status.value = await response.json() as WeixinChannelStatus
  } catch (error) {
    if (!silent) ElMessage.error(error instanceof Error ? error.message : '无法读取微信通道状态')
  } finally {
    if (!silent) loading.value = false
  }
}

async function responseDetail(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json() as { detail?: string }
    return body.detail || fallback
  } catch {
    return fallback
  }
}

/** 发起扫码绑定，后续状态由轻量轮询持续同步。 */
async function beginBinding(): Promise<void> {
  actionLoading.value = true
  try {
    const response = await fetch('/v1/admin/weixin/binding', { method: 'POST' })
    if (!response.ok) throw new Error(await responseDetail(response, '无法生成微信二维码'))
    status.value = await response.json() as WeixinChannelStatus
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '无法生成微信二维码')
  } finally {
    actionLoading.value = false
  }
}

/** 解除绑定会同时停止消息循环并删除服务器端微信凭据。 */
async function unbind(): Promise<void> {
  try {
    await ElMessageBox.confirm(
      status.value?.bound ? '解除绑定后，微信将无法继续访问 Agent。' : '确认取消本次扫码绑定？',
      status.value?.bound ? '解除微信绑定' : '取消绑定',
      { type: 'warning', confirmButtonText: '确认', cancelButtonText: '返回' },
    )
  } catch {
    return
  }

  actionLoading.value = true
  try {
    const response = await fetch('/v1/admin/weixin/binding', { method: 'DELETE' })
    if (!response.ok) throw new Error(await responseDetail(response, '解除微信绑定失败'))
    status.value = await response.json() as WeixinChannelStatus
    ElMessage.success('微信绑定已解除')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '解除微信绑定失败')
  } finally {
    actionLoading.value = false
  }
}

watch(
  () => status.value?.qrcode_url,
  async value => {
    qrCodeDataUrl.value = value
      ? await QRCode.toDataURL(value, {
          width: 248,
          margin: 1,
          color: { dark: '#17352f', light: '#ffffff' },
        })
      : ''
  },
  { immediate: true },
)

onMounted(async () => {
  await loadStatus()
  pollingTimer = window.setInterval(() => void loadStatus(true), 2000)
})

onUnmounted(() => {
  if (pollingTimer !== null) window.clearInterval(pollingTimer)
})
</script>

<style scoped>
.weixin-view {
  min-height: 100%;
  padding: 42px clamp(24px, 5vw, 72px);
  color: var(--color-navy-900, #17352f);
}

.weixin-view__intro {
  max-width: 980px;
  margin: 0 auto 38px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 32px;
}

.weixin-view__eyebrow {
  margin: 0 0 8px;
  color: #8a6d00;
  font-family: var(--font-mono, monospace);
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
}

.weixin-view__intro h2 {
  margin: 0 0 10px;
  font-size: 1.75rem;
  letter-spacing: 0;
}

.weixin-view__intro p:last-child {
  max-width: 660px;
  margin: 0;
  color: var(--color-slate-500, #64736c);
  line-height: 1.7;
}

.weixin-view__state {
  min-width: 112px;
  display: flex;
  align-items: center;
  gap: 9px;
  color: #61716a;
  font-size: 0.8rem;
  font-weight: 700;
}

.weixin-view__state-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #9aa8a1;
  box-shadow: 0 0 0 4px rgba(154, 168, 161, 0.14);
}

.weixin-view__state--active .weixin-view__state-dot {
  background: #2f855a;
  box-shadow: 0 0 0 4px rgba(47, 133, 90, 0.14);
}

.weixin-view__state--waiting .weixin-view__state-dot {
  background: #d09a18;
  box-shadow: 0 0 0 4px rgba(208, 154, 24, 0.15);
}

.weixin-view__state--error .weixin-view__state-dot {
  background: #c2413a;
  box-shadow: 0 0 0 4px rgba(194, 65, 58, 0.14);
}

.weixin-view__workspace {
  max-width: 980px;
  margin: 0 auto;
  border-top: 1px solid var(--color-slate-200, #dce4df);
  border-bottom: 1px solid var(--color-slate-200, #dce4df);
}

.weixin-view__binding {
  min-height: 360px;
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  align-items: center;
  gap: clamp(32px, 6vw, 72px);
  padding: 40px 0;
}

.weixin-view__qr {
  width: 264px;
  height: 264px;
  display: grid;
  place-items: center;
  border: 1px solid var(--color-slate-200, #dce4df);
  border-radius: 6px;
  background: #ffffff;
}

.weixin-view__qr img {
  width: 248px;
  height: 248px;
  display: block;
}

.weixin-view__qr-loading,
.weixin-view__symbol {
  width: 148px;
  height: 148px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: #2f855a;
  background: #edf7f0;
}

.weixin-view__qr-loading {
  width: 248px;
  height: 248px;
  color: #7a8982;
  background: #f6f8f7;
}

.weixin-view__qr-loading svg {
  animation: weixin-spin 1s linear infinite;
}

.weixin-view__symbol--error {
  color: #c2413a;
  background: #fff1f0;
}

.weixin-view__binding-copy h3 {
  margin: 0 0 10px;
  font-size: 1.22rem;
  letter-spacing: 0;
}

.weixin-view__binding-copy > p {
  max-width: 540px;
  margin: 0 0 18px;
  color: var(--color-slate-500, #64736c);
  line-height: 1.7;
}

.weixin-view__account code {
  margin-left: 6px;
  color: #2f5f50;
  overflow-wrap: anywhere;
}

.weixin-view__binding-copy .weixin-view__error {
  padding-left: 12px;
  border-left: 3px solid #c2413a;
  color: #9f322d;
}

.weixin-view__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.weixin-view__actions :deep(.el-button span) {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.weixin-view__facts {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  border-top: 1px solid var(--color-slate-200, #dce4df);
}

.weixin-view__facts div {
  min-width: 0;
  padding: 22px 20px;
  border-right: 1px solid var(--color-slate-200, #dce4df);
}

.weixin-view__facts div:last-child {
  border-right: 0;
}

.weixin-view__facts span,
.weixin-view__facts strong {
  display: block;
}

.weixin-view__facts span {
  margin-bottom: 7px;
  color: #7a8982;
  font-size: 0.72rem;
}

.weixin-view__facts strong {
  color: #294a40;
  font-size: 0.86rem;
  overflow-wrap: anywhere;
}

@keyframes weixin-spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 760px) {
  .weixin-view { padding: 28px 20px; }
  .weixin-view__intro { flex-direction: column; gap: 16px; }
  .weixin-view__binding {
    grid-template-columns: 1fr;
    justify-items: start;
    gap: 28px;
  }
  .weixin-view__qr { width: min(264px, 100%); }
  .weixin-view__facts { grid-template-columns: 1fr; }
  .weixin-view__facts div { border-right: 0; border-bottom: 1px solid var(--color-slate-200, #dce4df); }
  .weixin-view__facts div:last-child { border-bottom: 0; }
}
</style>
