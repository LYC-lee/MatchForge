/**
 * 企业经营驾驶舱 API 客户端
 *
 * 对接后端 (api/routers/enterprise_context.py + dashboard.py + rfqs.py +
 * supplier_leads.py + audit.py + relationships.py)。
 *
 * 设计原则:
 *  - 优先调用真实接口, 失败时由调用方 (composable) 降级到 mock 数据。
 *  - 所有函数返回 Promise<AxiosResponse>, 异常由调用方 try/catch。
 *  - 类型与后端 payload 对齐, 字段名保持 snake_case 以减少映射成本。
 *
 * 复用 web/src/api/index.ts 的 axios 实例 (自带 /api/v1 baseURL + Bearer 注入)。
 */
import api from './index'

// ============================================================
// 企业上下文 (enterprise_context.router)
// ============================================================

export interface EnterpriseContextItem {
  company_id: number
  company: {
    id: number
    name: string
    name_en: string | null
    name_alias: string | null
    country: string | null
    region: string | null
    website: string | null
    description: string | null
  }
  segment_code: string | null
  segment_name: string | null
  segment_name_en: string | null
  chain_position: string | null
  role: string | null
  product_count: number
  order_count: number
  shortage_count: number
  upstream_count: number
  downstream_count: number
  knowledge_status: string
}

export function getEnterpriseContexts() {
  return api.get('/enterprise-context/companies')
}

export const getEnterpriseCompanies = getEnterpriseContexts

export function getEnterpriseContext(companyId: number) {
  return api.get(`/enterprise-context/${companyId}`)
}

// ============================================================
// 经营驾驶舱聚合 (dashboard.router)
// ============================================================

export interface DashboardProduct {
  id: number
  company_id: number
  product_name: string
  product_model: string
  product_type: string | null
  description: string | null
  monthly_capacity: number | null
  unit: string | null
  status: string | null
}

export interface DashboardOrder {
  id: number
  company_id: number
  product_id: number
  order_number: string
  customer_company_id: number | null
  customer_name?: string
  product_name?: string
  product_model?: string
  quantity: number
  due_date: string | null
  priority: string
  status: string
  /** 演示合并标记: true 表示来自 demo_orders (非基线业务表) */
  is_demo?: boolean
}

export interface DashboardForecast {
  id: number
  company_id: number
  product_id: number
  product_name?: string
  product_model?: string
  forecast_period: string
  forecast_quantity: number
  confidence: number
  source_type: string
}

export interface DashboardShortage {
  id: number
  company_id: number
  product_id: number | null
  product_name: string | null
  part_number: string | null
  part_name: string | null
  category_name: string | null
  shortage_type: string // shortage | warning
  required_qty: number
  available_qty: number
  shortage_qty: number
  safety_stock_qty: number | null
  unit: string | null
  is_critical: boolean
  severity: string // critical | high | medium | low
  status: string
  preferred_supplier_company_id: number | null
  preferred_supplier_name: string | null
  relationship_missing: boolean
  affected_order_numbers: string[]
  affected_product_ids: number[]
  /** 演示合并标记: true 表示来自 demo_shortages (非基线 kb_shortages) */
  is_demo?: boolean
}

export interface DashboardAction {
  action_type: string
  category: string // sourcing | production | sales | collaboration
  priority: string // urgent | high | medium | low
  severity: string
  title: string
  detail: string
  part_number: string | null
  product_id: number | null
  suggested_supplier_company_id: number | null
  suggested_supplier_name: string | null
  relationship_missing: boolean
  shortage_id: number | null
  /** 演示合并标记: true 表示由 demo 缺件合成 (非基线推荐动作) */
  is_demo?: boolean
}

export interface ChatPartnerSummary {
  company_id: number
  company_name: string
  direction: string // upstream | downstream | support
  segment_name: string | null
  relationship_type: string
}

export interface DashboardData {
  company_id: number
  company: EnterpriseContextItem['company'] & {
    segment_code?: string | null
    segment_name?: string | null
    chain_position?: string | null
    role?: string | null
    knowledge_status?: string
  }
  products_summary: {
    total: number
    active_count: number
    items: DashboardProduct[]
  }
  orders_summary: {
    total: number
    active_count: number
    active_total_quantity: number
    by_status: Record<string, number>
    by_priority: Record<string, number>
    items: DashboardOrder[]
  }
  forecast_summary: {
    total: number
    total_forecast_quantity: number
    items: DashboardForecast[]
  }
  shortages: {
    company_id: number
    items: DashboardShortage[]
  }
  recommended_actions: {
    items: DashboardAction[]
  }
  upstream_summary: { total: number; items: ChatPartnerSummary[] }
  downstream_summary: { total: number; items: ChatPartnerSummary[] }
  support_summary: { total: number; items: ChatPartnerSummary[] }
  chat_partners_summary: { total: number; items: ChatPartnerSummary[] }
}

export function getDashboard(companyId: number) {
  return api.get(`/companies/${companyId}/dashboard`)
}

export function getCompanyOrders(companyId: number) {
  return api.get(`/companies/${companyId}/orders`)
}

export const getOrders = getCompanyOrders

export function getCompanyForecasts(companyId: number) {
  return api.get(`/companies/${companyId}/forecasts`)
}

export const getForecasts = getCompanyForecasts

export function getCompanyShortages(companyId: number) {
  return api.get(`/companies/${companyId}/shortages`)
}

export const getShortages = getCompanyShortages

export function recalculateShortages(companyId: number) {
  return api.post(`/companies/${companyId}/shortages/recalculate`)
}

export function getRecommendedActions(companyId: number) {
  return api.get(`/companies/${companyId}/recommended-actions`)
}

// ============================================================
// 产品与 BOM
// ============================================================

export interface ProductionProduct {
  id: number
  company_id: number
  product_name: string
  product_model: string
  product_type: string | null
  description: string | null
  monthly_capacity: number | null
  unit: string | null
  status: string | null
}

export interface BomItem {
  id: number
  product_id: number
  part_number: string
  part_name: string
  category_name: string | null
  required_qty: number
  unit: string | null
  is_critical: boolean
  safety_stock_qty: number | null
  preferred_supplier_company_id: number | null
  preferred_supplier_name: string | null
}

export interface BomSummary {
  company_id: number
  total_parts: number
  critical_parts: number
  items: Array<{
    product_id: number
    product_name: string
    product_model: string
    part_count: number
    critical_count: number
  }>
}

export function getCompanyProducts(companyId: number) {
  return api.get(`/companies/${companyId}/products`)
}

export function getProductBom(productId: number, companyId?: number) {
  const params = companyId ? { company_id: companyId } : undefined
  return api.get(`/products/${productId}/bom`, { params })
}

export function getBomSummary(companyId: number) {
  return api.get(`/companies/${companyId}/bom-summary`)
}

// ============================================================
// RFQ 闭环 (rfqs.router)
// ============================================================

export interface RfqRecord {
  id: number
  rfq_number: string
  buyer_company_id: number
  title: string
  raw_query: string | null
  part_number: string | null
  part_name: string | null
  quantity: number
  unit: string
  target_price: number | null
  lead_time_days: number | null
  accept_alternatives: boolean
  scenario: string | null
  status: string // draft | sent | quoted | closed
  created_by: string
  context: Record<string, any>
  created_at: string | null
  updated_at: string | null
  supplier_leads?: RfqSupplierLead[]
}

export interface RfqSupplierLead {
  id: number
  rfq_id: number
  supplier_company_id: number
  supplier_name: string | null
  match_score: number | null
  match_reason: string | null
  status: string // pending | sent | viewed | quoted | declined
  sent_at: string | null
  viewed_at: string | null
  created_at: string | null
}

export interface QuotationRecord {
  id: number
  rfq_id: number
  supplier_company_id: number
  supplier_name: string | null
  part_number: string | null
  unit_price: number
  currency: string
  moq: number | null
  lead_time_days: number | null
  stock_qty: number | null
  valid_until: string | null
  is_in_stock: boolean
  note: string | null
  created_at: string | null
  rank?: number
  is_lowest?: boolean
  meets_target?: boolean | null
  delta_vs_target?: number | null
}

export interface RfqCreatePayload {
  buyer_company_id: number
  title: string
  part_number?: string
  part_name?: string
  quantity?: number
  unit?: string
  target_price?: number
  lead_time_days?: number
  accept_alternatives?: boolean
  scenario?: string
  raw_query?: string
  supplier_candidates?: number[]
  shortage_id?: string
  product_id?: number
  recommended_action_id?: string
}

export function createRfq(payload: RfqCreatePayload) {
  return api.post('/rfqs', payload)
}

export function listRfqs(params?: { buyer_company_id?: number; status?: string }) {
  return api.get('/rfqs', { params })
}

export function getRfq(rfqId: number) {
  return api.get(`/rfqs/${rfqId}`)
}

export function sendRfq(rfqId: number, supplierCompanyIds?: number[]) {
  return api.post(`/rfqs/${rfqId}/send`, {
    supplier_company_ids: supplierCompanyIds || null,
  })
}

export function listCompanyRfqs(companyId: number, status?: string) {
  return api.get(`/companies/${companyId}/rfqs`, { params: status ? { status } : undefined })
}

export function listQuotations(rfqId: number) {
  return api.get(`/rfqs/${rfqId}/quotations`)
}

export function getQuoteComparison(rfqId: number) {
  return api.get(`/rfqs/${rfqId}/quote-comparison`)
}

export function createQuotation(
  rfqId: number,
  payload: {
    supplier_company_id: number
    part_number?: string
    unit_price: number
    currency?: string
    moq?: number
    lead_time_days?: number
    stock_qty?: number
    valid_until?: string
    is_in_stock?: boolean
    note?: string
  },
) {
  return api.post(`/rfqs/${rfqId}/quotations`, payload)
}

// ============================================================
// 供应商线索 (supplier_leads.router)
// ============================================================

export interface SupplierLead {
  id: number
  rfq_id: number
  rfq_number: string | null
  rfq_title: string | null
  rfq_status: string | null
  buyer_company_id: number | null
  buyer_name: string | null
  supplier_company_id: number
  part_number: string | null
  part_name: string | null
  quantity: number | null
  unit: string | null
  target_price: number | null
  lead_time_days: number | null
  accept_alternatives: boolean | null
  match_score: number | null
  match_reason: string | null
  status: string // pending | sent | viewed | quoted | declined
  sent_at: string | null
  viewed_at: string | null
  created_at: string | null
}

export function getSupplierLeads(companyId: number, status?: string) {
  return api.get(`/suppliers/${companyId}/leads`, { params: status ? { status } : undefined })
}

export function viewLead(leadId: number) {
  return api.post(`/supplier-leads/${leadId}/view`)
}

export function declineLead(leadId: number, note?: string) {
  return api.post(`/supplier-leads/${leadId}/decline`, note ? { note } : undefined)
}

// ============================================================
// 审核队列 (audit.router) -- 需要 admin 会话
// ============================================================

export interface AuditQueueItem {
  id: number
  item_type: string // supplier_capability | rfq_supplier_match | quotation_anomaly
  entity_id: number
  company_id: number | null
  title: string
  /** 判定依据/详情（demo 沙盘与部分后端版本提供） */
  detail?: string
  payload: Record<string, any>
  status: string // pending | approved | rejected
  review_note: string | null
  created_at: string | null
  reviewed_at: string | null
}

/** 审核队列需要 admin 角色; 复用当前会话 token (管理员须通过真实登录获得 admin 会话)。 */
export function getAuditQueue(params?: { status?: string; item_type?: string }) {
  return api.get('/admin/audit-queue', { params })
}

export function approveAuditItem(itemId: number, note?: string) {
  return api.post(`/admin/audit-queue/${itemId}/approve`, note ? { note } : undefined)
}

export function rejectAuditItem(itemId: number, note?: string) {
  return api.post(`/admin/audit-queue/${itemId}/reject`, note ? { note } : undefined)
}

// ============================================================
// 上下游协同问答 (relationships.router)
// ============================================================

export interface ChatPartner {
  company_id: number
  company_name: string
  name_en: string | null
  segment_code: string | null
  segment_name: string | null
  chain_position: string | null
  role: string | null
  knowledge_status: string | null
  relationship_type: string
  direction: string // upstream | downstream | support
  product_scope: string[]
  business_scope: string[]
  confidence_level: string
  status: string
}

export function getChatPartners(companyId: number) {
  return api.get(`/companies/${companyId}/chat-partners`)
}

export function getRelationships(companyId: number) {
  return api.get('/relationships', { params: { company_id: companyId } })
}

type PartnerChatPayload = { partner_company_id: number; query: string; scope: 'product' | 'business' }

export function partnerChat(
  companyId: number,
  payloadOrPartnerId: PartnerChatPayload | number,
  query?: string,
  scope: 'product' | 'business' = 'product',
) {
  const payload = typeof payloadOrPartnerId === 'number'
    ? { partner_company_id: payloadOrPartnerId, query: query || '', scope }
    : payloadOrPartnerId
  return api.post(`/companies/${companyId}/partner-chat`, payload)
}

// ============================================================
// 企业内部问答 (chat.router)
// ============================================================

export function chatAsk(companyId: number, query: string, language?: string) {
  return api.post('/chat/ask', { company_id: companyId, query, language })
}
