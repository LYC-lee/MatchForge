import { ref, watch, computed } from 'vue'
import {
  getDashboard,
  getCompanyOrders,
  getCompanyForecasts,
  type DashboardData,
  type DashboardOrder,
  type DashboardForecast,
} from '@/api/enterprise'
import { getMockDashboard } from '@/mock/dashboardAdapter'
import { useEnterpriseContext } from '@/composables/useEnterpriseContext'
import { defaultEnterpriseId, getEnterpriseContext as getMockCtx } from '@/mock/enterpriseContext'
import { onDemoRefresh } from '@/composables/useDemoRefresh'

/** 风险等级排序辅助 (critical > high > medium > low) */
export function severityRank(severity: string): number {
  return { critical: 4, high: 3, medium: 2, low: 1 }[severity] || 0
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
