import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Alternative, ProcureState, Supplier } from '@/api'

export const useProcureStore = defineStore('procure', () => {
  // ---- 寻源状态 ----
  const threadId = ref<string | null>(null)
  const rawQuery = ref('')
  const parsedSpec = ref<Record<string, any> | null>(null)
  const normalizedSpec = ref<Record<string, any> | null>(null)
  const alternatives = ref<Alternative[]>([])
  const matchedSuppliers = ref<Supplier[]>([])
  const rfqDoc = ref<string | null>(null)
  const rfqId = ref<string | null>(null)
  const leadGrade = ref<ProcureState['lead_grade']>(null)
  const errors = ref<string[]>([])

  // 流式进度
  const progress = ref<{ agent: string; status: string }[]>([])
  const isStreaming = ref(false)

  // 选中的替代
  const selectedAlternative = ref<Alternative | null>(null)

  // 选中的供应商
  const selectedSuppliers = ref<Supplier[]>([])

  function reset() {
    threadId.value = null
    rawQuery.value = ''
    parsedSpec.value = null
    normalizedSpec.value = null
    alternatives.value = []
    matchedSuppliers.value = []
    rfqDoc.value = null
    rfqId.value = null
    leadGrade.value = null
    errors.value = []
    progress.value = []
    isStreaming.value = false
    selectedAlternative.value = null
    selectedSuppliers.value = []
  }

  function applyState(state: Partial<ProcureState>) {
    if (state.thread_id) threadId.value = state.thread_id
    if (state.raw_query) rawQuery.value = state.raw_query
    if (state.parsed_spec) parsedSpec.value = state.parsed_spec
    if (state.normalized_spec) normalizedSpec.value = state.normalized_spec
    if (state.alternatives) alternatives.value = state.alternatives
    if (state.matched_suppliers) matchedSuppliers.value = state.matched_suppliers
    if (state.rfq_doc) rfqDoc.value = state.rfq_doc
    if (state.rfq_id) rfqId.value = state.rfq_id
    if (state.lead_grade) leadGrade.value = state.lead_grade
    if (state.errors) errors.value = state.errors
  }

  return {
    threadId,
    rawQuery,
    parsedSpec,
    normalizedSpec,
    alternatives,
    matchedSuppliers,
    rfqDoc,
    rfqId,
    leadGrade,
    errors,
    progress,
    isStreaming,
    selectedAlternative,
    selectedSuppliers,
    reset,
    applyState,
  }
})