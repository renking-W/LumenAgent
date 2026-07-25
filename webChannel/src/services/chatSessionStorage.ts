// 活动聊天 Session 只用于同一次登录状态下的页面刷新恢复。
const ACTIVE_CHAT_SESSION_KEY = 'lumen:last-session-id'

export const readRememberedChatSession = () => {
  return localStorage.getItem(ACTIVE_CHAT_SESSION_KEY) ?? ''
}

export const rememberChatSession = (sessionId: string) => {
  if (sessionId) {
    localStorage.setItem(ACTIVE_CHAT_SESSION_KEY, sessionId)
    return
  }
  localStorage.removeItem(ACTIVE_CHAT_SESSION_KEY)
}

export const clearRememberedChatSession = () => {
  localStorage.removeItem(ACTIVE_CHAT_SESSION_KEY)
}