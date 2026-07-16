import { ref, watch } from 'vue'
import {
  listCompanyRfqs,
  createRfq,
  sendRfq,
  getQuoteComparison,
  type RfqRecord,
  type QuotationRecord,
} from '@/api/enterprise'
import { useEnterpriseContext } from '@/composables/useEnterpriseContext'
import { onDemoRefresh } from '@/composables/useDemoRefresh'

/**
 * RFQ 闭环 composable: 当前企业的 RFQ 列表 + 创建 + 发送 + 报价对比。
 *
 * 优先真实接口; 失败时列表置空并记录 error (不阻断页面, 用户仍可看缺件)。
 */
export function useRfq() {
  const { currentEnterpriseId } = useEnterpriseContext()

  const rfqs = ref<RfqRecord[]>([])
  const loading = ref(true)
  const error = ref<string | null>(null)
  const comparison = ref<{ rfq_number: string; items: QuotationRecord[] } | null>(null)

  async function fetchRfqs(companyId: number) {
    loading.value = true
    error.value = null
    try {
      const res = await listCompanyRfqs(companyId)
      rfqs.value = (res.data?.items || []) as RfqRecord[]
    } catch (e: any) {
      error.value = e?.message || 'RFQ 接口不可用'
      rfqs.value = []
    } finally {
      loading.value = false
    }
  }

  watch(currentEnterpriseId, (id) => {
    if (id) fetchRfqs(id)
  }, { immediate: true })

  onDemoRefresh(() => fetchRfqs(currentEnterpriseId.value))

  async function create(payload: Parameters<typeof createRfq>[0]) {
    const res = await createRfq(payload)
    await fetchRfqs(currentEnterpriseId.value)
    return res.data
  }

  async function send(rfqId: number, supplierIds?: number[]) {
    const res = await sendRfq(rfqId, supplierIds)
    await fetchRfqs(currentEnterpriseId.value)
    return res.data
  }

  async function loadComparison(rfqId: number) {
    try {
      const res = await getQuoteComparison(rfqId)
      comparison.value = {
        rfq_number: res.data.rfq_number,
        items: res.data.items as QuotationRecord[],
      }
    } catch {
      comparison.value = null
    }
  }

  return {
    rfqs,
    loading,
    error,
    comparison,
    create,
    send,
    loadComparison,
    refresh: () => fetchRfqs(currentEnterpriseId.value),
  }
}
