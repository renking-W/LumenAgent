<template>
  <div class="chat-layout">
    <SessionList
      ref="sessionListRef"
      :active-session-id="activeSessionId"
      @select-session="handleSelectSession"
      @delete-session="(id) => emit('delete-session', id)"
      @new-session="emit('new-session')"
    />
    <div class="chat-pane" ref="chatPaneRef" @scroll="onChatPaneScroll">
      <!-- 顶部加载更多指示器 -->
      <div v-if="messages.length > 0" class="scroll-top-indicator">
        <span v-if="loadingMore" class="loading-more">加载中...</span>
        <span v-else-if="!hasMore" class="no-more">已加载全部消息</span>
      </div>

      <!-- 空状态 -->
      <div v-if="messages.length === 0" class="empty-state">
        <div class="empty-state-graphic">
          <div class="empty-state-ring"></div>
          <span class="empty-state-icon">💬</span>
        </div>
        <h2>开始新的对话</h2>
        <p class="empty-state-desc">在下方输入你的问题，AI 将实时流式回复</p>
        <div class="empty-state-suggestions">
          <button class="suggestion-chip" @click="$emit('new-session')">📝 开始新会话</button>
          <button class="suggestion-chip" @click="$emit('scroll-to-bottom')">👇 查看底部输入区</button>
        </div>
      </div>

      <!-- 消息列表 -->
      <ChatMessage
        v-for="(msg, idx) in messages"
        :key="msg.id"
        :message="msg"
        :is-streaming="streamingMessageId === msg.id"
        @retry="emit('retry')"
      />
    </div>

    <!-- 滚动到底部按钮 -->
    <transition name="fade">
      <button
        v-if="!isNearBottom && messages.length > 0"
        class="scroll-bottom-btn"
        @click="scrollToBottom"
        title="滚动到底部"
      >
        ↓
      </button>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { ChatMessage as ChatMessageType } from '../types'
import ChatMessage from './ChatMessage.vue'
import SessionList from './SessionList.vue'

const props = defineProps<{
  messages: ChatMessageType[]
  activeSessionId: string
  streamingMessageId: string
  isNearBottom: boolean
  loadingMore: boolean
  hasMore: boolean
}>()

const emit = defineEmits<{
  'select-session': [sessionId: string]
  'scroll-to-bottom': []
  'delete-session': [sessionId: string]
  'new-session': []
  'load-more': []
  retry: []
}>()

const SCROLL_TOP_THRESHOLD = 80
let savedScrollHeight = 0

const sessionListRef = ref<InstanceType<typeof SessionList> | null>(null)
const chatPaneRef = ref<HTMLElement | null>(null)

const handleSelectSession = (id: string) => {
  emit('select-session', id)
}

const scrollToBottom = () => {
  if (chatPaneRef.value) {
    chatPaneRef.value.scrollTop = chatPaneRef.value.scrollHeight
  }
  emit('scroll-to-bottom')
}

const scrollPaneToBottom = () => {
  if (chatPaneRef.value) {
    chatPaneRef.value.scrollTop = chatPaneRef.value.scrollHeight
  }
}

const onChatPaneScroll = () => {
  const el = chatPaneRef.value
  if (!el || props.loadingMore || !props.hasMore) return
  if (el.scrollTop < SCROLL_TOP_THRESHOLD) {
    savedScrollHeight = el.scrollHeight
    emit('load-more')
  }
}

/** 预加载消息后保持滚动位置（在父组件 prepend 消息 + nextTick 后调用） */
const restoreScrollAfterPrepend = () => {
  const el = chatPaneRef.value
  if (!el || !savedScrollHeight) return
  el.scrollTop = el.scrollHeight - savedScrollHeight
  savedScrollHeight = 0
}

const refreshSessions = () => {
  sessionListRef.value?.fetchSessions()
}

defineExpose({ refreshSessions, scrollPaneToBottom, restoreScrollAfterPrepend })
</script>

<style scoped>
.chat-layout {
  display: flex;
  flex-direction: row;
  height: 100%;
  min-height: 100%;
  position: relative;
}

.scroll-top-indicator {
  text-align: center;
  padding: var(--space-2) 0;
  font-size: 0.82rem;
  color: var(--color-slate-400);
  flex-shrink: 0;
}
.loading-more {
  display: inline-block;
  animation: pulse-dot 1.2s ease-in-out infinite;
}
.no-more {
  color: var(--color-slate-300);
}
@keyframes pulse-dot {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

.chat-pane {
  flex: 1;
  padding: var(--space-5) var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-height: 100%;
  min-width: 0;
  background: var(--color-slate-50);
  overflow-y: auto;
}

/* ── 空状态 ── */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--color-slate-400);
  user-select: none;
  gap: var(--space-3);
  padding: var(--space-10);
  border: 2px dashed var(--color-slate-200);
  border-radius: var(--radius-2xl);
  background: var(--color-white);
  margin: var(--space-8) 0;
}
.empty-state-graphic {
  position: relative;
  width: 72px;
  height: 72px;
  display: grid;
  place-items: center;
  margin-bottom: var(--space-2);
}
.empty-state-ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 2px solid var(--color-slate-200);
  animation: empty-ring-pulse 3s ease-in-out infinite;
}
.empty-state-icon {
  font-size: 2rem;
  z-index: 1;
}
@keyframes empty-ring-pulse {
  0%, 100% { transform: scale(1); opacity: 0.5; }
  50% { transform: scale(1.08); opacity: 0.8; }
}
.empty-state h2 {
  margin: 0;
  color: var(--color-navy-700);
  font-weight: 600;
  font-size: 1.2rem;
}
.empty-state-desc {
  margin: 0;
  font-size: 0.88rem;
  color: var(--color-slate-400);
}
.empty-state-suggestions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-2);
}
.suggestion-chip {
  padding: 6px 16px;
  border: 1px solid var(--color-slate-200);
  border-radius: var(--radius-full);
  background: var(--color-slate-50);
  color: var(--color-slate-500);
  font-size: 0.82rem;
  cursor: pointer;
  transition: all var(--transition-fast);
}
.suggestion-chip:hover {
  border-color: var(--color-gold-300);
  background: var(--color-gold-50);
  color: var(--color-gold-700);
}

/* ── 滚动到底部按钮 ── */
.scroll-bottom-btn {
  position: absolute;
  bottom: var(--space-4);
  right: var(--space-6);
  width: 40px;
  height: 40px;
  border-radius: var(--radius-full);
  border: 1px solid var(--color-slate-200);
  background: var(--color-white);
  color: var(--color-navy-600);
  font-size: 1.2rem;
  cursor: pointer;
  box-shadow: var(--shadow-md);
  display: grid;
  place-items: center;
  transition: all var(--transition-fast);
  z-index: 10;
}
.scroll-bottom-btn:hover {
  background: var(--color-gold-50);
  border-color: var(--color-gold-500);
  color: var(--color-gold-600);
  box-shadow: var(--shadow-glow);
  transform: translateY(-2px);
}

/* ── 过渡动画 ── */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
