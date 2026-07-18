import api from './index'

export interface DemoEvent {
  id?: number | string
  event_id?: number | string
  scenario_id?: string
  company_id?: number
  company_name?: string
  affected_company_id?: number
  affected_company_name?: string
  action_type?: string
  event_type?: string
  summary?: string
  result_summary?: string
  message?: string
  created_at?: string
  timestamp?: string
}

/** 演示订单明细 (后端 _compute_company_state.demo_orders 项) */
export interface DemoOrderItem {
  id?: number
  order_number: string
  product_id?: number
  product_name?: string
  product_model?: string
  quantity: number
  priority: string
  status: string
  customer_company_id?: number | null
  customer_company_name?: string | null
  due_date?: string | null
  unit?: string | null
  created_at?: string | null
}

/** 演示缺件明细 (后端 _demo_shortages 项, 字段与 DashboardShortage 对齐) */
export interface DemoShortageItem {
  part_number: string
  part_name?: string | null
  category_name?: string | null
  shortage_type: string // shortage | warning
  required_qty: number
  available_qty: number
  shortage_qty: number
  safety_stock_qty?: number | null
  unit?: string | null
  is_critical?: boolean
  severity: string // critical | high | medium | low
  preferred_supplier_company_id?: number | null
  preferred_supplier_name?: string | null
  relationship_missing?: boolean
  product_id?: number | null
  product_name?: string | null
  affected_order_numbers?: string[]
  affected_product_ids?: number[]
}

export interface DemoRfqItem {
  rfq_number: string
  part_name?: string
  quantity: number
  status: string
  candidate_count?: number
}

/** demo RFQ 完整记录 (GET /demo/rfqs 项) */
export interface DemoRfqRecord {
  id: number
  scenario_id?: string
  rfq_number: string
  company_id: number
  title?: string
  part_number?: string
  part_name?: string
  quantity: number
  unit?: string
  target_price?: number | null
  lead_time_days?: number | null
  accept_alternatives?: boolean
  scenario?: string
  status: string
  candidates?: DemoRfqCandidate[]
  selected_supplier_company_id?: number | null
  created_at?: string | null
}

export interface DemoRfqCandidate {
  supplier_company_id: number
  supplier_name?: string
  direction?: string
  segment_code?: string
  match_score?: number
  match_reason?: string
  status?: string
}

/** demo 报价记录 */
export interface DemoQuotationRecord {
  id: number
  rfq_id: number
  supplier_company_id: number
  supplier_name?: string
  part_number?: string
  unit_price: number
  currency?: string
  moq?: number | null
  lead_time_days?: number | null
  stock_qty?: number | null
  is_in_stock?: boolean
  note?: string
  created_at?: string | null
  rank?: number
  is_lowest?: boolean
  meets_target?: boolean | null
  delta_vs_target?: number | null
}

/** 报价对比视图 */
export interface DemoQuoteComparison {
  rfq_id: number
  rfq_number: string
  target_price?: number | null
  quantity: number
  quote_count: number
  lowest_price?: number | null
  items: DemoQuotationRecord[]
}

/** 供应商视角 RFQ 项 (GET /demo/supplier-view) */
export interface DemoSupplierRfqItem {
  rfq_id: number
  rfq_number: string
  title?: string
  buyer_company_id: number
  buyer_name?: string
  part_number?: string
  part_name?: string
  quantity: number
  unit?: string
  target_price?: number | null
  lead_time_days?: number | null
  accept_alternatives?: boolean
  rfq_status: string
  selected_supplier_company_id?: number | null
  is_selected?: boolean
  my_match_score?: number
  my_match_reason?: string
  my_quote?: DemoQuotationRecord | null
  created_at?: string | null
}

export interface DemoSupplierView {
  scenario_id?: string
  supplier_company_id: number
  supplier_name?: string
  total_rfqs: number
  items: DemoSupplierRfqItem[]
  events?: DemoEvent[]
}

/** 审核队列项 (GET /demo/audit-queue) */
export interface DemoAuditItem {
  audit_id: string
  item_type: 'no_direct_supplier' | 'quotation_anomaly' | string
  title: string
  detail?: string
  company_id?: number
  company_name?: string
  severity?: string
  status: string
  payload?: Record<string, unknown>
  created_at?: string | null
}

export interface DemoAuditQueue {
  scenario_id?: string
  company_id?: number | null
  total: number
  pending: number
  items: DemoAuditItem[]
}

export interface DemoInventoryItem {
  part_number: string
  part_name?: string
  category_name?: string | null
  baseline_on_hand: number
  consumed_qty: number
  replenished_qty: number
  available_qty: number
  safety_stock_qty?: number
  unit?: string
}

export interface DemoDirectPartner {
  company_id: number
  company_name: string
  direction: string // supplier | customer | support
  role?: string | null
}

export interface DemoState {
  scenario_id?: string
  scenario_name?: string
  scenario_status?: string
  company_id?: number
  company_name?: string
  is_primary?: boolean
  role?: string
  chain_position?: string
  products_total?: number
  baseline_inventory_total?: number
  demo_orders_total?: number
  demo_orders_active_count?: number
  demo_orders_active_quantity?: number
  demo_orders?: DemoOrderItem[]
  demo_inventory_overrides_total?: number
  demo_inventory?: DemoInventoryItem[]
  demo_shortages_total?: number
  demo_shortages?: DemoShortageItem[]
  demo_rfqs_total?: number
  demo_rfqs?: DemoRfqItem[]
  direct_partners?: DemoDirectPartner[]
  events?: DemoEvent[]
  recent_events?: DemoEvent[]
  [key: string]: unknown
}

export interface DemoActionResult {
  ok?: boolean
  message?: string
  summary?: string
  state?: DemoState
  events?: DemoEvent[]
  [key: string]: unknown
}

export function getDemoState(companyId?: number) {
  return api.get<DemoState>('/demo/state', { params: companyId ? { company_id: companyId } : undefined })
}

export function getDemoEvents(companyId?: number) {
  return api.get<{ items?: DemoEvent[]; events?: DemoEvent[] } | DemoEvent[]>('/demo/events', {
    params: companyId ? { company_id: companyId } : undefined,
  })
}

export function resetDemoScenario(companyId?: number) {
  return api.post<DemoActionResult>('/demo/scenarios/reset', companyId ? { company_id: companyId } : undefined)
}

/** demo RFQ 列表 (买方视角) */
export function getDemoRfqs(companyId: number, status?: string) {
  return api.get<{ items: DemoRfqRecord[]; total: number }>('/demo/rfqs', {
    params: { company_id: companyId, ...(status ? { status } : {}) },
  })
}

/** demo 报价对比 */
export function getDemoQuoteComparison(rfqId: number, companyId: number) {
  return api.get<DemoQuoteComparison>(`/demo/rfqs/${rfqId}/quote-comparison`, {
    params: { company_id: companyId },
  })
}

/** 供应商视角: 收到的 demo RFQ + 自己的报价 + 事件 */
export function getDemoSupplierView(companyId: number) {
  return api.get<DemoSupplierView>('/demo/supplier-view', {
    params: { company_id: companyId },
  })
}

/** 演示只读审核队列 */
export function getDemoAuditQueue(companyId?: number) {
  return api.get<DemoAuditQueue>('/demo/audit-queue', {
    params: companyId ? { company_id: companyId } : undefined,
  })
}

export interface DemoRfqParams {
  part_number?: string
  shortage_index?: number
  quantity?: number
  target_price?: number
  lead_time_days?: number
}

export function generateDemoOrders(companyId: number, opts?: { product_id?: number; quantity?: number; priority?: string }) {
  return api.post<DemoActionResult>('/demo/actions/generate-orders', {
    company_id: companyId,
    ...(opts?.product_id ? { product_id: opts.product_id } : {}),
    ...(opts?.quantity ? { quantity: opts.quantity } : {}),
    priority: opts?.priority || 'normal',
  })
}

export function consumeDemoInventory(companyId: number, opts?: { part_number?: string; quantity?: number }) {
  return api.post<DemoActionResult>('/demo/actions/consume-inventory', {
    company_id: companyId,
    ...(opts?.part_number ? { part_number: opts.part_number } : {}),
    ...(opts?.quantity ? { quantity: opts.quantity } : {}),
  })
}

export function recalculateDemoShortages(companyId: number) {
  return api.post<DemoActionResult>('/demo/actions/recalculate-shortages', { company_id: companyId })
}

export function generateDemoRfq(companyId: number, params?: DemoRfqParams) {
  return api.post<DemoActionResult>('/demo/actions/generate-rfq', {
    company_id: companyId,
    ...(params || {}),
  })
}

export function simulateDemoQuotes(companyId: number, rfqId?: number) {
  return api.post<DemoActionResult>('/demo/actions/simulate-quotes', {
    company_id: companyId,
    ...(rfqId ? { rfq_id: rfqId } : {}),
  })
}

export function executeDemoReplenishment(companyId: number, opts?: { rfq_id?: number; supplier_company_id?: number }) {
  return api.post<DemoActionResult>('/demo/actions/execute-replenishment', {
    company_id: companyId,
    ...(opts || {}),
  })
}

export function selectDemoAlternative(companyId: number, opts?: { part_number?: string; alternative_supplier_company_id?: number; quantity?: number }) {
  return api.post<DemoActionResult>('/demo/actions/select-alternative', {
    company_id: companyId,
    ...(opts || {}),
  })
}
