import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/stores/auth'

/** 正在刷新 token 的 promise（防并发） */
let refreshPromise: Promise<boolean> | null = null

/** 等待重试的请求队列 */
let pendingQueue: Array<{
  resolve: (token: string) => void
  reject: (err: Error) => void
}> = []

// ============================================================
// Axios 实例
// ============================================================
const api = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
})

// ============================================================
// 请求拦截器 — 自动注入 Token
// ============================================================
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const auth = useAuthStore()
    const token = auth.token
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

// ============================================================
// 响应拦截器 — 401 自动刷新 Token + 重试
// ============================================================
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean
    }

    // 非 401、或已重试过、或没有 config -> 直接拒绝
    if (
      !error.response ||
      error.response.status !== 401 ||
      originalRequest._retry ||
      !originalRequest
    ) {
      return Promise.reject(normalizeError(error))
    }

    const auth = useAuthStore()
    if (auth.user?.is_demo || auth.token === 'demo-token') {
      return Promise.reject(normalizeError(error))
    }

    // 标记当前请求已重试过
    originalRequest._retry = true

    try {
      // 尝试刷新 Token
      const newToken = await refreshAccessToken()

      // 用新 Token 重放原始请求
      if (originalRequest.headers) {
        originalRequest.headers.Authorization = `Bearer ${newToken}`
      }
      return api(originalRequest)
    } catch {
      // 刷新失败 -> 仅清除登录态，不跳转（由路由守卫负责跳转）
      const auth = useAuthStore()
      auth.logout()
      return Promise.reject(normalizeError(error))
    }
  },
)

// ============================================================
// Token 刷新（防并发）
// ============================================================
async function refreshAccessToken(): Promise<string> {
  // 如果已有刷新中的 promise，直接排队
  if (refreshPromise) {
    return new Promise((resolve, reject) => {
      pendingQueue.push({ resolve, reject })
    })
  }

  refreshPromise = doRefresh()

  try {
    const success = await refreshPromise

    if (!success) {
      throw new Error('Token refresh failed')
    }

    const auth = useAuthStore()
    const newToken = auth.token
    if (!newToken) throw new Error('Token not found after refresh')

    // 唤醒队列中等待的请求
    pendingQueue.forEach(({ resolve }) => resolve(newToken!))
    pendingQueue = []

    return newToken
  } catch (err) {
    pendingQueue.forEach(({ reject }) => reject(err as Error))
    pendingQueue = []
    throw err
  } finally {
    refreshPromise = null
  }
}

/**
 * 实际执行刷新 Token 的请求
 * 后端暂未提供 /auth/refresh 接口，token 过期后引导重新登录
 */
async function doRefresh(): Promise<boolean> {
  return false
}

// ============================================================
// 统一错误处理
// ============================================================
export interface ApiError {
  code: string
  message: string
  status?: number
  traceId?: string
}

function normalizeError(error: AxiosError): ApiError {
  // 网络断开
  if (!error.response) {
    return {
      code: 'NETWORK_ERROR',
      message: error.message === 'canceled'
        ? '请求已取消'
        : '网络连接失败，请检查网络',
      traceId: undefined,
    }
  }

  const data = error.response.data as Record<string, any> | undefined
  const status = error.response.status

  const codeMapping: Record<number, string> = {
    400: 'VALIDATION_ERROR',
    401: 'UNAUTHORIZED',
    403: 'FORBIDDEN',
    404: 'NOT_FOUND',
    429: 'RATE_LIMITED',
    500: 'SERVER_ERROR',
    502: 'BAD_GATEWAY',
    503: 'SERVICE_UNAVAILABLE',
  }

  return {
    code: data?.code || codeMapping[status] || 'UNKNOWN_ERROR',
    message: data?.message || getDefaultMessage(status),
    status,
    traceId: data?.trace_id,
  }
}

function getDefaultMessage(status: number): string {
  const messages: Record<number, string> = {
    400: '请求参数有误',
    401: '身份验证失败，请重新登录',
    403: '没有权限访问',
    404: '请求的资源不存在',
    429: '请求过于频繁，请稍后再试',
    500: '服务器内部错误',
    502: '网关错误',
    503: '服务暂不可用',
  }
  return messages[status] || `请求失败 (${status})`
}

// ============================================================
// 业务 API 封装
// ============================================================

// 注意: 以下 API 函数为旧多页流程遗留代码，调用不存在的端点。
// 实际寻源流程请使用 @/api/procure.ts 的 SSE 流式接口。
// RFQ/供应商/审核等接口请使用 @/api/enterprise.ts。
// 这些函数仅保留以供参考，后续可彻底移除。

export default api
