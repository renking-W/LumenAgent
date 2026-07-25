// 管理员后台共享的用户、额度和会话接口类型。
export type AdminRole = 'user' | 'admin'

export interface AdminUser {
  id: string
  username: string
  role: AdminRole
  daily_round_limit: number
  unlimited: boolean
  enabled: boolean
  created_at: string
  updated_at: string
  last_login_at: string | null
  used_rounds: number
  session_count: number
}

export interface AdminUserList {
  total: number
  total_users: number
  enabled_users: number
  unlimited_users: number
  used_rounds_today: number
  usage_date: string
  users: AdminUser[]
}

export interface AdminUserSession {
  id: string
  title: string
  kind: number
  created_at: string
  updated_at: string
}

export interface AdminUserSessionList {
  total: number
  sessions: AdminUserSession[]
}

export interface CreateAdminUserPayload {
  username: string
  password: string
  role: AdminRole
  daily_round_limit: number
  unlimited: boolean
}

export interface UpdateAdminUserPayload {
  role?: AdminRole
  daily_round_limit?: number
  unlimited?: boolean
  enabled?: boolean
}

// 统一提取 FastAPI 错误详情，保持后台操作提示一致。
const responseDetail = async (response: Response, fallback: string) => {
  try {
    const body = await response.json() as { detail?: string | { message?: string } }
    if (typeof body.detail === 'string') return body.detail
    return body.detail?.message || fallback
  } catch {
    return fallback
  }
}

const request = async <T>(
  path: string,
  init: RequestInit = {},
  fallback = '请求失败',
): Promise<T> => {
  const response = await fetch(path, {
    ...init,
    headers: {
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...init.headers,
    },
  })
  if (!response.ok) {
    throw new Error(await responseDetail(response, fallback))
  }
  if (response.status === 204) return undefined as T
  return await response.json() as T
}

export const listAdminUsers = async (params: {
  limit: number
  offset: number
  query?: string
  enabled?: boolean
}) => {
  const search = new URLSearchParams({
    limit: String(params.limit),
    offset: String(params.offset),
  })
  if (params.query) search.set('query', params.query)
  if (params.enabled !== undefined) search.set('enabled', String(params.enabled))
  return await request<AdminUserList>(
    '/v1/admin/users?' + search.toString(),
    {},
    '无法读取用户列表',
  )
}

export const createAdminUser = async (payload: CreateAdminUserPayload) => {
  return await request<AdminUser>(
    '/v1/admin/users',
    { method: 'POST', body: JSON.stringify(payload) },
    '创建用户失败',
  )
}

export const updateAdminUser = async (
  userId: string,
  payload: UpdateAdminUserPayload,
) => {
  return await request<AdminUser>(
    '/v1/admin/users/' + encodeURIComponent(userId),
    { method: 'PATCH', body: JSON.stringify(payload) },
    '更新用户失败',
  )
}

export const resetAdminUserPassword = async (
  userId: string,
  password: string,
) => {
  await request<void>(
    '/v1/admin/users/' + encodeURIComponent(userId) + '/password',
    { method: 'PUT', body: JSON.stringify({ password }) },
    '重置密码失败',
  )
}

export const listAdminUserSessions = async (
  userId: string,
  limit = 20,
  offset = 0,
) => {
  const search = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  })
  return await request<AdminUserSessionList>(
    '/v1/admin/users/' + encodeURIComponent(userId) + '/sessions?' + search.toString(),
    {},
    '无法读取用户会话',
  )
}