import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { streamProcure } from '@/api/procure'
import { buildRfqTemplate } from '@/mock/data'
import type {
  AgentName,
  AgentState,
  Alternative,
  LeadGrade,
  ProcureState,
  SpecField,
  Supplier,
} from '@/types/procure'

type Phase = 'idle' | 'spec' | 'gating' | 'match' | 'done'

const AGENT_ORDER: AgentName[] = ['parse', 'normalize', 'alternatives', 'match', 'gen_rfq', 'grade']

export const useProcureStore = defineStore('procure', () => {
  const threadId = ref<string>('')
  const rfqId = ref<string | null>(null)
  const rawQuery = ref<string>('')
  const phase = ref<Phase>('idle')
  const agents = ref<AgentState[]>(
    AGENT_ORDER.map((name) => ({ name, status: 'pending' as const })),
  )
  const parsedSpec = ref<Record<string, SpecField> | null>(null)
  const normalizedSpec = ref<Record<string, SpecField> | null>(null)
  const alternatives = ref<Alternative[]>([])
  const matchedSuppliers = ref<Supplier[]>([])
  const selectedSupplierIds = ref<Set<string>>(new Set())
  const rfqDoc = ref<string>('')
  const rfqSent = ref(false)
  const leadGrade = ref<LeadGrade | null>(null)
  const errors = ref<string[]>([])
  let controller: AbortController | null = null

  /** 信息不足:无解析结果且无替代料 */
  const isVague = computed(
    () => errors.value.length > 0 && alternatives.value.length === 0 && !parsedSpec.value,
  )

  function setAgent(name: AgentName, status: AgentState['status'], message?: string) {
    const a = agents.value.find((x) => x.name === name)
    if (!a) return
    a.status = status
    a.message = message
    if (status === 'running') a.startedAt = Date.now()
    if (status === 'done' || status === 'error') a.endedAt = Date.now()
  }

  function applyResult(state: Partial<ProcureState>) {
    if (state.thread_id) threadId.value = state.thread_id
    if (state.raw_query !== undefined) rawQuery.value = state.raw_query
    if (state.parsed_spec !== undefined) parsedSpec.value = state.parsed_spec
    if (state.normalized_spec !== undefined) normalizedSpec.value = state.normalized_spec
    if (state.alternatives !== undefined) alternatives.value = state.alternatives
    if (state.matched_suppliers !== undefined) matchedSuppliers.value = state.matched_suppliers
    if (state.rfq_doc !== undefined && state.rfq_doc !== null) rfqDoc.value = state.rfq_doc
    if (state.rfq_id !== undefined) rfqId.value = state.rfq_id
    if (state.lead_grade !== undefined) leadGrade.value = state.lead_grade
    if (state.errors !== undefined) errors.value = state.errors
  }

  function reset() {
    controller?.abort()
    threadId.value = ''
    rfqId.value = null
    rawQuery.value = ''
    phase.value = 'idle'
    agents.value = AGENT_ORDER.map((name) => ({ name, status: 'pending' as const }))
    parsedSpec.value = null
    normalizedSpec.value = null
    alternatives.value = []
    matchedSuppliers.value = []
    selectedSupplierIds.value = new Set()
    rfqDoc.value = ''
    rfqSent.value = false
    leadGrade.value = null
    errors.value = []
  }

  /** 阶段1:发起寻源,跑 parse + normalize,然后停在规格确认门控 */
  function startProcure(query: string) {
    reset()
    rawQuery.value = query
    phase.value = 'spec'

    controller = streamProcure({ query, phase: 'spec' }, {
      onStart: (tid) => { threadId.value = tid },
      onProgress: (agent, status, result) => {
        setAgent(agent, status)
        if (agent === 'parse' && status === 'done' && result) {
          parsedSpec.value = result as Record<string, SpecField>
        }
        if (agent === 'normalize' && status === 'done' && result) {
          normalizedSpec.value = result as Record<string, SpecField>
        }
      },
      onError: (agent, message) => {
        if (agent) setAgent(agent, 'error', message)
        errors.value.push(message)
        if (phase.value === 'spec') phase.value = 'done'
      },
      onResult: (state) => applyResult(state),
      onEnd: () => {
        if (phase.value === 'spec' && !errors.value.length) {
          phase.value = 'gating'
        } else if (phase.value === 'match') {
          phase.value = 'done'
        }
      },
    })
  }

  /** 阶段2:用户确认规格后,继续 alternatives + match + gen_rfq + grade */
  function confirmSpec(editedSpec: Record<string, SpecField>) {
    normalizedSpec.value = editedSpec
    phase.value = 'match'
    const restAgents: AgentName[] = ['alternatives', 'match', 'gen_rfq', 'grade']
    restAgents.forEach((n) => setAgent(n, 'pending'))
    rfqDoc.value = ''

    controller = streamProcure(
      { thread_id: threadId.value, confirmed_spec: editedSpec, phase: 'match' },
      {
        onStart: (tid) => { threadId.value = tid },
        onProgress: (agent, status, result) => {
          setAgent(agent, status)
          if (agent === 'alternatives' && status === 'done' && result) {
            alternatives.value = result as Alternative[]
          }
          if (agent === 'match' && status === 'done' && result) {
            matchedSuppliers.value = result as Supplier[]
          }
        },
        onToken: (text) => { rfqDoc.value += text },
        onError: (agent, message) => {
          if (agent) setAgent(agent, 'error', message)
          errors.value.push(message)
          // gen_rfq 失败 -> 固定模板兜底
          if (agent === 'gen_rfq') {
            rfqDoc.value = buildRfqTemplate({
              rawQuery: rawQuery.value,
              spec: editedSpec,
              alternatives: alternatives.value,
              suppliers: matchedSuppliers.value,
            })
          }
        },
        onResult: (state) => applyResult(state),
        onEnd: () => { phase.value = 'done' },
      },
    )
  }

  function toggleSupplier(id: string) {
    const s = new Set(selectedSupplierIds.value)
    if (s.has(id)) {
      s.delete(id)
    } else {
      s.add(id)
    }
    selectedSupplierIds.value = s
  }

  function setRfqDoc(text: string) { rfqDoc.value = text }
  function markRfqSent() { rfqSent.value = true }
  function abort() { controller?.abort() }

  return {
    threadId, rfqId, rawQuery, phase, agents,
    parsedSpec, normalizedSpec, alternatives, matchedSuppliers,
    selectedSupplierIds, rfqDoc, rfqSent, leadGrade, errors,
    isVague,
    startProcure, confirmSpec, reset, abort,
    toggleSupplier, setRfqDoc, markRfqSent,
  }
})
