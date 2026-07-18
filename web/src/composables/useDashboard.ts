import { ref, watch, computed } from 'vue'
import {
  getDashboard,
  getCompanyOrders,
  getCompanyForecasts,
  type DashboardData,
  type DashboardOrder,
  type DashboardForecast,
  type DashboardShortage,
  type DashboardAction,
} from '@/api/enterprise'
import { getMockDashboard } from '@/mock/dashboardAdapter'
import { useEnterpriseContext } from '@/composables/useEnterpriseContext'
import { defaultEnterpriseId, getEnterpriseContext as getMockCtx } from '@/mock/enterpriseContext'
import { onDemoRefresh } from '@/composables/useDemoRefresh'
import { getDemoState, type DemoState, type DemoOrderItem, type DemoShortageItem } from '@/api/demo'
import { useAuthStore } from '@/stores/auth'

/** 风险等级排序辅助 (urgent > critical > high > medium > low) */
export function severityRank(severity: string): number {
  return { urgent: 5, critical: 4, high: 3, medium: 2, low: 1 }[severity] || 0
}

// ============================================================
// demo 沙盘数据 -> 驾驶舱类型映射 (仅 is_demo 模式启用)
// 负数 id 区分演示数据, 避免与基线业务表主键冲突。
// ============================================================

function mapDemoOrder(o: DemoOrderItem, companyId: number, idx: number): DashboardOrder {
  const synId = o.id ? -o.id : -(idx + 1)
  return {
    id: synId,
    company_id: companyId,
    product_id: o.product_id ?? 0,
    order_number: o.order_number,
    customer_company_id: o.customer_company_id ?? null,
    customer_name: o.customer_company_name || undefined,
    product_name: o.product_name,
    product_model: o.product_model,
    quantity: o.quantity,
    due_date: o.due_date ?? null,
    priority: o.priority,
    status: o.status,
    is_demo: true,
  }
}

function mapDemoShortage(s: DemoShortageItem, companyId: number, idx: number): DashboardShortage {
  return {
    id: -(idx + 1),
    company_id: companyId,
    product_id: s.product_id ?? null,
    product_name: s.product_name ?? null,
    part_number: s.part_number,
    part_name: s.part_name ?? null,
    category_name: s.category_name ?? null,
    shortage_type: s.shortage_type,
    required_qty: s.required_qty,
    available_qty: s.available_qty,
    shortage_qty: s.shortage_qty,
    safety_stock_qty: s.safety_stock_qty ?? null,
    unit: s.unit ?? null,
    is_critical: s.is_critical ?? false,
    severity: s.severity,
    status: 'open',
    preferred_supplier_company_id: s.preferred_supplier_company_id ?? null,
    preferred_supplier_name: s.preferred_supplier_name ?? null,
    relationship_missing: s.relationship_missing ?? false,
    affected_order_numbers: s.affected_order_numbers ?? [],
    affected_product_ids: s.affected_product_ids ?? [],
    is_demo: true,
  }
}

function mapDemoShortageToAction(s: DemoShortageItem): DashboardAction {
  const priority = s.severity === 'critical' ? 'urgent' : s.severity === 'high' ? 'high' : 'medium'
  return {
    action_type: 'demo_sourcing',
    category: 'sourcing',
    priority,
    severity: s.severity,
    title: `演示缺件采购: ${s.part_name || s.part_number}`,
    detail: `演示场景触发缺件 ${s.part_name || ''}(${s.part_number}) 缺口 ${s.shortage_qty}${s.unit || ''}，建议向直接关系供应商发起 RFQ 询价补货。`,
    part_number: s.part_number,
    product_id: s.product_id ?? null,
    suggested_supplier_company_id: s.preferred_supplier_company_id ?? null,
    suggested_supplier_name: s.preferred_supplier_name ?? null,
    relationship_missing: s.relationship_missing ?? false,
    shortage_id: null,
    is_demo: true,
  }
}

/**
 * 将 /demo/state 的演示增量合并进基线 dashboard 聚合对象 (原地 mutate)。
 *
 * - demo 订单置顶并入 orders_summary.items, 重算 total/active_count/active_total_quantity/by_status/by_priority。
 * - demo 缺件置顶并入 shortages.items (缺件风险卡片 + 缺件列表随之刷新)。
 * - 由 demo 缺件合成 sourcing 推荐动作, 置顶并入 recommended_actions.items。
 * - 仅 mutate 传入的 dash, 不触发任何基线写回。
 */
function mergeDemoIntoDashboard(dash: DashboardData, demo: DemoState, companyId: number): void {
  const demoOrders = demo.demo_orders || []
  const demoShortages = demo.demo_shortages || []

  // 1) 合并订单 + 重算统计
  if (demoOrders.length) {
    if (!dash.orders_summary) {
      dash.orders_summary = { total: 0, active_count: 0, active_total_quantity: 0, by_status: {}, by_priority: {}, items: [] }
    }
    const mappedOrders = demoOrders.map((o, i) => mapDemoOrder(o, companyId, i))
    dash.orders_summary.items = [...mappedOrders, ...(dash.orders_summary.items || [])]
    dash.orders_summary.total = (dash.orders_summary.total || 0) + (demo.demo_orders_total ?? demoOrders.length)
    dash.orders_summary.active_count = (dash.orders_summary.active_count || 0) + (demo.demo_orders_active_count ?? 0)
    dash.orders_summary.active_total_quantity = (dash.orders_summary.active_total_quantity || 0) + (demo.demo_orders_active_quantity ?? 0)
    const byStatus: Record<string, number> = { ...(dash.orders_summary.by_status || {}) }
    const byPriority: Record<string, number> = { ...(dash.orders_summary.by_priority || {}) }
    for (const o of demoOrders) {
      byStatus[o.status] = (byStatus[o.status] || 0) + 1
      byPriority[o.priority] = (byPriority[o.priority] || 0) + 1
    }
    dash.orders_summary.by_status = byStatus
    dash.orders_summary.by_priority = byPriority
  }

  // 2) 合并缺件 (全部 demo 缺件, 含 shortage + warning)
  if (demoShortages.length) {
    if (!dash.shortages) {
      dash.shortages = { company_id: companyId, items: [] }
    }
    const mappedShortages = demoShortages.map((s, i) => mapDemoShortage(s, companyId, i))
    dash.shortages.items = [...mappedShortages, ...(dash.shortages.items || [])]
  }

  // 3) 由 demo 缺件 (shortage 类型) 合成 sourcing 推荐动作
  const demoActions = demoShortages
    .filter((s) => s.shortage_type === 'shortage')
    .map((s) => mapDemoShortageToAction(s))
  if (demoActions.length) {
    if (!dash.recommended_actions) {
      dash.recommended_actions = { items: [] }
    }
    dash.recommended_actions.items = [...demoActions, ...(dash.recommended_actions.items || [])]
  }
}

/**
 * 经营驾驶舱数据 composable。
 *
 * 优先拉取后端 /companies/{id}/dashboard; 失败时降级到 mock (dashboardAdapter)。
 * 后端 dashboard 聚合接口的 orders_summary.items / forecast_summary.items 在
 * 某些版本为空数组, 因此额外并发拉 /orders 和 /forecasts 补全明细。
 */
export function useDashboard() {
  const { currentEnterpriseId } = useEnterpriseContext()
  const auth = useAuthStore()

  const dashboard = ref<DashboardData | null>(null)
  const orders = ref<DashboardOrder[]>([])
  const forecasts = ref<DashboardForecast[]>([])
  const loading = ref(true)
  const error = ref<string | null>(null)
  const dataSource = ref<'api' | 'mock' | 'loading'>('loading')

  async function fetchDashboard(companyId: number) {
    loading.value = true
    error.value = null
    dataSource.value = 'loading'

    try {
      const [dashRes, ordRes, fcRes] = await Promise.all([
        getDashboard(companyId),
        getCompanyOrders(companyId),
        getCompanyForecasts(companyId),
      ])
      const dash = dashRes.data as DashboardData
      // 补全订单/预测明细 (聚合接口 items 可能为空)
      if (dash.orders_summary && (!dash.orders_summary.items || dash.orders_summary.items.length === 0)) {
        dash.orders_summary.items = (ordRes.data?.items || []) as DashboardOrder[]
      }
      if (dash.forecast_summary && (!dash.forecast_summary.items || dash.forecast_summary.items.length === 0)) {
        dash.forecast_summary.items = (fcRes.data?.items || []) as DashboardForecast[]
      }

      // demo 模式: 合并 /demo/state 的演示增量 (订单/缺件/动作) 到驾驶舱。
      // 真实账号不进入此分支, 只看基线/业务数据; 演示数据不写回基线表。
      if (auth.user?.is_demo) {
        try {
          const demoRes = await getDemoState(companyId)
          if (demoRes.data) {
            mergeDemoIntoDashboard(dash, demoRes.data, companyId)
          }
        } catch (demoErr) {
          // demo state 拉取失败不阻断基线驾驶舱展示
          console.warn('[useDashboard] demo state merge skipped:', demoErr)
        }
      }

      orders.value = dash.orders_summary?.items || []
      forecasts.value = dash.forecast_summary?.items || []
      dashboard.value = dash
      dataSource.value = 'api'
    } catch (e: any) {
      // 降级到 mock
      error.value = e?.message || '后端不可用, 已降级到 mock 数据'
      const mockDash = getMockDashboard(companyId)
      // 如果 mock 也没有该企业, 用默认企业兜底
      if (!mockDash || mockDash.company.name === '加载中…') {
        dashboard.value = getMockDashboard(defaultEnterpriseId)
      } else {
        dashboard.value = mockDash
      }
      orders.value = dashboard.value.orders_summary?.items || []
      forecasts.value = dashboard.value.forecast_summary?.items || []
      dataSource.value = 'mock'
    } finally {
      loading.value = false
    }
  }

  watch(currentEnterpriseId, (id) => {
    if (id) fetchDashboard(id)
  }, { immediate: true })

  onDemoRefresh(() => fetchDashboard(currentEnterpriseId.value))

  /** 风险等级排序辅助 (critical > high > medium > low) -- 模块级导出版 */
  const severityRankFn = severityRank

  const topShortages = computed(() => {
    const items = dashboard.value?.shortages?.items || []
    return [...items].sort((a, b) => severityRank(b.severity) - severityRank(a.severity)).slice(0, 5)
  })

  const criticalShortages = computed(() =>
    (dashboard.value?.shortages?.items || []).filter((s) => s.shortage_type === 'shortage'),
  )

  const sortedActions = computed(() => {
    const items = dashboard.value?.recommended_actions?.items || []
    return [...items].sort((a, b) => severityRank(b.priority) - severityRank(a.priority))
  })

  return {
    dashboard,
    orders,
    forecasts,
    loading,
    error,
    dataSource,
    topShortages,
    criticalShortages,
    sortedActions,
    severityRank: severityRankFn,
    refresh: () => fetchDashboard(currentEnterpriseId.value),
  }
}

/** mock 兜底用的上下文 (供仍需要 mock relations 的旧视图引用)。 */
export function useMockInternalQuestions(companyId: number) {
  const ctx = getMockCtx(companyId)
  return ctx.internalQuestions
}
