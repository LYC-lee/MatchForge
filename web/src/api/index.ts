import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 60000, // 寻源链路可能较长
  headers: { 'Content-Type': 'application/json' },
})

// ============================================================
// SSE 流式寻源 (F1-F6 一站式)
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
  onError: (err: Error) => void
): AbortController {
  const controller = new AbortController()

  fetch('/api/v1/procure', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, thread_id: threadId }),
    signal: controller.signal,
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
    .catch(onError)

  return controller
}

// ============================================================
// 单步接口 (Spike 期可独立调用)
// ============================================================

// 解析需求
export function parseQuery(query: string) {
  return api.post('/parse', { query })
}

// 替代料推荐
export function getAlternatives(spec: Record<string, any>) {
  return api.post('/alternatives', { spec })
}

// 供应商匹配
export function matchSuppliers(
  spec: Record<string, any>,
  alternatives: Alternative[],
  filters?: Record<string, any>
) {
  return api.post('/match', { spec, alternatives, filters })
}

// 生成询价单
export function generateRfq(
  spec: Record<string, any>,
  alternatives: Alternative[],
  suppliers: Supplier[]
) {
  return api.post('/rfq/generate', { spec, alternatives, suppliers })
}

// 提交询价
export function submitRfq(rfqDoc: string, spec: Record<string, any>, supplierIds: string[]) {
  return api.post('/rfq/submit', { rfq_doc: rfqDoc, parsed_spec: spec, target_supplier_ids: supplierIds })
}

// 历史记录
export function getRfqs() {
  return api.get('/rfqs')
}

export function getRfqDetail(rfqId: string) {
  return api.get(`/rfq/${rfqId}`)
}

// 供应商列表/搜索
export function getSuppliers(params?: Record<string, any>) {
  return api.get('/suppliers', { params })
}

export default api