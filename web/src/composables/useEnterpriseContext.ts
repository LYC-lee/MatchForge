import { computed, ref } from 'vue'
import { defaultEnterpriseId, enterpriseContexts, getEnterpriseContext } from '@/mock/enterpriseContext'

const storageKey = 'matchforge-current-enterprise-id'

function readInitialId() {
  const saved = Number(window.localStorage.getItem(storageKey))
  return Number.isFinite(saved) && saved > 0 ? saved : defaultEnterpriseId
}

const currentEnterpriseId = ref(readInitialId())

export function useEnterpriseContext() {
  const current = computed(() => getEnterpriseContext(currentEnterpriseId.value))
  const companies = computed(() => enterpriseContexts.map((item) => item.company))

  function setCurrentEnterprise(id: number) {
    currentEnterpriseId.value = id
    window.localStorage.setItem(storageKey, String(id))
  }

  return {
    companies,
    current,
    currentEnterpriseId,
    setCurrentEnterprise,
  }
}
