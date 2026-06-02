<template>
  <article
    class="message"
    :class="[message.role, { streaming: isStreaming }]"
    ref="msgRef"
  >
    <div class="message-meta">
      <span class="role-badge">{{ message.roleLabel }}</span>
      <span class="time">{{ message.time }}</span>
      <el-tag
        v-if="message.status === 0"
        size="small"
        type="warning"
        effect="light"
      >已中断</el-tag>
    </div>
    <div class="message-content">
      <template v-for="block in message.blocks" :key="block.id">
        <!-- 可折叠块：思考、工具调用、工具结果、错误 -->
        <details v-if="isCollapsible(block.kind)" class="block block--collapsible" :open="block.expanded">
          <summary class="block-summary">
            <span class="block-summary-title">{{ block.title }}</span>
            <span class="block-summary-kind">{{ block.kind }}</span>
          </summary>
          <div class="block-body">
            <div class="md" v-html="renderMarkdown(block.content)"></div>
            <button
              v-if="block.kind === 'error'"
              class="retry-btn"
              @click.stop="$emit('retry')"
            >
              ↻ 重试
            </button>
          </div>
        </details>

        <!-- 文本块 → 完整 markdown 渲染 -->
        <div v-else class="block block--text">
          <div class="md" v-html="renderMarkdown(block.content)"></div>
        </div>
      </template>

      <!-- 流式光标 -->
      <span v-if="isStreaming" class="streaming-cursor">▍</span>
    </div>
  </article>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import type { ChatMessage } from '../types'
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
  ['reasoning', 'tool_use', 'tool_result', 'error'].includes(kind)

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
.message {
  max-width: 940px;
  width: 100%;
  padding: 20px;
  border-radius: 20px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.04);
  animation: msg-fade-in 0.3s ease;
}
.message.user {
  align-self: flex-end;
  background: #eff6ff;
  border-color: #bfdbfe;
}
.message.assistant {
  align-self: flex-start;
}

.message-meta {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 10px;
}
.role-badge {
  padding: 4px 10px;
  border-radius: 999px;
  background: #e0e7ff;
  color: #3730a3;
  font-size: 0.82rem;
  font-weight: 600;
}
.user .role-badge {
  background: #dbeafe;
  color: #1d4ed8;
}
.time {
  color: #6b7280;
  font-size: 0.85rem;
}

.message-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ── 块容器 ── */
.block {
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  overflow: hidden;
  background: #ffffff;
}
.block--collapsible {
  border-color: #e5e7eb;
}
.block--text {
  border: none;
  background: transparent;
  padding: 0;
}

.block-summary {
  cursor: pointer;
  list-style: none;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  font-weight: 600;
  color: #111827;
  background: #f8fafc;
  user-select: none;
}
.block-summary::-webkit-details-marker {
  display: none;
}
.block-summary-title {
  font-size: 0.9rem;
}
.block-summary-kind {
  font-size: 0.75rem;
  color: #6b7280;
  background: #e5e7eb;
  padding: 2px 8px;
  border-radius: 999px;
}

.block-body {
  padding: 14px;
  border-top: 1px solid #e5e7eb;
}

/* ── 重试按钮 ── */
.retry-btn {
  margin-top: 12px;
  padding: 6px 16px;
  font-size: 0.85rem;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #ffffff;
  color: #374151;
  cursor: pointer;
  transition: all 0.15s;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.retry-btn:hover {
  background: #f3f4f6;
  border-color: #2563eb;
  color: #2563eb;
}

/* ── 流式光标 ── */
.streaming-cursor {
  display: inline-block;
  font-size: 1.2rem;
  color: #2563eb;
  animation: cursor-blink 0.9s step-end infinite;
  margin-left: 2px;
  line-height: 1;
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
