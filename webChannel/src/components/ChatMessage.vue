<template>
  <div class="message-row" :class="message.role">
    <img v-if="message.role === 'assistant'" class="msg-avatar" src="/logo.svg" alt="AI" />
    <article
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
      <template v-for="item in groupedBlocks" :key="item.id">
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
      </template>

      <!-- 流式光标 -->
      <span v-if="isStreaming" class="streaming-cursor">▍</span>
    </div>
    <div class="message-footer">
      <span class="time">{{ message.time }}</span>
    </div>
  </article>
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
}>()

const msgRef = ref<HTMLElement | null>(null)

const isCollapsible = (kind: string) =>
  ['thinking', 'error'].includes(kind)

// ── 合并 tool_use + tool_result 分组 ─────────────────
interface ToolRenderItem {
  kind: 'tool'
  id: string
  toolName: string
  useContent: string
  resultContents: string[]
}
interface SingleRenderItem {
  kind: 'single'
  id: string
  block: ChatBlock
}
type RenderItem = ToolRenderItem | SingleRenderItem

const groupedBlocks = computed<RenderItem[]>(() => {
  const items: RenderItem[] = []
  const blocks = props.message.blocks
  let i = 0
  while (i < blocks.length) {
    const block = blocks[i]
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

.message {
  flex: 1;
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
</style>
