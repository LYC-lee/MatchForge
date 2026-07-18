import { ref, computed, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useEnterpriseContext } from '@/composables/useEnterpriseContext'
import { onDemoRefresh, emitDemoRefresh } from '@/composables/useDemoRefresh'
import {
  getDemoRfqs,
  getDemoSupplierView,
  getDemoQuoteComparison,
  getDemoAuditQueue,
  generateDemoRfq,
  simulateDemoQuotes,
  executeDemoReplenishment,
  recalculateDemoShortages,
  type DemoRfqRecord,
  type DemoSupplierView,
  type DemoQuoteComparison,
  type DemoAuditQueue,
  type DemoActionResult,
  type DemoRfqParams,
} from '@/api/demo'

/**
 * 演示沙盘 composable: 统一 demo 模式判定 + demo 数据拉取 + demo 动作执行。
 *
 * - isDemo: 当前是否为演示沙盘模式 (auth.user.is_demo)。
 * - demoRfqs: 当前企业 (买方) 的 demo RFQ 列表。
 * - supplierView: 当前企业作为供应商收到的 demo RFQ + 自己的报价。
 * - auditQueue: 演示只读审核队列。
 * - 动作 (generateRfq/simulateQuotes/executeReplenishment/recalculateShortages):
 *   执行后自动 emitDemoRefresh, 触发全局驾驶舱/列表重拉。
 * - lastResult: 最近一次动作结果 (供 UI 展示 no_direct_supplier / RFQ 编号等)。
 */
export function useDemo() {
  const auth = useAuthStore()
  const { currentEnterpriseId } = useEnterpriseContext()

  const isDemo = computed(() => !!auth.user?.is_demo)

  const demoRfqs = ref<DemoRfqRecord[]>([])
  const supplierView = ref<DemoSupplierView | null>(null)
  const auditQueue = ref<DemoAuditQueue | null>(null)
  const comparison = ref<DemoQuoteComparison | null>(null)
  const loadingRfqs = ref(false)
  const loadingSupplier = ref(false)
  const loadingAudit = ref(false)
  const lastResult = ref<DemoActionResult | null>(null)
  const actionError = ref<string | null>(null)
  const running = ref('')

  async function fetchDemoRfqs(status?: string) {
    if (!isDemo.value) return
    loadingRfqs.value = true
    try {
      const res = await getDemoRfqs(currentEnterpriseId.value, status)
      demoRfqs.value = res.data.items
    } catch {
      demoRfqs.value = []
    } finally {
      loadingRfqs.value = false
    }
  }

  async function fetchSupplierView() {
    if (!isDemo.value) return
    loadingSupplier.value = true
    try {
      const res = await getDemoSupplierView(currentEnterpriseId.value)
      supplierView.value = res.data
    } catch {
      supplierView.value = null
    } finally {
      loadingSupplier.value = false
    }
  }

  async function fetchAuditQueue() {
    if (!isDemo.value) return
    loadingAudit.value = true
    try {
      const res = await getDemoAuditQueue()
      auditQueue.value = res.data
    } catch {
      auditQueue.value = null
    } finally {
      loadingAudit.value = false
    }
  }

  async function loadComparison(rfqId: number) {
    if (!isDemo.value) return
    try {
      const res = await getDemoQuoteComparison(rfqId, currentEnterpriseId.value)
      comparison.value = res.data
    } catch {
      comparison.value = null
    }
  }

  /** 执行 demo 动作的通用包装: 写 lastResult/actionError, 成功后 emitDemoRefresh。 */
  async function runAction<T extends DemoActionResult>(
    key: string,
    runner: () => Promise<{ data: T }>,
    opts?: { refresh?: 'rfqs' | 'supplier' | 'audit' | 'all' },
  ): Promise<T | null> {
    actionError.value = null
    running.value = key
    try {
      const res = await runner()
      lastResult.value = res.data
      emitDemoRefresh()
      const refresh = opts?.refresh || 'all'
      if (refresh === 'all' || refresh === 'rfqs') await fetchDemoRfqs()
      if (refresh === 'all' || refresh === 'supplier') await fetchSupplierView()
      if (refresh === 'all' || refresh === 'audit') await fetchAuditQueue()
      return res.data
    } catch (e: any) {
      actionError.value = e?.response?.data?.detail || e?.message || '演示动作执行失败'
      lastResult.value = null
      return null
    } finally {
      running.value = ''
    }
  }

  async function generateRfq(params?: DemoRfqParams) {
    return runAction('rfq', () => generateDemoRfq(currentEnterpriseId.value, params))
  }

  async function simulateQuotes(rfqId?: number) {
    return runAction('quotes', () => simulateDemoQuotes(currentEnterpriseId.value, rfqId))
  }

  async function executeReplenishment(opts?: { rfq_id?: number; supplier_company_id?: number }) {
    return runAction('replenish', () => executeDemoReplenishment(currentEnterpriseId.value, opts))
  }

  async function recalculateShortages() {
    return runAction('shortages', () => recalculateDemoShortages(currentEnterpriseId.value))
  }

  function clearLastResult() {
    lastResult.value = null
    actionError.value = null
  }

  // demo 模式下企业切换自动重拉
  watch(currentEnterpriseId, (id) => {
    if (id && isDemo.value) {
      fetchDemoRfqs()
      fetchSupplierView()
      fetchAuditQueue()
    }
  }, { immediate: true })

  // 全局 demo 刷新 (控制台动作后触发)
  onDemoRefresh(() => {
    if (isDemo.value) {
      fetchDemoRfqs()
      fetchSupplierView()
      fetchAuditQueue()
    }
  })

  return {
    isDemo,
    currentEnterpriseId,
    demoRfqs,
    supplierView,
    auditQueue,
    comparison,
    loadingRfqs,
    loadingSupplier,
    loadingAudit,
    lastResult,
    actionError,
    running,
    fetchDemoRfqs,
    fetchSupplierView,
    fetchAuditQueue,
    loadComparison,
    generateRfq,
    simulateQuotes,
    executeReplenishment,
    recalculateShortages,
    clearLastResult,
  }
}
