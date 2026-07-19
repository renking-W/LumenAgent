import { computed, reactive, ref } from "vue"
import type { ChatBlock, ChatMessage } from "../types"

interface ContentBlock {
  type: string
  text?: string
  thinking?: string
  name?: string
  input?: unknown
  content?: string
  id?: string
  tool_use_id?: string
  image_url?: { url: string }
}

interface StoredMessage {
  seq: number
  role: string
  content: ContentBlock[]
  created_at: string
  updated_at: string
  status: number
}

interface SendOptions {
  mode?: "simple" | "agent"
  mcp_server_ids?: string[]
  approval_mode?: string
  self_system?: string
  session_kind?: number
  image_urls?: string[]
}

interface ChatRun {
  run_id: string
  session_id: string
  status: "running" | "completed" | "interrupted" | "failed"
  last_event_id: number
}

interface StreamEvent {
  type: string
  data?: any
}

const LAST_SESSION_KEY = "lumen:last-session-id"
const RECONNECT_DELAY_MS = 600

const sleep = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms))

export function useChatStream(persistActiveSession = true) {
  const messages = reactive<ChatMessage[]>([])
  const sending = ref(false)
  const sessionId = ref("")
  const statusText = ref("等待输入")
  const subscriptionController = ref<AbortController | null>(null)
  const activeRunId = ref("")
  const lastEventId = ref(0)
  const lastUserPrompt = ref("")

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

  const rememberSession = (sid: string) => {
    if (!persistActiveSession) return
    if (sid) localStorage.setItem(LAST_SESSION_KEY, sid)
    else localStorage.removeItem(LAST_SESSION_KEY)
  }

  const pretty = (value: unknown) => JSON.stringify(value, null, 2)
  const nowStamp = () => new Date().toLocaleTimeString("zh-CN", { hour12: false })

  const addMessage = (role: "user" | "assistant") => {
    const message: ChatMessage = {
      id: crypto.randomUUID(),
      role,
      roleLabel: role === "user" ? "User" : "Assistant",
      time: nowStamp(),
      blocks: [],
    }
    messages.push(message)
    return message
  }

  const getOrCreateAssistant = () => {
    let message = messages[messages.length - 1]
    if (!message || message.role !== "assistant") message = addMessage("assistant")
    return message
  }

  const trackPending = (block: ChatBlock) => {
    if (block.kind === "text") pendingTexts.value.push(block)
    else if (block.kind === "thinking") pendingThinkings.value.push(block)
    else if (block.kind === "tool_use") pendingToolUses.value.push(block)
    else if (block.kind === "tool_result") pendingToolResults.value.push(block)
    else if (block.kind === "error") pendingErrors.value.push(block)
  }

  const pushBlock = (
    kind: string,
    title: string,
    content: string,
    expanded = true,
  ) => {
    const block: ChatBlock = {
      id: crypto.randomUUID(),
      kind,
      title,
      content,
      expanded,
    }
    getOrCreateAssistant().blocks.push(block)
    trackPending(block)
    return block
  }

  const appendBlock = (
    kind: string,
    title: string,
    content: string,
    expanded = true,
  ) => {
    const message = getOrCreateAssistant()
    const existing = message.blocks[message.blocks.length - 1]
    if (existing && existing.kind === kind) {
      existing.content += content
      return existing
    }
    return pushBlock(kind, title, content, expanded)
  }

  const applyApprovalResult = (toolCallId: string, approved: boolean) => {
    // 从后往前匹配最近的审批块，兼容切换会话后的完整事件补放。
    for (let messageIndex = messages.length - 1; messageIndex >= 0; messageIndex--) {
      const blocks = messages[messageIndex].blocks
      for (let blockIndex = blocks.length - 1; blockIndex >= 0; blockIndex--) {
        const block = blocks[blockIndex]
        if (block.kind !== "awaiting_approval") continue
        try {
          const calls = JSON.parse(block.content)
          const target = calls.find((call: any) => call.id === toolCallId)
          if (!target) continue
          target._resolved = approved
          block.content = JSON.stringify(calls)
          return
        } catch {
          continue
        }
      }
    }
  }

  const consumeEvent = (event: StreamEvent) => {
    switch (event.type) {
      case "text":
        appendBlock("text", "正文", event.data?.delta ?? "")
        break
      case "thinking":
        appendBlock("thinking", "思考", event.data?.delta ?? "", false)
        break
      case "awaiting_approval": {
        const calls = event.data?.tool_calls ?? []
        if (calls.length) {
          pushBlock(
            "awaiting_approval",
            "等待审批",
            JSON.stringify(calls.map((call: any) => ({ ...call, _resolved: undefined }))),
          )
          statusText.value = "等待审批"
        }
        break
      }
      case "approval_result":
        applyApprovalResult(
          event.data?.tool_call_id ?? "",
          Boolean(event.data?.approved),
        )
        break
      case "tool_use": {
        const data = event.data ?? {}
        pushBlock(
          "tool_use",
          data.name ?? "工具调用",
          pretty({
            id: data.tool_call_id ?? "",
            name: data.name ?? "tool",
            input: data.arguments ?? {},
          }),
          false,
        )
        break
      }
      case "tool_result": {
        const data = event.data ?? {}
        pushBlock(
          "tool_result",
          "工具结果: " + (data.name ?? "工具"),
          data.result_preview ?? "",
          false,
        )
        break
      }
      case "assistant_done":
        statusText.value = "本轮完成"
        break
      case "error":
        if (event.data?.message !== "stream_interrupted") {
          appendBlock("error", "错误", event.data?.message ?? "未知错误")
        }
        break
    }
  }

  const parseStored = (stored: StoredMessage[]): ChatMessage[] => {
    const pad = (value: number) => String(value).padStart(2, "0")
    return stored.map(item => {
      const date = new Date(item.created_at)
      return {
        id: crypto.randomUUID(),
        role: item.role as "user" | "assistant",
        roleLabel: item.role === "user" ? "User" : "Assistant",
        time:
          pad(date.getMonth() + 1) +
          "/" +
          pad(date.getDate()) +
          " " +
          pad(date.getHours()) +
          ":" +
          pad(date.getMinutes()),
        status: item.status,
        seq: item.seq,
        blocks: item.content.map((block): ChatBlock => {
          if (block.type === "thinking") {
            return {
              id: crypto.randomUUID(),
              kind: "thinking",
              title: "思考",
              content: block.thinking ?? "",
              expanded: false,
            }
          }
          if (block.type === "tool_use") {
            return {
              id: crypto.randomUUID(),
              kind: "tool_use",
              title: block.name ?? "工具调用",
              content: pretty(block.input ?? {}),
              expanded: false,
            }
          }
          if (block.type === "tool_result") {
            return {
              id: crypto.randomUUID(),
              kind: "tool_result",
              title: "工具结果",
              content: block.content ?? "",
              expanded: false,
            }
          }
          if (block.type === "image_url") {
            return {
              id: crypto.randomUUID(),
              kind: "image",
              title: "图片",
              content: block.image_url?.url ?? "",
              expanded: true,
            }
          }
          return {
            id: crypto.randomUUID(),
            kind: "text",
            title: "正文",
            content: block.text ?? "",
            expanded: false,
          }
        }),
      }
    })
  }

  const loadStoredMessages = async (sid: string) => {
    const response = await fetch(
      "/v1/sessions/" + encodeURIComponent(sid) + "/messages?limit=20",
    )
    if (!response.ok) return false
    const stored: StoredMessage[] = await response.json()
    messages.splice(0, messages.length, ...parseStored(stored))
    return true
  }

  const detachSubscription = () => {
    subscriptionController.value?.abort()
    subscriptionController.value = null
    sending.value = false
    activeRunId.value = ""
    lastEventId.value = 0
    clearPendingBlocks()
  }

  const readEvents = async (
    runId: string,
    controller: AbortController,
  ) => {
    const response = await fetch(
      "/v1/chat/runs/" +
        encodeURIComponent(runId) +
        "/events?after=" +
        lastEventId.value,
      { signal: controller.signal },
    )
    if (!response.ok || !response.body) {
      throw new Error("订阅会话失败: HTTP " + response.status)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ""
    while (true) {
      const result = await reader.read()
      if (result.done) break
      buffer += decoder.decode(result.value, { stream: true })
      const frames = buffer.split("\n\n")
      buffer = frames.pop() ?? ""
      for (const frame of frames) {
        if (frame.startsWith(":")) continue
        const idLine = frame.split("\n").find(line => line.startsWith("id:"))
        const dataLine = frame.split("\n").find(line => line.startsWith("data:"))
        if (idLine) {
          const value = Number(idLine.slice(3).trim())
          if (Number.isFinite(value)) lastEventId.value = value
        }
        if (!dataLine) continue
        const data = dataLine.slice(5).trim()
        if (!data || data === "[DONE]") continue
        consumeEvent(JSON.parse(data))
      }
    }
  }

  const subscribe = async (run: ChatRun, replayFromStart = false) => {
    subscriptionController.value?.abort()
    const controller = new AbortController()
    subscriptionController.value = controller
    activeRunId.value = run.run_id
    lastEventId.value = replayFromStart ? 0 : lastEventId.value
    sending.value = true
    statusText.value = "生成中..."

    while (!controller.signal.aborted) {
      try {
        await readEvents(run.run_id, controller)
        const statusResponse = await fetch(
          "/v1/chat/runs/" + encodeURIComponent(run.run_id),
        )
        if (!statusResponse.ok) break
        const latest: ChatRun = await statusResponse.json()
        if (latest.status === "running") {
          await sleep(RECONNECT_DELAY_MS)
          continue
        }
        statusText.value =
          latest.status === "interrupted"
            ? "已中断"
            : latest.status === "failed"
              ? "生成失败"
              : "响应完成"
        await loadStoredMessages(run.session_id)
        break
      } catch (error) {
        if (controller.signal.aborted) return
        statusText.value = "连接恢复中..."
        await sleep(RECONNECT_DELAY_MS)
      }
    }

    if (subscriptionController.value === controller) {
      subscriptionController.value = null
      activeRunId.value = ""
      sending.value = false
      clearPendingBlocks()
    }
  }

  const findActiveRun = async (sid: string): Promise<ChatRun | undefined> => {
    const response = await fetch("/v1/chat/runs")
    if (!response.ok) return undefined
    const runs: ChatRun[] = await response.json()
    return runs.find(run => run.session_id === sid)
  }

  const send = async (text: string, options?: SendOptions) => {
    const content = text.trim()
    if (!content || sending.value) return
    lastUserPrompt.value = content
    if (!sessionId.value) {
      sessionId.value = crypto.randomUUID()
      rememberSession(sessionId.value)
    }

    addMessage("user").blocks.push({
      id: crypto.randomUUID(),
      kind: "text",
      title: "用户输入",
      content,
      expanded: true,
    })
    sending.value = true
    statusText.value = "启动生成..."

    try {
      const response = await fetch("/v1/chat/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: content,
          session_id: sessionId.value,
          mode: options?.mode ?? "agent",
          approval_mode: options?.approval_mode,
          mcp_server_ids: options?.mcp_server_ids,
          self_system: options?.self_system,
          session_kind: options?.session_kind,
          image_urls: options?.image_urls?.length ? options.image_urls : undefined,
        }),
      })
      if (!response.ok) throw new Error(await response.text())
      const run: ChatRun = await response.json()
      sessionId.value = run.session_id
      rememberSession(run.session_id)
      void subscribe(run, true)
    } catch (error) {
      sending.value = false
      const detail = error instanceof Error ? error.message : String(error)
      appendBlock("error", "会话异常", detail)
      statusText.value = "启动失败"
    }
  }

  const interrupt = async () => {
    if (!activeRunId.value) return
    const response = await fetch(
      "/v1/chat/runs/" + encodeURIComponent(activeRunId.value) + "/interrupt",
      { method: "POST" },
    )
    if (response.ok) statusText.value = "中断处理中..."
  }

  const approve = async (
    blockId: string,
    toolCallId: string,
    approved: boolean,
  ) => {
    if (!sessionId.value) return
    for (const message of messages) {
      const block = message.blocks.find(item => item.id === blockId)
      if (!block || block.kind !== "awaiting_approval") continue
      try {
        const calls = JSON.parse(block.content)
        const target = calls.find((call: any) => call.id === toolCallId)
        if (!target || target._resolved !== undefined) return
        target._resolved = approved
        block.content = JSON.stringify(calls)
      } catch {
        return
      }
      break
    }
    await fetch("/v1/chat/stream/approve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId.value,
        approvals: { [toolCallId]: approved },
      }),
    })
  }

  const loadSession = async (sid: string) => {
    detachSubscription()
    sessionId.value = sid
    rememberSession(sid)
    statusText.value = "加载会话..."
    await loadStoredMessages(sid)
    const active = await findActiveRun(sid)
    if (active) {
      void subscribe(active, true)
    } else {
      await loadStoredMessages(sid)
      statusText.value = "已加载会话"
    }
  }

  const reset = async () => {
    detachSubscription()
    messages.splice(0)
    sessionId.value = ""
    rememberSession("")
    statusText.value = "已新建会话"
  }

  const restoreLastSession = async () => {
    if (!persistActiveSession) return
    const sid = localStorage.getItem(LAST_SESSION_KEY)
    if (sid) await loadSession(sid)
  }

  const setSessionId = (sid: string) => {
    sessionId.value = sid
    rememberSession(sid)
  }

  const streamingMessageId = computed(() => {
    if (!sending.value || messages.length === 0) return ""
    const last = messages[messages.length - 1]
    return last.role === "assistant" ? last.id : ""
  })

  return {
    messages,
    sending,
    sessionId,
    statusText,
    streamingMessageId,
    lastUserPrompt,
    activeRunId,
    send,
    interrupt,
    approve,
    reset,
    loadSession,
    setSessionId,
    restoreLastSession,
    detachSubscription,
    clearPendingBlocks,
  }
}
