import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

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
      // 刷新失败 -> 登出
      auth.logout()
      if (router.currentRoute.value.name !== 'login') {
        router.replace({ name: 'login' })
      }
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
// SSE 流式寻源
// ============================================================
export interface ProcureState {
  thread_id: string
  raw_query: string
  parsed_spec: Record<string, any> | null
  normalized_spec: Record<string, any> | null
  alternatives: Alternative[]
  matched_suppliers: Supplier[]
  rfq_doc: string | null
  rfq_id: string | null
  lead_grade: LeadGrade | null
  errors: string[]
}

export interface Alternative {
  part: string
  brand: string
  confidence: number
  source: string
  verified: boolean
  specs?: Record<string, any>
  level?: 'L1' | 'L2' | 'L3' | 'L4' | 'L5'
  reason?: string
  diff_items?: DiffItem[]
}

export interface DiffItem {
  param: string
  original: string
  alternative: string
  type: 'match' | 'diff' | 'risk'
}

export interface Supplier {
  id: string
  name: string
  score: number
  category: string
  brands: string[]
  qualifications: string[]
  location: string
  moq?: number
  lead_time_weeks?: number
  in_stock: boolean
  data_source: string
  updated_at: string
}

export interface LeadGrade {
  grade: 'A' | 'B' | 'C' | 'D'
  score: number
  reasons: string[]
}

// SSE: 流式寻源
export function procureStream(
  query: string,
  threadId: string | null,
  onEvent: (event: string, data: any) => void,
  onError: (err: Error) => void,
  signal?: AbortSignal,
): AbortController {
  const controller = new AbortController()
  const mergedSignal = signal
    ? combineAbortSignals(controller.signal, signal)
    : controller.signal

  fetch('/api/v1/procure', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, thread_id: threadId }),
    signal: mergedSignal,
  })
    .then(async (response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const reader = response.body?.getReader()
      if (!reader) throw new Error('No response body')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        let currentEvent = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              onEvent(currentEvent, data)
            } catch {
              // skip malformed
            }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name === 'AbortError') return
      onError(err)
    })

  return controller
}

/** 合并多个 AbortSignal */
function combineAbortSignals(...signals: AbortSignal[]): AbortSignal {
  const controller = new AbortController()
  for (const sig of signals) {
    if (sig.aborted) {
      controller.abort(sig.reason)
      return controller.signal
    }
    sig.addEventListener('abort', () => controller.abort(sig.reason), { once: true })
  }
  return controller.signal
}

// ============================================================
// 业务 API 封装
// ============================================================

// 解析需求 (F1)
export function parseQuery(query: string) {
  return api.post('/parse', { query })
}

// 替代料推荐 (F4)
export function getAlternatives(spec: Record<string, any>) {
  return api.post('/alternatives', { spec })
}

// 供应商匹配 (F6)
export function matchSuppliers(
  spec: Record<string, any>,
  alternatives: Alternative[],
  filters?: Record<string, any>,
) {
  return api.post('/match', { spec, alternatives, filters })
}

// 生成询价单 (F7)
export function generateRfq(
  spec: Record<string, any>,
  alternatives: Alternative[],
  suppliers: Supplier[],
) {
  return api.post('/rfq/generate', { spec, alternatives, suppliers })
}

// 提交询价
export function submitRfq(rfqDoc: string, spec: Record<string, any>, supplierIds: string[]) {
  return api.post('/rfq/submit', {
    rfq_doc: rfqDoc,
    parsed_spec: spec,
    target_supplier_ids: supplierIds,
  })
}

// 获取询价单详情
export function getRfqDetail(rfqId: string) {
  return api.get(`/rfq/${rfqId}`)
}

// 获取询价单列表
export function getRfqs() {
  return api.get('/rfqs')
}

// 供应商列表/搜索
export function getSuppliers(params?: Record<string, any>) {
  return api.get('/suppliers', { params })
}

// 供应商详情
export function getSupplierDetail(id: string) {
  return api.get(`/suppliers/${id}`)
}

// 供应商入驻
export function onboardSupplier(data: Record<string, any>) {
  return api.post('/suppliers/onboard', data)
}

// 运营: 审核队列
export function getAuditQueue(type: 'alternatives' | 'suppliers') {
  return api.get('/admin/audit', { params: { type } })
}

// 运营: 审核操作
export function performAudit(
  id: string,
  action: 'approve' | 'reject' | 'mark_risk',
  payload?: Record<string, any>,
) {
  return api.post(`/admin/audit/${id}`, { action, ...payload })
}

// 运营: 指标
export function getAdminMetrics() {
  return api.get('/admin/metrics')
}

// 线索列表（供应商端）
export function getLeads(params?: Record<string, any>) {
  return api.get('/leads', { params })
}

export default api
