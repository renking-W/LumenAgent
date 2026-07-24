<template>
  <!-- 图片灯箱 -->
  <teleport to="body">
    <div v-if="lightboxUrl" class="lightbox" @click.self="lightboxUrl = ''" @keydown.esc="lightboxUrl = ''" tabindex="-1">
      <button class="lightbox-close" @click="lightboxUrl = ''">×</button>
      <img :src="lightboxUrl" class="lightbox-img" alt="图片预览" />
    </div>
  </teleport>

  <div class="message-row" :class="message.role">
    <img v-if="message.role === 'assistant'" class="msg-avatar" src="/logo.svg" alt="AI" />
    <div class="message-stack">
      <article
        v-if="hasBubbleContent"
        class="message"
        :class="{ streaming: isStreaming }"
        ref="msgRef"
      >
      <div class="message-meta">
        <span class="role-badge">{{ message.roleLabel }}</span>
        <el-tag
          v-if="message.status === 0"
          size="small"
          type="warning"
          effect="light"
        >已中断</el-tag>
      </div>
      <div class="message-content">
      <template v-for="item in bubbleGroupedBlocks" :key="item.id">
        <!-- 可折叠块：思考、错误 -->
        <details v-if="item.kind === 'single' && isCollapsible(item.block.kind)" class="block block--collapsible" :open="item.block.expanded">
          <summary class="block-summary">
            <span class="block-summary-title">{{ item.block.title }}</span>
            <span class="block-summary-kind">{{ item.block.kind }}</span>
          </summary>
          <div class="block-body">
            <div class="md" v-html="renderMarkdown(item.block.content)"></div>
            <button
              v-if="item.block.kind === 'error'"
              class="retry-btn"
              @click.stop="$emit('retry')"
            >
              ↻ 重试
            </button>
          </div>
        </details>

        <!-- 图片块 -->
        <div v-else-if="item.kind === 'single' && item.block.kind === 'image'" class="block block--image">
          <img
            :src="item.block.content"
            class="msg-image"
            alt="图片"
            @click="openImagePreview(item.block.content)"
          />
        </div>

        <!-- 文件附件卡片 -->
        <div v-else-if="item.kind === 'single' && item.block.kind === 'file'" class="block block--file">
          <div class="file-extension">{{ fileExtensionLabel(item.block) }}</div>
          <div class="file-info">
            <a
              v-if="item.block.fileUrl"
              class="file-name file-name--link"
              :href="item.block.fileUrl"
              target="_blank"
              rel="noopener noreferrer"
            >{{ item.block.fileName || '未命名文件' }}</a>
            <span v-else class="file-name">{{ item.block.fileName || '未命名文件' }}</span>
            <span class="file-meta">
              {{ fileExtensionLabel(item.block) }} · {{ formatFileSize(item.block.fileSize) }}
            </span>
          </div>
        </div>

        <!-- 文本块 → 用户消息纯文本，AI 消息 markdown 渲染 -->
        <div v-else-if="item.kind === 'single'" class="block block--text">
          <div v-if="message.role === 'user'" class="plain-text">{{ item.block.content }}</div>
          <div v-else class="md" v-html="renderMarkdown(item.block.content)"></div>
        </div>

        <!-- Tool 分组：tool_use + tool_result 合并展示 -->
        <details v-else-if="item.kind === 'tool'" class="block block--collapsible">
          <summary class="block-summary">
            <span class="block-summary-title">🛠 {{ item.toolName }}</span>
            <span class="block-summary-kind">{{ item.toolName }}</span>
          </summary>
          <div class="block-body">
            <div class="tool-detail">
              <div class="tool-detail-label">工具名称</div>
              <pre class="tool-detail-pre"><code>{{ item.toolName }}</code></pre>
            </div>
            <div class="tool-detail">
              <div class="tool-detail-label">调用参数</div>
              <pre class="tool-detail-pre">{{ item.useContent }}</pre>
            </div>
            <template v-for="(rc, ri) in item.resultContents" :key="ri">
              <div class="tool-detail">
                <div class="tool-detail-label">调用结果{{ item.resultContents.length > 1 ? ' #' + (ri + 1) : '' }}</div>
                <pre class="tool-detail-pre"><code>{{ rc }}</code></pre>
              </div>
            </template>
          </div>
        </details>

        <!-- 审批等待卡片（待审批 / 已全部完成） -->
        <div v-else-if="item.kind === 'approval'" class="approval-container">
          <!-- ── 待审批：完整卡片 ── -->
          <div v-if="!item.allResolved" class="block block--approval">
            <div class="approval-header">
              <span class="approval-header-icon">🔒</span>
              <span class="approval-header-title">等待审批</span>
              <span class="approval-header-count">{{ item.toolCalls.length }} 个工具</span>
            </div>
            <div
              v-for="tc in item.toolCalls"
              :key="tc.id"
              class="approval-tool-card"
              :class="{
                'approval-tool-card--approved': tc._resolved === true,
                'approval-tool-card--rejected': tc._resolved === false,
              }"
            >
              <div class="approval-tool-header">
                <span class="approval-tool-name">🛠 {{ tc.name }}</span>
                <el-tag
                  v-if="tc._resolved === true"
                  size="small"
                  type="success"
                  effect="light"
                >✅ 已放行</el-tag>
                <el-tag
                  v-else-if="tc._resolved === false"
                  size="small"
                  type="danger"
                  effect="light"
                >❌ 已拒绝</el-tag>
              </div>
              <pre class="approval-tool-params">{{ pretty(tc.input) }}</pre>
              <div v-if="tc._resolved === undefined" class="approval-tool-actions">
                <el-button size="small" type="primary" plain @click="emit('approve-tool', item.id, tc.id)">
                  ✅ 放行
                </el-button>
                <el-button size="small" plain @click="emit('reject-tool', item.id, tc.id)">
                  ❌ 拒绝
                </el-button>
              </div>
            </div>
          </div>
          <!-- ── 已全部审批：可折叠摘要 ── -->
          <details v-else class="block block--collapsible approval-resolved" :open="false">
            <summary class="block-summary">
              <span class="block-summary-title">{{ item.summaryLabel }}</span>
              <span class="block-summary-kind">{{ item.toolCalls.length }} 个</span>
            </summary>
            <div class="block-body">
              <div v-for="tc in item.toolCalls" :key="tc.id" class="approval-tool-card approval-tool-card--compact">
                <div class="approval-tool-header">
                  <span class="approval-tool-name">🛠 {{ tc.name }}</span>
                  <el-tag
                    :type="tc._resolved ? 'success' : 'danger'"
                    size="small"
                    effect="light"
                  >{{ tc._resolved ? '已放行' : '已拒绝' }}</el-tag>
                </div>
                <pre class="approval-tool-params">{{ pretty(tc.input) }}</pre>
              </div>
            </div>
          </details>
        </div>
      </template>

      <!-- 流式光标 -->
      <span v-if="isStreaming" class="streaming-cursor">▍</span>
    </div>
        <div v-if="message.role === 'assistant'" class="message-footer">
          <span class="time">{{ message.time }}</span>
        </div>
      </article>

      <!-- 用户附件独立展示，不放入聊天气泡 -->
      <div v-if="userAttachmentBlocks.length" class="user-attachments">
        <div
          v-for="block in userAttachmentBlocks"
          :key="block.id"
          class="user-attachment-item"
        >
          <div v-if="block.kind === 'image'" class="block block--image">
            <img
              :src="block.content"
              class="msg-image"
              alt="图片"
              @click="openImagePreview(block.content)"
            />
          </div>
          <div v-else class="block block--file">
            <div class="file-extension">{{ fileExtensionLabel(block) }}</div>
            <div class="file-info">
              <a
                v-if="block.fileUrl"
                class="file-name file-name--link"
                :href="block.fileUrl"
                target="_blank"
                rel="noopener noreferrer"
              >{{ block.fileName || '未命名文件' }}</a>
              <span v-else class="file-name">{{ block.fileName || '未命名文件' }}</span>
              <span class="file-meta">
                {{ fileExtensionLabel(block) }} · {{ formatFileSize(block.fileSize) }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="message.role === 'user'" class="message-footer message-footer--outside">
        <span class="time">{{ message.time }}</span>
      </div>
    </div>
  <img v-if="message.role === 'user'" class="msg-avatar" src="/user.svg" alt="User" />
</div>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import type { ChatMessage, ChatBlock } from '../types'
import { renderMarkdown } from '../utils/markdown'

const props = defineProps<{
  message: ChatMessage
  isStreaming: boolean
}>()

const emit = defineEmits<{
  retry: []
  'approve-tool': [blockId: string, toolId: string]
  'reject-tool': [blockId: string, toolId: string]
}>()

const msgRef = ref<HTMLElement | null>(null)

const pretty = (value: unknown) => JSON.stringify(value, null, 2)

const isCollapsible = (kind: string) =>
  ['thinking', 'error'].includes(kind)

const lightboxUrl = ref('')
const openImagePreview = (url: string) => {
  lightboxUrl.value = url
}

const fileExtensionLabel = (block: ChatBlock) => {
  const extension = block.fileExtension?.replace(/^\./, '').trim()
  return extension ? extension.toUpperCase() : 'FILE'
}

const formatFileSize = (size = 0) => {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

// ── 合并 tool_use + tool_result + awaiting_approval 分组 ──
interface ToolRenderItem {
  kind: 'tool'
  id: string
  toolName: string
  useContent: string
  resultContents: string[]
}
interface ApprovalRenderItem {
  kind: 'approval'
  id: string
  toolCalls: Array<{ id: string; name: string; input: unknown; _resolved?: boolean }>
  allResolved: boolean
  allApproved: boolean
  summaryLabel: string
}
interface SingleRenderItem {
  kind: 'single'
  id: string
  block: ChatBlock
}
type RenderItem = ToolRenderItem | ApprovalRenderItem | SingleRenderItem

const groupedBlocks = computed<RenderItem[]>(() => {
  const items: RenderItem[] = []
  const blocks = props.message.blocks
  let i = 0
  while (i < blocks.length) {
    const block = blocks[i]
    if (block.kind === 'awaiting_approval') {
      // 解析工具调用列表
      let toolCalls: Array<{ id: string; name: string; input: unknown; _resolved?: boolean }> = []
      try { toolCalls = JSON.parse(block.content) } catch { toolCalls = [] }
      const allResolved = toolCalls.length > 0 && toolCalls.every((tc) => tc._resolved !== undefined)
      const allApproved = allResolved && toolCalls.every((tc) => tc._resolved === true)
      const approvedCount = toolCalls.filter((tc) => tc._resolved === true).length
      const rejectedCount = toolCalls.filter((tc) => tc._resolved === false).length
      let summaryLabel = `🔒 等待审批 (${toolCalls.length})`
      if (allResolved) {
        summaryLabel = allApproved
          ? `✅ 已全部放行`
          : rejectedCount === 0 ? `✅ 已全部放行`
          : approvedCount === 0 ? `❌ 已全部拒绝`
          : `✅ ${approvedCount}放行 / ${rejectedCount}拒绝`
      }
      items.push({ kind: 'approval', id: block.id, toolCalls, allResolved, allApproved, summaryLabel })
      i++
      continue
    }
    if (block.kind === 'tool_use') {
      // 收集后面连续的所有 tool_result
      const resultBlocks: ChatBlock[] = []
      let j = i + 1
      while (j < blocks.length && blocks[j].kind === 'tool_result') {
        resultBlocks.push(blocks[j])
        j++
      }
      items.push({
        kind: 'tool',
        id: block.id,
        toolName: block.title,  // 标题已存工具名（bash/read/write 等）
        useContent: block.content,
        resultContents: resultBlocks.map(b => b.content),
      })
      i = j
      continue
    }
    items.push({ kind: 'single', id: block.id, block })
    i++
  }
  return items
})

const bubbleGroupedBlocks = computed(() => {
  if (props.message.role !== 'user') return groupedBlocks.value
  return groupedBlocks.value.filter(item =>
    !(item.kind === 'single' && ['image', 'file'].includes(item.block.kind))
  )
})

const userAttachmentBlocks = computed(() => {
  if (props.message.role !== 'user') return []
  return props.message.blocks.filter(block => ['image', 'file'].includes(block.kind))
})

const hasBubbleContent = computed(() =>
  props.message.role === 'assistant' ||
  bubbleGroupedBlocks.value.length > 0 ||
  props.isStreaming
)

// ── 复制按钮注入 ─────────────────────────────────────
const injectCopyButtons = () => {
  if (!msgRef.value) return
  msgRef.value.querySelectorAll<HTMLPreElement>('.md pre').forEach((pre) => {
    if (pre.querySelector('.copy-btn')) return
    const btn = document.createElement('button')
    btn.className = 'copy-btn'
    btn.textContent = '复制'
    btn.addEventListener('click', async (e) => {
      e.stopPropagation()
      const code = pre.querySelector('code')?.textContent || pre.textContent || ''
      try {
        await navigator.clipboard.writeText(code)
        btn.textContent = '已复制'
        btn.classList.add('copy-btn--ok')
        setTimeout(() => {
          btn.textContent = '复制'
          btn.classList.remove('copy-btn--ok')
        }, 2000)
      } catch {
        btn.textContent = '复制失败'
      }
    })
    pre.style.position = 'relative'
    pre.appendChild(btn)
  })
}

// 监听 blocks 变化（新增或内容追加）后重新注入复制按钮
watch(
  () => props.message.blocks,
  () => nextTick(injectCopyButtons),
  { deep: true }
)
</script>

<style scoped>
.message-row {
  display: flex;
  gap: var(--space-3);
  align-items: flex-start;
  max-width: 940px;
  width: 65%;
  animation: msg-fade-in 0.3s ease;
}
.message-row.assistant {
  align-self: flex-start;
}
.message-row.user {
  align-self: flex-end;
}

.message-stack {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: var(--space-2);
}
.message-row.user .message-stack {
  align-items: flex-end;
}

.message {
  width: 100%;
  min-width: 0;
  padding: var(--space-5);
  border-radius: var(--radius-xl);
  background: var(--color-white);
  border: 1px solid var(--color-slate-200);
  box-shadow: var(--shadow-sm);
  transition: border-color var(--transition-fast);
}
.message-row.user .message {
  background: linear-gradient(135deg, var(--color-gold-50), #FFFBEB);
  border-color: var(--color-gold-200);
  border-bottom-right-radius: var(--radius-sm);
}
.message-row.assistant .message {
  border-bottom-left-radius: var(--radius-sm);
}
.message.streaming {
  border-color: var(--color-gold-300);
  box-shadow: 0 0 0 1px rgba(234, 179, 8, 0.08), var(--shadow-sm);
}

.msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: var(--space-5);
  padding: 5px;
  object-fit: contain;
  background: var(--color-slate-100);
}
.message-row.user .msg-avatar {
  background: var(--color-gold-100);
}

.message-meta {
  display: flex;
  gap: var(--space-2);
  align-items: center;
  margin-bottom: var(--space-3);
}
.role-badge {
  padding: 2px 10px;
  border-radius: var(--radius-full);
  background: var(--color-indigo-50);
  color: var(--color-indigo-600);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.02em;
}
.message-row.user .role-badge {
  background: var(--color-gold-100);
  color: var(--color-gold-700);
}

.message-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid var(--color-slate-100);
}
.message-row.assistant .message-footer {
  justify-content: flex-start;
}
.message-row.user .message-footer {
  border-top-color: rgba(234, 179, 8, 0.12);
}
.message-footer--outside {
  width: 100%;
  margin-top: 0;
  padding-top: 0;
  border-top: none;
}
.time {
  color: var(--color-slate-400);
  font-size: 0.75rem;
}

.message-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

/* ── 块容器 ── */
.block {
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: var(--color-white);
}
.block--collapsible {
  border-color: var(--color-slate-200);
}
.block--text {
  border: none;
  background: transparent;
  padding: 0;
}
.plain-text {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.65;
  color: var(--color-navy-800);
}

.block-summary {
  cursor: pointer;
  list-style: none;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  font-weight: 600;
  font-size: 0.88rem;
  color: var(--color-navy-700);
  background: var(--color-slate-50);
  user-select: none;
  transition: background var(--transition-fast);
}
.block-summary:hover {
  background: var(--color-slate-100);
}
.block-summary::-webkit-details-marker {
  display: none;
}
.block-summary-title {
  font-size: 0.88rem;
}
.block-summary-kind {
  font-size: 0.72rem;
  color: var(--color-slate-400);
  background: var(--color-slate-200);
  padding: 2px 8px;
  border-radius: var(--radius-full);
}

.block-body {
  padding: var(--space-4);
  border-top: 1px solid var(--color-slate-200);
}

/* ── 重试按钮 ── */
.retry-btn {
  margin-top: var(--space-3);
  padding: 6px 16px;
  font-size: 0.85rem;
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-sm);
  background: var(--color-white);
  color: var(--color-navy-600);
  cursor: pointer;
  transition: all var(--transition-fast);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.retry-btn:hover {
  background: var(--color-gold-50);
  border-color: var(--color-gold-500);
  color: var(--color-gold-600);
}

/* ── 流式光标 ── */
.streaming-cursor {
  display: inline-block;
  font-size: 1.2rem;
  color: var(--color-gold-500);
  animation: cursor-blink 0.9s step-end infinite;
  margin-left: 2px;
  line-height: 1;
}

/* ── Tool 详情 ── */
.tool-detail {
  margin-bottom: var(--space-3);
}
.tool-detail:last-child {
  margin-bottom: 0;
}
.tool-detail-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-slate-400);
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.tool-detail-value {
  font-size: 0.9rem;
  color: var(--color-navy-800);
}
.tool-detail-pre {
  background: var(--color-slate-50);
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  font-size: 0.82rem;
  max-height: 240px;
  overflow: auto;
}

/* ── 动画 ── */
@keyframes msg-fade-in {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
@keyframes cursor-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* ── 审批等待卡片 ── */
.block--approval {
  border: 1px solid var(--color-gold-200);
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: var(--color-gold-50);
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.approval-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--color-gold-200);
}
.approval-header-icon {
  font-size: 1.1rem;
}
.approval-header-title {
  font-weight: 600;
  font-size: 0.9rem;
  color: var(--color-navy-800);
  flex: 1;
}
.approval-header-count {
  font-size: 0.72rem;
  color: var(--color-slate-400);
  background: var(--color-white);
  padding: 2px 8px;
  border-radius: var(--radius-full);
  border: 1px solid var(--color-slate-200);
}
.approval-tool-card {
  background: var(--color-white);
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-lg);
  padding: var(--space-3);
  transition: all var(--transition-fast);
}
.approval-tool-card--approved {
  border-color: var(--color-success);
  background: var(--color-success-bg);
}
.approval-tool-card--rejected {
  border-color: var(--color-error);
  background: var(--color-error-bg);
  opacity: 0.7;
}
.approval-tool-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}
.approval-tool-name {
  font-weight: 600;
  font-size: 0.88rem;
  color: var(--color-navy-800);
  font-family: var(--font-mono);
}
.approval-tool-params {
  margin: 0 0 var(--space-3);
  padding: var(--space-2) var(--space-3);
  background: var(--color-slate-50);
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-md);
  font-family: var(--font-mono);
  font-size: 0.78rem;
  line-height: 1.5;
  max-height: 160px;
  overflow: auto;
  color: var(--color-navy-700);
}
.approval-tool-actions {
  display: flex;
  gap: var(--space-2);
}

/* ── 审批已全部完成：折叠摘要 ── */
.approval-resolved {
  border-color: var(--color-slate-200);
  background: var(--color-white);
}
.approval-resolved .block-summary {
  background: transparent;
  font-weight: 500;
  font-size: 0.82rem;
  padding: var(--space-2) var(--space-3);
}
.approval-resolved .block-summary:hover {
  background: var(--color-slate-50);
}
.approval-resolved .block-body {
  padding: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.approval-tool-card--compact {
  margin: 0;
  padding: var(--space-2) var(--space-3);
}
.approval-tool-card--compact .approval-tool-params {
  margin-bottom: 0;
  max-height: 120px;
  font-size: 0.75rem;
}

/* ── 图片块 ── */
.block--image {
  border: none;
  background: transparent;
  padding: 0;
  display: inline-block;
  max-width: 100%;
}
.msg-image {
  display: block;
  max-width: 200px;
  max-height: 150px;
  width: auto;
  height: auto;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-slate-200);
  box-shadow: var(--shadow-sm);
  cursor: zoom-in;
  transition: box-shadow var(--transition-fast), transform var(--transition-fast);
  object-fit: contain;
}
.msg-image:hover {
  box-shadow: var(--shadow-md);
  transform: scale(1.02);
}

/* ── 文件附件 ── */
.block--file {
  width: min(360px, 100%);
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  border-color: var(--color-slate-200);
  background: var(--color-slate-50);
}
.file-extension {
  width: 48px;
  height: 48px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--color-slate-300);
  border-radius: var(--radius-md);
  background: var(--color-white);
  color: var(--color-navy-700);
  font-size: 0.7rem;
  font-weight: 700;
}
.file-info {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.file-name {
  overflow: hidden;
  color: var(--color-navy-800);
  font-size: 0.88rem;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-name--link {
  text-decoration: none;
}
.file-name--link:hover {
  color: var(--color-indigo-600);
  text-decoration: underline;
}
.file-meta {
  color: var(--color-slate-500);
  font-size: 0.75rem;
}

.user-attachments {
  max-width: 100%;
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--space-2);
}
.user-attachment-item {
  max-width: 100%;
}

/* ── 灯箱 ── */
.lightbox {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(2, 6, 23, 0.85);
  backdrop-filter: blur(6px);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: zoom-out;
  animation: lightbox-in 0.18s ease;
}
@keyframes lightbox-in {
  from { opacity: 0; }
  to   { opacity: 1; }
}
.lightbox-img {
  max-width: 90vw;
  max-height: 90vh;
  object-fit: contain;
  border-radius: var(--radius-xl);
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.6);
  cursor: default;
  animation: lightbox-scale-in 0.18s ease;
}
@keyframes lightbox-scale-in {
  from { transform: scale(0.88); opacity: 0; }
  to   { transform: scale(1);    opacity: 1; }
}
.lightbox-close {
  position: fixed;
  top: 20px;
  right: 24px;
  width: 40px;
  height: 40px;
  border-radius: var(--radius-full);
  border: none;
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  font-size: 1.4rem;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background var(--transition-fast);
  z-index: 10000;
}
.lightbox-close:hover {
  background: rgba(255, 255, 255, 0.22);
}
</style>
