import { computed } from 'vue'
import { useEnterpriseContext } from './useEnterpriseContext'

export function useIsLogistics() {
  const { current } = useEnterpriseContext()
  const isLogistics = computed(() => {
    const seg = current.value?.segment_name || ''
    return seg.includes('物流') || seg.includes('服务') || current.value?.company_id === 9004
  })
  return { isLogistics }
}
