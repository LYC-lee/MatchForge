import { computed, ref, watch } from 'vue'
import { getEnterpriseContexts, type EnterpriseContextItem } from '@/api/enterprise'
import { useAuthStore } from '@/stores/auth'
import { DEFAULT_DEMO_COMPANY_ID, findDemoCompany } from '@/data/demoCompanies'

const storageKey = 'matchforge-current-enterprise-id'

function readInitialId() {
  const saved = Number(window.localStorage.getItem(storageKey))
  return Number.isFinite(saved) && saved > 0 ? saved : DEFAULT_DEMO_COMPANY_ID
}

const currentEnterpriseId = ref(readInitialId())
const companies = ref<EnterpriseContextItem[]>([])
const dataSource = ref<'api' | 'empty' | 'loading'>('loading')
let loaded = false

function emptyEnterprise(id: number): EnterpriseContextItem {
  const demo = findDemoCompany(id)
  return {
    company_id: id,
    company: {
      id,
      name: demo?.name || '绑定企业加载中...',
      name_en: null,
      name_alias: null,
      country: null,
      region: null,
      website: null,
      description: null,
    },
    segment_code: null,
    segment_name: demo?.segment_name || null,
    segment_name_en: null,
    chain_position: demo?.chain_position || null,
    role: demo?.role || null,
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
    emptyEnterprise(currentEnterpriseId.value)
  )
})

function setCurrentEnterprise(id: number) {
  currentEnterpriseId.value = id
  window.localStorage.setItem(storageKey, String(id))
}

export function useEnterpriseContext() {
  const auth = useAuthStore()
  const boundId = computed(() => auth.user?.company_id || readInitialId())

  if (currentEnterpriseId.value !== boundId.value) {
    setCurrentEnterprise(boundId.value)
  }

  watch(boundId, (id) => {
    if (id && currentEnterpriseId.value !== id) {
      setCurrentEnterprise(id)
    }
  })

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
