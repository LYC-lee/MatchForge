/**
 * 知识库 API 客户端
 * 复用 web/src/api/index.ts 的 axios 实例 (自带 /api/v1 baseURL + Bearer 注入)
 */
import api from './index'
import type { Citation } from '@/types/procure'

// ============================================================
// 认证
// ============================================================
export function kbLogin(name: string, account: string, role: 'user' | 'admin' = 'user') {
  return api.post('/auth/login', { name, account, role })
}

// ============================================================
// 公司
// ============================================================
export interface CompanyListItem {
  id: number
  name: string
  name_en: string | null
  country: string | null
  region: string | null
  segment_code: string | null
  segment_name: string | null
  role: string | null
  knowledge_status: string
  last_generated_at: string | null
}

export interface CompanyDetail extends CompanyListItem {
  name_alias: string | null
  website: string | null
  description: string | null
  segment_name_en: string | null
  chain_position: string | null
  confidence_level: string | null
}

export function getCompanies(params?: { search?: string; segment?: string; knowledge_ready?: boolean }) {
  return api.get('/companies', { params })
}

export function getSegments() {
  return api.get('/companies/segments')
}

export function getCompanyDetail(id: number) {
  return api.get(`/companies/${id}`)
}

export function getCompanyKnowledge(id: number) {
  return api.get(`/companies/${id}/knowledge`)
}

export function getCompanyProducts(id: number) {
  return api.get(`/companies/${id}/products`)
}

// ============================================================
// 聊天 / RAG
// ============================================================
/**
 * 后端 kb/rag.py `_trace_chunk` 实际返回结构:
 * { chunk_id, chunk_uid, chunk_type, product_model, business_type, score, language, source_type }
 * manual_type / excerpt / text / company_id 视后端版本可选,前端防御性读取。
 */
export interface RetrievedChunk {
  chunk_id: number
  chunk_uid: string
  chunk_type: string
  product_model: string | null
  business_type: string | null
  score: number
  language: string
  source_type: string
  /** 手册类型 product|business (新版后端输出,旧版缺省) */
  manual_type?: string | null
  /** 片段文本(新版后端可能输出 excerpt 或全量 text) */
  excerpt?: string
  text?: string
  company_id?: number
}

export interface ChatResult {
  request_id: string
  answer: string
  intent: string
  language: string
  retrieved: RetrievedChunk[] | { company_id: number; count: number; chunks: RetrievedChunk[] }[]
  mode: string
}

/**
 * 将问答 API 的 retrieved 字段映射为统一的 Citation[](引用回显契约 C2)。
 * 同时兼容单公司(扁平数组)与多公司比较(按 company_id 分组)两种结构;
 * 缺失字段防御: doc 缺省 'business', company_id 缺省 fallbackCompanyId, excerpt 缺省 ''。
 */
export function mapRetrievedToCitations(
  retrieved: ChatResult['retrieved'] | undefined | null,
  fallbackCompanyId = 0,
): Citation[] {
  if (!retrieved || !Array.isArray(retrieved)) return []
  const flat: { chunk: RetrievedChunk; groupCompanyId?: number }[] = []
  for (const item of retrieved as (RetrievedChunk & { chunks?: RetrievedChunk[] })[]) {
    if (!item) continue
    if (Array.isArray(item.chunks)) {
      const groupId = (item as unknown as { company_id?: number }).company_id
      for (const c of item.chunks) flat.push({ chunk: c, groupCompanyId: groupId })
    } else {
      flat.push({ chunk: item })
    }
  }
  return flat.map(({ chunk: c, groupCompanyId }, i) => ({
    doc: c.manual_type || 'business',
    chunk_id: String(c.chunk_id ?? c.chunk_uid ?? i),
    chunk_uid: c.chunk_uid || String(c.chunk_id ?? ''),
    score: typeof c.score === 'number' ? c.score : 0,
    excerpt: c.excerpt ?? c.text ?? '',
    company_id: c.company_id ?? groupCompanyId ?? fallbackCompanyId,
    language: c.language || '',
  }))
}

export function chatSingle(company_id: number, query: string, language?: string) {
  return api.post<ChatResult>('/chat/ask', { company_id, query, language })
}

export function chatCompare(company_ids: number[], query: string, language?: string) {
  return api.post<ChatResult>('/chat/compare', { company_ids, query, language })
}

export function getTrace(request_id: string) {
  return api.get(`/chat/trace/${request_id}`)
}

// ============================================================
// 管理员
// ============================================================
export interface KbStats {
  company_count: number
  companies_ready: number
  manual_count: number
  zh_manual_count: number
  en_manual_count: number
  product_manual_count: number
  business_manual_count: number
  product_chunk_count: number
  business_chunk_count: number
  zh_chunk_count: number
  en_chunk_count: number
  product_count: number
  vector_count: number
  vector_backend: string
  embedder: { available: boolean; model: string; dim: number }
}

export interface KbTask {
  task_id: string
  company_id: number | null
  task_type: string
  total_steps: number
  completed_steps: number
  progress: number
  status: string
  current_stage: string | null
  error_message: string | null
  retry_count: number
  result_summary: Record<string, any> | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export function adminStats() {
  return api.get<KbStats>('/admin/kb/stats')
}

export function adminCapabilities() {
  return api.get('/admin/kb/capabilities')
}

export function adminGenerate(company_ids?: number[], force = false) {
  return api.post('/admin/kb/generate', { company_ids, force })
}

export function adminIncremental(company_id: number) {
  return api.post(`/admin/kb/incremental/${company_id}`)
}

export function adminRebuildIndex(drop_first = false) {
  return api.post('/admin/kb/rebuild-index', { drop_first })
}

export function adminListTasks() {
  return api.get('/admin/kb/tasks')
}

export function adminGetTask(task_id: string) {
  return api.get(`/admin/kb/tasks/${task_id}`)
}

export function adminTaskFailures(task_id: string) {
  return api.get(`/admin/kb/tasks/${task_id}/failures`)
}

export function adminCancelTask(task_id: string) {
  return api.post(`/admin/kb/tasks/${task_id}/cancel`)
}
