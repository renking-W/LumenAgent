import { computed, readonly, ref } from 'vue'

export interface AuthUser {
  id: string
  username: string
  role: 'user' | 'admin'
  daily_round_limit: number
  unlimited: boolean
  enabled: boolean
  created_at: string
  last_login_at: string | null
}

interface AuthSession {
  access_token: string
  token_type: string
  expires_at: string
  refresh_at: string
  user: AuthUser
}

const AUTH_STORAGE_KEY = 'lumen:auth-session'
const PUBLIC_AUTH_PATHS = new Set(['/v1/auth/status', '/v1/auth/login'])
const nativeFetch = window.fetch.bind(window)

const authEnabled = ref(false)
const authReady = ref(false)
const authInitializationError = ref('')
const currentUser = ref<AuthUser | null>(null)

let session: AuthSession | null = null
let refreshTimer: number | null = null
let refreshPromise: Promise<AuthSession> | null = null
let fetchInstalled = false

const parseTime = (value: string): number => {
  const result = Date.parse(value)
  return Number.isFinite(result) ? result : 0
}

const readStoredSession = (): AuthSession | null => {
  const raw = localStorage.getItem(AUTH_STORAGE_KEY)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as AuthSession
    if (!parsed.access_token || !parsed.expires_at || !parsed.refresh_at || !parsed.user) {
      return null
    }
    return parsed
  } catch {
    return null
  }
}

const cancelRefreshTimer = () => {
  if (refreshTimer !== null) {
    window.clearTimeout(refreshTimer)
    refreshTimer = null
  }
}

const clearSession = () => {
  cancelRefreshTimer()
  session = null
  currentUser.value = null
  localStorage.removeItem(AUTH_STORAGE_KEY)
}

const scheduleRefresh = () => {
  cancelRefreshTimer()
  if (!session || !authEnabled.value) return
  const delay = Math.max(0, parseTime(session.refresh_at) - Date.now())
  refreshTimer = window.setTimeout(() => {
    void refreshAccessToken().catch(() => clearSession())
  }, delay + 250)
}

const saveSession = (nextSession: AuthSession) => {
  session = nextSession
  currentUser.value = nextSession.user
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(nextSession))
  scheduleRefresh()
  window.dispatchEvent(new CustomEvent('lumen:token-refreshed', {
    detail: { token: nextSession.access_token },
  }))
}

const responseDetail = async (response: Response, fallback: string) => {
  try {
    const body = await response.json() as { detail?: string }
    return body.detail || fallback
  } catch {
    return fallback
  }
}

const authorizationHeaders = (token: string, source?: HeadersInit) => {
  const headers = new Headers(source)
  if (!headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  return headers
}

export const refreshAccessToken = async (): Promise<AuthSession> => {
  if (refreshPromise) return refreshPromise
  if (!session) throw new Error('登录状态已失效')

  refreshPromise = (async () => {
    const response = await nativeFetch('/v1/auth/refresh', {
      method: 'POST',
      headers: authorizationHeaders(session!.access_token),
    })
    if (!response.ok) {
      const message = await responseDetail(response, '登录状态已过期，请重新登录')
      clearSession()
      throw new Error(message)
    }
    const nextSession = await response.json() as AuthSession
    saveSession(nextSession)
    return nextSession
  })().finally(() => {
    refreshPromise = null
  })

  return refreshPromise
}

const ensureFreshToken = async () => {
  if (!session) throw new Error('请先登录')
  if (Date.now() >= parseTime(session.expires_at)) {
    clearSession()
    throw new Error('登录状态已过期，请重新登录')
  }
  if (Date.now() >= parseTime(session.refresh_at)) {
    await refreshAccessToken()
  }
}

const resolveRequestUrl = (input: RequestInfo | URL) => {
  const raw = input instanceof Request ? input.url : input.toString()
  return new URL(raw, window.location.href)
}

export const authFetch: typeof window.fetch = async (input, init = {}) => {
  const url = resolveRequestUrl(input)
  const isSameOriginApi = url.origin === window.location.origin && url.pathname.startsWith('/v1/')
  const isPublicAuthRequest = PUBLIC_AUTH_PATHS.has(url.pathname)

  let requestInit = init
  if (authEnabled.value && isSameOriginApi && !isPublicAuthRequest) {
    await ensureFreshToken()
    requestInit = {
      ...init,
      headers: authorizationHeaders(
        session!.access_token,
        init.headers ?? (input instanceof Request ? input.headers : undefined),
      ),
    }
  }

  const response = await nativeFetch(input, requestInit)
  if (
    response.status === 401
    && authEnabled.value
    && isSameOriginApi
    && !isPublicAuthRequest
  ) {
    clearSession()
  }
  return response
}

export const installAuthenticatedFetch = () => {
  if (fetchInstalled) return
  fetchInstalled = true
  window.fetch = authFetch
  window.addEventListener('storage', event => {
    if (event.key !== AUTH_STORAGE_KEY) return
    session = readStoredSession()
    currentUser.value = session?.user ?? null
    scheduleRefresh()
  })
}

export const initializeAuth = async () => {
  authReady.value = false
  authInitializationError.value = ''
  try {
    const statusResponse = await nativeFetch('/v1/auth/status')
    if (!statusResponse.ok) throw new Error('认证状态接口不可用')
    const statusBody = await statusResponse.json() as { auth_enabled: boolean }
    authEnabled.value = Boolean(statusBody.auth_enabled)

    if (!authEnabled.value) {
      clearSession()
      return
    }

    session = readStoredSession()
    if (!session) return
    if (Date.now() >= parseTime(session.expires_at)) {
      clearSession()
      return
    }
    if (Date.now() >= parseTime(session.refresh_at)) {
      await refreshAccessToken()
    }

    const meResponse = await nativeFetch('/v1/auth/me', {
      headers: authorizationHeaders(session!.access_token),
    })
    if (!meResponse.ok) {
      clearSession()
      return
    }
    const user = await meResponse.json() as AuthUser
    saveSession({ ...session!, user })
  } catch (error) {
    clearSession()
    authInitializationError.value = error instanceof Error
      ? error.message
      : '无法连接认证服务'
  } finally {
    authReady.value = true
  }
}

export const login = async (username: string, password: string) => {
  const response = await nativeFetch('/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: username.trim(), password }),
  })
  if (!response.ok) {
    throw new Error(await responseDetail(response, '登录失败，请检查账号和密码'))
  }
  const nextSession = await response.json() as AuthSession
  saveSession(nextSession)
}

export const logout = () => clearSession()

export const authState = {
  enabled: readonly(authEnabled),
  ready: readonly(authReady),
  initializationError: readonly(authInitializationError),
  user: readonly(currentUser),
  authenticated: computed(() => !authEnabled.value || currentUser.value !== null),
}

export const getAccessToken = () => session?.access_token ?? ''
