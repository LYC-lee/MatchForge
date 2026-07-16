/**
 * Mock → DashboardData 适配器
 *
 * 将 web/src/mock/enterpriseContext.ts 中的 mock EnterpriseContext
 * 转换为与后端 /companies/{id}/dashboard 一致的 DashboardData 结构。
 *
 * 用途: 当后端不可用时, 前端仍可用 mock 数据渲染驾驶舱, 保持 UI 不白屏。
 * 边界: 此文件仅做数据形状转换, 不包含业务逻辑; 后续移除 mock 时直接删除即可。
 */
import type {
  DashboardData,
  DashboardProduct,
  DashboardOrder,
  DashboardForecast,
  DashboardShortage,
  DashboardAction,
  ChatPartnerSummary,
} from '@/api/enterprise'
import { enterpriseContexts, getEnterpriseContext, type EnterpriseContext } from '@/mock/enterpriseContext'

const severityMap: Record<string, string> = { 高: 'critical', 中: 'medium', 低: 'low' }
const priorityMap: Record<string, string> = { 高: 'urgent', 中: 'medium', 低: 'low' }

function toProducts(ctx: EnterpriseContext): DashboardProduct[] {
  return ctx.products.map((p, idx) => ({
    id: 9000 + idx + 1,
    company_id: ctx.company.id,
    product_name: p.name,
    product_model: p.model,
    product_type: ctx.company.segment,
    description: p.status,
    monthly_capacity: Number(String(p.capacity).replace(/[^\d]/g, '')) || null,
    unit: '台',
    status: p.risk === '高' ? 'at_risk' : 'active',
  }))
}

function toOrders(ctx: EnterpriseContext): DashboardOrder[] {
  return ctx.demands.map((d, idx) => ({
    id: idx + 1,
    company_id: ctx.company.id,
    product_id: 9000 + idx + 1,
    order_number: d.id,
    customer_company_id: null,
    customer_name: d.customer,
    product_name: d.product,
    product_model: d.product,
    quantity: d.quantity,
    due_date: d.due,
    priority: d.type === '紧急' ? 'urgent' : d.risk === '高' ? 'high' : 'normal',
    status: d.status,
  }))
}

function toForecasts(ctx: EnterpriseContext): DashboardForecast[] {
  return ctx.demands
    .filter((d) => d.type === '预测')
    .map((d, idx) => ({
      id: idx + 1,
      company_id: ctx.company.id,
      product_id: 9000 + idx + 1,
      product_name: d.product,
      product_model: d.product,
      forecast_period: d.due,
      forecast_quantity: d.quantity,
      confidence: 0.7,
      source_type: 'manual',
    }))
}

function toShortages(ctx: EnterpriseContext): DashboardShortage[] {
  return ctx.shortages.map((s, idx) => ({
    id: idx + 1,
    company_id: ctx.company.id,
    product_id: 9000 + idx + 1,
    product_name: s.affectedProducts[0] || null,
    part_number: s.code,
    part_name: s.part,
    category_name: null,
    shortage_type: s.risk === '高' ? 'shortage' : 'warning',
    required_qty: s.gap,
    available_qty: 0,
    shortage_qty: s.gap,
    safety_stock_qty: null,
    unit: '个',
    is_critical: s.risk === '高',
    severity: severityMap[s.risk] || 'low',
    status: 'open',
    preferred_supplier_company_id: null,
    preferred_supplier_name: s.suppliers[0] || null,
    relationship_missing: false,
    affected_order_numbers: s.affectedOrders,
    affected_product_ids: [],
  }))
}

function toActions(ctx: EnterpriseContext): DashboardAction[] {
  const categoryMap: Record<string, string> = { 采购: 'sourcing', 生产: 'production', 销售: 'sales', 协同: 'collaboration' }
  return ctx.actions.map((a) => ({
    action_type: a.category === '采购' ? 'contact_supplier' : a.category === '生产' ? 'adjust_schedule' : 'sync_downstream',
    category: categoryMap[a.category] || 'sourcing',
    priority: priorityMap[a.priority] || 'medium',
    severity: severityMap[a.priority] || 'low',
    title: a.title,
    detail: a.detail,
    part_number: null,
    product_id: null,
    suggested_supplier_company_id: null,
    suggested_supplier_name: a.target || null,
    relationship_missing: false,
    shortage_id: null,
  }))
}

function toPartnerSummaries(ctx: EnterpriseContext): ChatPartnerSummary[] {
  return ctx.relations.map((r) => ({
    company_id: r.id,
    company_name: r.name,
    direction: r.direction === '上游' ? 'upstream' : 'downstream',
    segment_name: r.segment,
    relationship_type: r.direction === '上游' ? 'supply' : 'channel',
  }))
}

/** 将单个 mock EnterpriseContext 转为 DashboardData。 */
export function mockToDashboard(ctx: EnterpriseContext): DashboardData {
  const products = toProducts(ctx)
  const orders = toOrders(ctx)
  const forecasts = toForecasts(ctx)
  const shortages = toShortages(ctx)
  const actions = toActions(ctx)
  const upstream = toPartnerSummaries(ctx).filter((p) => p.direction === 'upstream')
  const downstream = toPartnerSummaries(ctx).filter((p) => p.direction === 'downstream')

  return {
    company_id: ctx.company.id,
    company: {
      id: ctx.company.id,
      name: ctx.company.name,
      name_en: null,
      name_alias: null,
      country: '中国',
      region: ctx.company.location,
      website: null,
      description: ctx.company.note,
      segment_code: null,
      segment_name: ctx.company.segment,
      chain_position: null,
      role: ctx.company.role,
      knowledge_status: 'ready',
    },
    products_summary: { total: products.length, active_count: products.length, items: products },
    orders_summary: {
      total: orders.length,
      active_count: orders.filter((o) => o.status !== 'completed').length,
      active_total_quantity: orders.reduce((sum, o) => sum + o.quantity, 0),
      by_status: {},
      by_priority: {},
      items: orders,
    },
    forecast_summary: {
      total: forecasts.length,
      total_forecast_quantity: forecasts.reduce((sum, f) => sum + f.forecast_quantity, 0),
      items: forecasts,
    },
    shortages: { company_id: ctx.company.id, items: shortages },
    recommended_actions: { items: actions },
    upstream_summary: { total: upstream.length, items: upstream },
    downstream_summary: { total: downstream.length, items: downstream },
    support_summary: { total: 0, items: [] },
    chat_partners_summary: { total: upstream.length + downstream.length, items: [...upstream, ...downstream] },
  }
}

/** 获取 mock 企业的 DashboardData (按 id)。 */
export function getMockDashboard(companyId: number): DashboardData {
  const ctx = getEnterpriseContext(companyId)
  return mockToDashboard(ctx)
}

/** 全部 mock 企业摘要 (供企业切换器降级使用)。 */
export function getMockEnterpriseList() {
  return enterpriseContexts.map((ctx) => ({
    company_id: ctx.company.id,
    company: {
      id: ctx.company.id,
      name: ctx.company.name,
      name_en: null,
      name_alias: null,
      country: '中国',
      region: ctx.company.location,
      website: null,
      description: ctx.company.note,
    },
    segment_code: null,
    segment_name: ctx.company.segment,
    segment_name_en: null,
    chain_position: null,
    role: ctx.company.role,
    product_count: ctx.products.length,
    order_count: ctx.demands.length,
    shortage_count: ctx.shortages.length,
    upstream_count: ctx.relations.filter((r) => r.direction === '上游').length,
    downstream_count: ctx.relations.filter((r) => r.direction === '下游').length,
    knowledge_status: 'ready',
  }))
}
