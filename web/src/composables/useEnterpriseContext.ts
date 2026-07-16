import { computed, ref } from 'vue'
import { getEnterpriseContexts, type EnterpriseContextItem } from '@/api/enterprise'

const storageKey = 'matchforge-current-enterprise-id'
const DEMO_COMPANY_ID = 9003

function readInitialId() {
  const saved = Number(window.localStorage.getItem(storageKey))
  return Number.isFinite(saved) && saved > 0 ? saved : DEMO_COMPANY_ID
}

const currentEnterpriseId = ref(readInitialId())
const companies = ref<EnterpriseContextItem[]>([])
const dataSource = ref<'api' | 'empty' | 'loading'>('loading')
let loaded = false

function emptyEnterprise(id: number): EnterpriseContextItem {
  return {
    company_id: id,
    company: {
      id,
      name: '加载中...',
      name_en: null,
      name_alias: null,
      country: null,
      region: null,
      website: null,
      description: null,
    },
    segment_code: null,
    segment_name: null,
    segment_name_en: null,
    chain_position: null,
    role: null,
    product_count: 0,
    order_count: 0,
    shortage_count: 0,
    upstream_count: 0,
    downstream_count: 0,
    knowledge_status: 'unknown',
  }
}

async function loadCompanies() {
  if (loaded) return
  dataSource.value = 'loading'
  try {
    const res = await getEnterpriseContexts()
    const items = res.data?.items as EnterpriseContextItem[] | undefined
    companies.value = items || []
    dataSource.value = companies.value.length > 0 ? 'api' : 'empty'

    const validIds = new Set(companies.value.map((c) => c.company_id))
    if (companies.value.length > 0 && !validIds.has(currentEnterpriseId.value)) {
      setCurrentEnterprise(companies.value[0].company_id)
    }
  } catch {
    companies.value = []
    dataSource.value = 'empty'
  } finally {
    loaded = true
  }
}

const current = computed<EnterpriseContextItem>(() => {
  return (
    companies.value.find((c) => c.company_id === currentEnterpriseId.value) ||
    companies.value[0] ||
    emptyEnterprise(currentEnterpriseId.value)
  )
})

function setCurrentEnterprise(id: number) {
  currentEnterpriseId.value = id
  window.localStorage.setItem(storageKey, String(id))
}

export function useEnterpriseContext() {
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
