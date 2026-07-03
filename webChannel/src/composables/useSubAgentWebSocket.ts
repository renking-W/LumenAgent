/**
 * useSubAgentWebSocket — Sub-Agent 实时事件 WebSocket 连接管理。
 *
 * 直连 FastAPI（ws://127.0.0.1:21675/v1/sub-agents/ws），实时接收 session/update
 * 和 permission_request 事件。
 */

import { onUnmounted, ref } from 'vue'

const WS_BASE = 'ws://127.0.0.1:21675/v1/sub-agents/ws'

export interface SubAgentEvent {
  type: string
  event: string
  run_id: string
  [key: string]: unknown
}

export function useSubAgentWebSocket() {
  const connected = ref(false)
  const currentRunId = ref<string | null>(null)

  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let heartbeatTimer: ReturnType<typeof setInterval> | null = null
  let reconnectAttempts = 0
  let manualDisconnect = false

  const eventHandlers = new Set<(event: SubAgentEvent) => void>()
  const MAX_RECONNECT_DELAY = 30000

  function onEvent(handler: (event: SubAgentEvent) => void) {
    eventHandlers.add(handler)
  }

  function offEvent(handler: (event: SubAgentEvent) => void) {
    eventHandlers.delete(handler)
  }

  function _dispatch(event: SubAgentEvent) {
    for (const handler of eventHandlers) {
      handler(event)
    }
  }

  function _startHeartbeat() {
    _stopHeartbeat()
    heartbeatTimer = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'pong' }))
      }
    }, 25000)
  }

  function _stopHeartbeat() {
    if (heartbeatTimer !== null) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  function _scheduleReconnect() {
    if (manualDisconnect || !currentRunId.value) return
    if (reconnectTimer !== null) return
    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), MAX_RECONNECT_DELAY)
    reconnectAttempts++
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      if (currentRunId.value) _doConnect(currentRunId.value)
    }, delay)
  }

  function _cancelReconnect() {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  function _doConnect(runId: string) {
    if (ws) { ws.close(); ws = null }

    try {
      ws = new WebSocket(WS_BASE)
    } catch (err) {
      console.error('[SubAgent WS] 连接失败:', err)
      _scheduleReconnect()
      return
    }

    ws.onopen = () => {
      connected.value = true
      manualDisconnect = false
      reconnectAttempts = 0
      ws?.send(JSON.stringify({ type: 'subscribe', run_id: runId }))
      _startHeartbeat()
    }

    ws.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'subscribed' || data.type === 'ping') return
        if (data.type === 'sub_agent_event') {
          _dispatch(data as SubAgentEvent)
        }
      } catch { /* ignore */ }
    }

    ws.onclose = () => {
      connected.value = false
      _stopHeartbeat()
      if (!manualDisconnect) _scheduleReconnect()
    }

    ws.onerror = () => { ws?.close() }
  }

  function connect(runId: string) {
    if (currentRunId.value === runId && connected.value) return
    manualDisconnect = false
    currentRunId.value = runId
    _cancelReconnect()
    _doConnect(runId)
  }

  function disconnect() {
    manualDisconnect = true
    currentRunId.value = null
    _cancelReconnect()
    _stopHeartbeat()
    if (ws) {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'unsubscribe' }))
      ws.close()
      ws = null
    }
    connected.value = false
  }

  onUnmounted(() => {
    disconnect()
    eventHandlers.clear()
  })

  return { connected, currentRunId, connect, disconnect, onEvent, offEvent }
}
