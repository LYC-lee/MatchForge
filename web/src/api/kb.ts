/**
 * 知识库 API 客户端
 * 复用 web/src/api/index.ts 的 axios 实例 (自带 /api/v1 baseURL + Bearer 注入)
 */
import api from './index'

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
export interface RetrievedChunk {
  chunk_id: number
  chunk_uid: string
  chunk_type: string
  product_model: string | null
  business_type: string | null
  score: number
  language: string
  source_type: string
}

export interface ChatResult {
  request_id: string
  answer: string
  intent: string
  language: string
  retrieved: RetrievedChunk[] | { company_id: number; count: number; chunks: RetrievedChunk[] }[]
  mode: string
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
