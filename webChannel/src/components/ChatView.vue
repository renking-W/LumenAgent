<template>
  <div class="chat-layout">
    <SessionList
      ref="sessionListRef"
      :active-session-id="activeSessionId"
      @select-session="handleSelectSession"
      @delete-session="(id) => emit('delete-session', id)"
    />
    <div class="chat-pane" ref="chatPaneRef">
      <!-- 空状态 -->
      <div v-if="messages.length === 0" class="empty-state">
        <div class="empty-icon">💬</div>
        <h2>开始新的对话</h2>
        <p>在下方输入你的问题，AI 将实时流式回复</p>
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
}>()

const emit = defineEmits<{
  'select-session': [sessionId: string]
  'scroll-to-bottom': []
  'delete-session': [sessionId: string]
  retry: []
}>()

const sessionListRef = ref<InstanceType<typeof SessionList> | null>(null)
const chatPaneRef = ref<HTMLElement | null>(null)

const handleSelectSession = (id: string) => {
  emit('select-session', id)
}

const scrollToBottom = () => {
  emit('scroll-to-bottom')
}

const refreshSessions = () => {
  sessionListRef.value?.fetchSessions()
}

defineExpose({ refreshSessions })
</script>

<style scoped>
.chat-layout {
  display: flex;
  flex-direction: row;
  height: 100%;
  min-height: 100%;
  position: relative;
}

.chat-pane {
  flex: 1;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100%;
  min-width: 0;
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
  overflow-y: auto;
}

/* ── 空状态 ── */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #9ca3af;
  user-select: none;
  gap: 8px;
}
.empty-icon {
  font-size: 3rem;
  margin-bottom: 8px;
}
.empty-state h2 {
  margin: 0;
  color: #6b7280;
  font-weight: 600;
  font-size: 1.2rem;
}
.empty-state p {
  margin: 0;
  font-size: 0.9rem;
  color: #9ca3af;
}

/* ── 滚动到底部按钮 ── */
.scroll-bottom-btn {
  position: absolute;
  bottom: 16px;
  right: 24px;
  width: 40px;
  height: 40px;
  border-radius: 999px;
  border: 1px solid #d1d5db;
  background: #ffffff;
  color: #374151;
  font-size: 1.2rem;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  display: grid;
  place-items: center;
  transition: all 0.2s;
  z-index: 10;
}
.scroll-bottom-btn:hover {
  background: #f3f4f6;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.15);
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
