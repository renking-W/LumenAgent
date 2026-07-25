/**
 * useVMWebSocket — VM 实时事件 WebSocket 连接管理。
 *
 * 使用当前页面的主机和协议连接 FastAPI，兼容本地代理与 HTTPS 部署。
 * 自动管理连接生命周期：subscribe、事件转发、心跳、断线重连。
 */

import { onUnmounted, ref } from 'vue'
import type { VMWebSocketEvent } from '../types'
import { getAccessToken } from '../services/auth'

// HTTPS 页面必须使用 WSS，主机和端口始终跟随当前页面。
const WS_PROTOCOL = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
const WS_BASE = `${WS_PROTOCOL}//${window.location.host}/v1/vm/ws`

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
      console.log('[VM WS] 已连接:', vmId)
      connected.value = true
      manualDisconnect = false
      reconnectAttempts = 0
      const token = getAccessToken()
      if (token) {
        // 浏览器 WebSocket 无法设置 Authorization，登录态通过首帧发送。
        ws?.send(JSON.stringify({ type: 'auth', token }))
      } else {
        ws?.send(JSON.stringify({ type: 'subscribe', vm_id: vmId }))
      }
      _startHeartbeat()
    }

    ws.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'auth_ok') {
          const activeVmId = currentVmId.value
          if (activeVmId) {
            ws?.send(JSON.stringify({ type: 'subscribe', vm_id: activeVmId }))
          }
          return
        }
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

  function _handleTokenRefreshed(event: Event) {
    const token = (event as CustomEvent<{ token?: string }>).detail?.token
    if (token && ws?.readyState === WebSocket.OPEN) {
      // HTTP 刷新成功后同步更新长连接身份，避免旧 Token 到期时断开。
      ws.send(JSON.stringify({ type: 'auth_refresh', token }))
    }
  }

  window.addEventListener('lumen:token-refreshed', _handleTokenRefreshed)

  // ── 生命周期清理（组件卸载时） ──
  onUnmounted(() => {
    disconnect()
    eventHandlers.clear()
    window.removeEventListener('lumen:token-refreshed', _handleTokenRefreshed)
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
