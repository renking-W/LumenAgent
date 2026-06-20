/**
 * useVMWebSocket — VM 实时事件 WebSocket 连接管理。
 *
 * 直连 FastAPI（ws://127.0.0.1:21675/v1/vm/ws），绕开 Flask 代理。
 * 自动管理连接生命周期：subscribe、事件转发、心跳、断线重连。
 */

import { onUnmounted, ref } from 'vue'
import type { VMWebSocketEvent } from '../types'

const WS_BASE = 'ws://127.0.0.1:21675/v1/vm/ws'

export function useVMWebSocket() {
  const connected = ref(false)
  const currentVmId = ref<string | null>(null)

  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let heartbeatTimer: ReturnType<typeof setInterval> | null = null
  let reconnectAttempts = 0
  let manualDisconnect = false

  const eventHandlers = new Set<(event: VMWebSocketEvent) => void>()

  const MAX_RECONNECT_DELAY = 30000

  // ── 事件回调管理 ──
  function onEvent(handler: (event: VMWebSocketEvent) => void) {
    eventHandlers.add(handler)
  }

  function offEvent(handler: (event: VMWebSocketEvent) => void) {
    eventHandlers.delete(handler)
  }

  function _dispatch(event: VMWebSocketEvent) {
    for (const handler of eventHandlers) {
      handler(event)
    }
  }

  // ── 心跳 ──
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

  // ── 重连 ──
  function _scheduleReconnect() {
    if (manualDisconnect || !currentVmId.value) return
    if (reconnectTimer !== null) return

    const delay = Math.min(
      1000 * Math.pow(2, reconnectAttempts),
      MAX_RECONNECT_DELAY,
    )
    reconnectAttempts++
    console.log(`[VM WS] ${delay}ms 后重连...`)
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      if (currentVmId.value) {
        _doConnect(currentVmId.value)
      }
    }, delay)
  }

  function _cancelReconnect() {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  // ── 连接 ──
  function _doConnect(vmId: string) {
    if (ws) {
      ws.close()
      ws = null
    }

    try {
      ws = new WebSocket(WS_BASE)
    } catch (err) {
      console.error('[VM WS] 连接失败:', err)
      _scheduleReconnect()
      return
    }

    ws.onopen = () => {
      console.log('[VM WS] 已连接, 订阅:', vmId)
      connected.value = true
      manualDisconnect = false
      reconnectAttempts = 0
      ws?.send(JSON.stringify({ type: 'subscribe', vm_id: vmId }))
      _startHeartbeat()
    }

    ws.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data)
        // 忽略系统消息
        if (data.type === 'subscribed') {
          console.log('[VM WS] 订阅确认:', data.vm_id)
          return
        }
        if (data.type === 'ping') {
          // 服务端心跳 ping，客户端已通过定时器发 pong
          return
        }
        if (data.type === 'vm_event') {
          _dispatch(data as VMWebSocketEvent)
        }
      } catch {
        // 忽略非 JSON 消息
      }
    }

    ws.onclose = () => {
      console.log('[VM WS] 连接关闭')
      connected.value = false
      _stopHeartbeat()
      if (!manualDisconnect) {
        _scheduleReconnect()
      }
    }

    ws.onerror = (err) => {
      console.error('[VM WS] 错误:', err)
      ws?.close()
    }
  }

  // ── 公开方法 ──
  function connect(vmId: string) {
    if (currentVmId.value === vmId && connected.value) return
    manualDisconnect = false
    currentVmId.value = vmId
    _cancelReconnect()
    _doConnect(vmId)
  }

  function disconnect() {
    manualDisconnect = true
    currentVmId.value = null
    _cancelReconnect()
    _stopHeartbeat()
    if (ws) {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'unsubscribe' }))
      }
      ws.close()
      ws = null
    }
    connected.value = false
  }

  // ── 生命周期清理（组件卸载时） ──
  onUnmounted(() => {
    disconnect()
    eventHandlers.clear()
  })

  return {
    connected,
    currentVmId,
    connect,
    disconnect,
    onEvent,
    offEvent,
  }
}
