import { computed, ref } from 'vue'
import { getEnterpriseContexts, type EnterpriseContextItem } from '@/api/enterprise'
import { getMockEnterpriseList } from '@/mock/dashboardAdapter'

const storageKey = 'matchforge-current-enterprise-id'

/** 推荐演示企业: 9003 鼎云整机 (后端种子链路中游, 有完整缺件+RFQ 闭环数据)。 */
const DEMO_COMPANY_ID = 9003

function readInitialId() {
  const saved = Number(window.localStorage.getItem(storageKey))
  return Number.isFinite(saved) && saved > 0 ? saved : DEMO_COMPANY_ID
}

const currentEnterpriseId = ref(readInitialId())
const companies = ref<EnterpriseContextItem[]>([])
const dataSource = ref<'api' | 'mock' | 'loading'>('loading')
let loaded = false

async function loadCompanies() {
  if (loaded) return
  dataSource.value = 'loading'
  try {
    const res = await getEnterpriseContexts()
    const items = res.data?.items as EnterpriseContextItem[] | undefined
    if (items && items.length > 0) {
      companies.value = items
      dataSource.value = 'api'
    } else {
      companies.value = getMockEnterpriseList()
      dataSource.value = 'mock'
    }
  } catch {
    companies.value = getMockEnterpriseList()
    dataSource.value = 'mock'
  } finally {
    loaded = true
  }
}

/** 当前选中的企业摘要 (从已加载列表中查找, 找不到时返回兜底)。 */
const current = computed<EnterpriseContextItem>(() => {
  const found = companies.value.find((c) => c.company_id === currentEnterpriseId.value)
  if (found) return found
  // 列表未加载完成或 id 不在列表中: 返回一个最小兜底对象, 避免渲染崩溃
  return companies.value[0] || {
    company_id: currentEnterpriseId.value,
    company: { id: currentEnterpriseId.value, name: '加载中…', name_en: null, name_alias: null, country: null, region: null, website: null, description: null },
    segment_code: null, segment_name: null, segment_name_en: null, chain_position: null, role: null,
    product_count: 0, order_count: 0, shortage_count: 0, upstream_count: 0, downstream_count: 0, knowledge_status: 'unknown',
  }
})

export function useEnterpriseContext() {
  function setCurrentEnterprise(id: number) {
    currentEnterpriseId.value = id
    window.localStorage.setItem(storageKey, String(id))
  }

  // 首次调用时触发加载 (不阻塞, 视图自行 watch current)
  loadCompanies()

  return {
    companies,
    current,
    currentEnterpriseId,
    setCurrentEnterprise,
    dataSource,
    reloadCompanies: () => {
      loaded = false
      return loadCompanies()
    },
  }
}
