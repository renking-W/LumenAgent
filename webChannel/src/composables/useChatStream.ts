/**
 * useChatStream — 聊天流式 SSE 逻辑的响应式封装。
 *
 * 每个调用方（主聊天 / MiniChatPanel）独立拥有 session_id 和消息状态。
 * 提取自 App.vue 的 sendMessage() / consumeEvent() / interruptChat()。
 */

import { computed, nextTick, reactive, ref } from 'vue'
import type { ChatBlock, ChatMessage } from '../types'

/** 后端返回的 content block 格式 */
interface CB {
  type: string; text?: string; thinking?: string
  name?: string; input?: unknown; content?: string
  is_error?: boolean; id?: string; tool_use_id?: string
  image_url?: { url: string }
}

interface StoredMsg {
  seq: number; role: string; content: CB[]
  created_at: string; updated_at: string; status: number
}

interface SendOptions {
  mode?: 'simple' | 'agent'
  mcp_server_ids?: string[]
  approval_mode?: string
  self_system?: string
  session_kind?: number
  image_urls?: string[]
}

export function useChatStream() {
  const messages = reactive<ChatMessage[]>([])
  const sending = ref(false)
  const sessionId = ref('')
  const statusText = ref('等待输入')
  const abortController = ref<AbortController | null>(null)

  const lastUserPrompt = ref('')

  // ── 流式过程中的分组列表 ──
  const pendingTexts = ref<ChatBlock[]>([])
  const pendingThinkings = ref<ChatBlock[]>([])
  const pendingToolUses = ref<ChatBlock[]>([])
  const pendingToolResults = ref<ChatBlock[]>([])
  const pendingErrors = ref<ChatBlock[]>([])

  const clearPendingBlocks = () => {
    pendingTexts.value = []
    pendingThinkings.value = []
    pendingToolUses.value = []
    pendingToolResults.value = []
    pendingErrors.value = []
  }

  const pushPendingBlock = (block: ChatBlock) => {
    switch (block.kind) {
      case 'text': pendingTexts.value.push(block); break
      case 'thinking': pendingThinkings.value.push(block); break
      case 'tool_use': pendingToolUses.value.push(block); break
      case 'tool_result': pendingToolResults.value.push(block); break
      case 'error': pendingErrors.value.push(block); break
    }
  }

  // ── helpers ──
  const pretty = (value: unknown) => JSON.stringify(value, null, 2)
  const nowStamp = () => new Date().toLocaleTimeString('zh-CN', { hour12: false })

  const addMessage = (role: 'user' | 'assistant') => {
    const msg: ChatMessage = {
      id: crypto.randomUUID(),
      role,
      roleLabel: role === 'user' ? 'User' : 'Assistant',
      time: nowStamp(),
      blocks: [],
    }
    messages.push(msg)
    return msg
  }

  const getOrCreateAssistant = () => {
    let msg = messages[messages.length - 1]
    if (!msg || msg.role !== 'assistant') msg = addMessage('assistant')
    return msg
  }

  const pushBlock = (kind: string, title: string, content: string, expanded = true) => {
    const msg = getOrCreateAssistant()
    const block: ChatBlock = { id: crypto.randomUUID(), kind, title, content, expanded }
    msg.blocks.push(block)
    pushPendingBlock(block)
    return block
  }

  const appendBlock = (kind: string, title: string, content: string, expanded = true) => {
    const msg = getOrCreateAssistant()
    const existing = msg.blocks[msg.blocks.length - 1]
    if (existing && existing.kind === kind) {
      existing.content += content
      return existing
    }
    const block: ChatBlock = { id: crypto.randomUUID(), kind, title, content, expanded }
    msg.blocks.push(block)
    pushPendingBlock(block)
    return block
  }

  const streamingMessageId = computed(() => {
    if (!sending.value || messages.length === 0) return ''
    const last = messages[messages.length - 1]
    return last.role === 'assistant' ? last.id : ''
  })

  // ── 事件消费 ──
  const consumeEvent = (event: { type: string; data?: any }) => {
    switch (event.type) {
      case 'text':
        appendBlock('text', '正文', event.data?.delta ?? '')
        break
      case 'thinking':
        appendBlock('thinking', '💭 思考', event.data?.delta ?? '', false)
        break
      case 'tool_calls':
        // tool_calls 仅用于通知，实际 tool_use 块由 tool_use 事件创建
        break
      case 'awaiting_approval': {
        const toolCalls: Array<{ id: string; name: string; input: unknown }> =
          event.data?.tool_calls ?? []
        if (toolCalls.length > 0) {
          const payload = toolCalls.map(tc => ({ ...tc, _resolved: undefined as boolean | undefined }))
          pushBlock('awaiting_approval', `🔒 等待审批`, JSON.stringify(payload), true)
          statusText.value = `等待审批: ${toolCalls.map(t => t.name).join(', ')}`
        }
        break
      }
      case 'tool_use': {
        const data = event.data ?? {}
        const toolCallId: string = data.tool_call_id ?? ''
        const toolName: string = data.name ?? '工具'
        const args: Record<string, unknown> = data.arguments ?? {}
        const toolCall = { id: toolCallId, name: toolName, input: args }
        pushBlock('tool_use', `⏳ ${toolName}`, pretty(toolCall), false)
        break
      }
      case 'tool_result': {
        // 清除上一个 tool_use 块的 ⏳ 标记
        const lastMsg = messages[messages.length - 1]
        if (lastMsg && lastMsg.role === 'assistant') {
          for (let bi = lastMsg.blocks.length - 1; bi >= 0; bi--) {
            const block = lastMsg.blocks[bi]
            if (block.kind === 'tool_use') {
              block.title = block.title.replace(/^⏳\s*/, '')
              break
            }
          }
        }
        const d = event.data ?? {}
        pushBlock('tool_result', `工具结果: ${d.name ?? '工具'}`, d.result_preview ?? '', false)
        break
      }
      case 'assistant_done':
        statusText.value = '本轮完成'
        break
      case 'error':
        appendBlock('error', '错误', event.data?.message ?? '未知错误')
        break
    }
  }

  // ── 中断 ──
  const interrupt = async () => {
    if (!sessionId.value) return

    // 没有活跃流（stream 已正常完成）→ 无需保存 partial 内容，只清理状态
    if (!abortController.value) {
      sending.value = false
      abortController.value = null
      clearPendingBlocks()
      statusText.value = '已中断'
      return
    }

    abortController.value.abort()

    try {
      await fetch('/v1/chat/stream/interrupt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId.value }),
      })
    } catch { /* ignore */ }

    // 保存已收到的部分 assistant 消息
    const lastMsg = messages[messages.length - 1]
    if (lastMsg && lastMsg.role === 'assistant') {
      const contentBlocks: Record<string, unknown>[] = []
      const pendingToolUseIds = new Set<string>()

      for (const block of lastMsg.blocks) {
        switch (block.kind) {
          case 'text':
            contentBlocks.push({ type: 'text', text: block.content })
            break
          case 'thinking':
            contentBlocks.push({ type: 'thinking', thinking: block.content })
            break
          case 'tool_use': {
            try {
              const parsed = JSON.parse(block.content)
              if (Array.isArray(parsed)) {
                for (const tc of parsed) {
                  contentBlocks.push({ type: 'tool_use', id: tc.id, name: tc.name, input: tc.input || tc.arguments || {} })
                  pendingToolUseIds.add(tc.id)
                }
              } else if (parsed && typeof parsed === 'object' && parsed.id) {
                contentBlocks.push({ type: 'tool_use', id: parsed.id, name: parsed.name || 'tool', input: parsed.input || {} })
                pendingToolUseIds.add(parsed.id)
              }
            } catch {
              contentBlocks.push({ type: 'tool_use', text: block.content })
            }
            break
          }
          case 'tool_result': {
            try {
              const data = JSON.parse(block.content)
              const tid = data.tool_call_id || ''
              contentBlocks.push({ type: 'tool_result', tool_use_id: tid, content: data.result_preview || block.content })
              pendingToolUseIds.delete(tid)
            } catch {
              contentBlocks.push({ type: 'tool_result', content: block.content })
            }
            break
          }
          case 'error':
            contentBlocks.push({ type: 'text', text: block.content, is_error: true })
            break
        }
      }

      for (const tid of pendingToolUseIds) {
        contentBlocks.push({ type: 'tool_result', tool_use_id: tid, content: '(interrupted)' })
      }

      try {
        await fetch(`/v1/sessions/${sessionId.value}/messages`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ role: 'assistant', content: contentBlocks, status: 0 }),
        })
      } catch { /* ignore */ }
    }

    sending.value = false
    abortController.value = null
    clearPendingBlocks()
    statusText.value = '已中断'
  }

  // ── 审批 ──
  const approve = async (blockId: string, toolCallId: string, approved: boolean) => {
    if (!sessionId.value) return
    for (const msg of messages) {
      const block = msg.blocks.find(b => b.id === blockId)
      if (!block || block.kind !== 'awaiting_approval') continue
      try {
        const toolCalls: Array<{ id: string; name: string; input: unknown; _resolved?: boolean }> =
          JSON.parse(block.content)
        const target = toolCalls.find(tc => tc.id === toolCallId)
        if (!target || target._resolved !== undefined) return
        target._resolved = approved
        block.content = JSON.stringify(toolCalls)
        const total = toolCalls.length
        const done = toolCalls.filter(tc => tc._resolved !== undefined).length
        block.title = done < total ? `🔒 等待审批 (${done}/${total})` : approved ? '✅ 已放行' : '❌ 已拒绝'
      } catch { /* ignore */ }
      break
    }
    try {
      await fetch('/v1/chat/stream/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId.value, approvals: { [toolCallId]: approved } }),
      })
    } catch { /* ignore */ }
  }

  // ── 发送消息 ──
  const send = async (text: string, options?: SendOptions) => {
    const content = text.trim()
    if (!content || sending.value) return
    lastUserPrompt.value = content
    sending.value = true
    abortController.value = new AbortController()
    statusText.value = '发送中...'

    addMessage('user').blocks.push({
      id: crypto.randomUUID(), kind: 'text', title: '用户输入', content, expanded: true,
    })

    try {
      const res = await fetch('/v1/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: content,
          session_id: sessionId.value || undefined,
          mode: options?.mode || 'agent',
          approval_mode: options?.approval_mode,
          mcp_server_ids: options?.mcp_server_ids,
          self_system: options?.self_system,
          session_kind: options?.session_kind,
          image_urls: options?.image_urls?.length ? options.image_urls : undefined,
        }),
        signal: abortController.value.signal,
      })
      if (!res.ok || !res.body) throw new Error(await res.text())

      const sid = res.headers.get('x-session-id')
      if (sid) sessionId.value = sid

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() ?? ''
        for (const part of parts) {
          const line = part.split('\n').find(l => l.startsWith('data: '))
          if (!line) continue
          const raw = line.slice(6)
          if (raw === '[DONE]') continue
          consumeEvent(JSON.parse(raw))
        }
      }
      statusText.value = '响应完成'
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        statusText.value = '已中断'
      } else {
        statusText.value = '请求失败'
        appendBlock('error', '请求失败', error instanceof Error ? error.message : String(error))
      }
    } finally {
      sending.value = false
      abortController.value = null
      clearPendingBlocks()
    }
  }

  // ── 重置 ──
  const reset = async () => {
    await interrupt()
    messages.splice(0)
    sessionId.value = ''
    statusText.value = '已重置为新会话'
  }

  // ── 加载历史消息 ──
  const loadSession = async (sid: string) => {
    await interrupt()
    try {
      const res = await fetch(`/v1/sessions/${sid}/messages?limit=20`)
      if (!res.ok) return
      const stored: StoredMsg[] = await res.json()
      sessionId.value = sid
      const isScheduled = sid.startsWith('__scheduled__')
      const filtered = isScheduled ? stored.filter(s => s.seq !== 0) : stored
      const parsed = filtered.map(sm => {
        const pad = (n: number) => String(n).padStart(2, '0')
        const d = new Date(sm.created_at)
        return {
          id: crypto.randomUUID(),
          role: sm.role as 'user' | 'assistant',
          roleLabel: sm.role === 'user' ? 'User' : 'Assistant',
          time: `${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`,
          blocks: sm.content.map((cb: CB): ChatBlock => {
            if (cb.type === 'thinking') return { id: crypto.randomUUID(), kind: 'thinking', title: '💭 思考', content: cb.thinking ?? '', expanded: false }
            if (cb.type === 'tool_use') return { id: crypto.randomUUID(), kind: 'tool_use', title: cb.name || '工具调用', content: pretty(cb.input ?? ''), expanded: false }
            if (cb.type === 'tool_result') return { id: crypto.randomUUID(), kind: 'tool_result', title: `工具结果${cb.name ? ': ' + cb.name : ''}`, content: cb.content ?? pretty(cb.input ?? ''), expanded: false }
            if (cb.type === 'image_url') return { id: crypto.randomUUID(), kind: 'image', title: '图片', content: cb.image_url?.url ?? '', expanded: true }
            return { id: crypto.randomUUID(), kind: 'text', title: '正文', content: cb.text ?? '', expanded: false }
          }),
          seq: sm.seq,
        }
      })
      messages.splice(0, messages.length, ...parsed)
      statusText.value = `已加载会话 (${parsed.length} 条消息)`
    } catch {
      statusText.value = '加载会话失败'
    }
  }

  /** 允许外部显式设置 session_id（如 MiniChatPanel 复用 VM 会话） */
  const setSessionId = (sid: string) => {
    sessionId.value = sid
  }

  return {
    messages,
    sending,
    sessionId,
    statusText,
    streamingMessageId,
    lastUserPrompt,
    send,
    interrupt,
    approve,
    reset,
    loadSession,
    setSessionId,
    clearPendingBlocks,
  }
}
