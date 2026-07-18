import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { streamProcure } from '@/api/procure'
import { createRfq, sendRfq, type RfqCreatePayload, type RfqCandidateDetail } from '@/api/enterprise'
import { useAuthStore } from '@/stores/auth'
import { getUserId, useHistory } from '@/composables/useHistory'
import type {
  AgentName,
  AgentState,
  Alternative,
  Citation,
  LeadGrade,
  ProcureState,
  SpecField,
  Supplier,
} from '@/types/procure'

type Phase = 'idle' | 'spec' | 'gating' | 'match' | 'done'

/**
 * 将后端返回的简单键值对格式转为前端 SpecConfirm 组件期望的 SpecField 格式。
 */
// 后端内部字段，不展示给用户
const INTERNAL_KEYS = new Set(['std_code', 'standard', '_mapped', '_phase'])

function toSpecFieldFormat(spec: Record<string, any> | null): Record<string, SpecField> | null {
  if (!spec) return null
  const result: Record<string, SpecField> = {}
  for (const [key, val] of Object.entries(spec)) {
    if (INTERNAL_KEYS.has(key)) continue  // 跳过内部字段
    if (typeof val === 'object' && val !== null && 'value' in val) {
      result[key] = val as SpecField
    } else {
      // C3: 不再写死 confidence,后端给了才保留(SpecField.confidence 可选透传)
      const strVal = val != null ? String(val) : ''
      result[key] = {
        value: strVal,
        missing: !strVal,
        editable: true,
      }
    }
  }
  return result
}

const AGENT_ORDER: AgentName[] = ['parse', 'normalize', 'alternatives', 'match', 'gen_rfq', 'grade']

export const useProcureStore = defineStore('procure', () => {
  const threadId = ref<string>('')
  const rfqId = ref<string | null>(null)
  const rawQuery = ref<string>('')
  const chatResponse = ref<string | null>(null)
  const chatStreamingText = ref<string>('')  // 流式输入的实时缓冲区
  /** 引用回显(C2): 当前会话累积的引用片段,按 agent 去重合并 */
  const chatCitations = ref<Citation[]>([])
  const phase = ref<Phase>('idle')
  const agents = ref<AgentState[]>(
    AGENT_ORDER.map((name) => ({ name, status: 'pending' as const })),
  )
  const parsedSpec = ref<Record<string, any> | null>(null)
  const normalizedSpec = ref<Record<string, any> | null>(null)
  const alternatives = ref<any[]>([])
  const matchedSuppliers = ref<any[]>([])
  const selectedSupplierIds = ref<Set<string>>(new Set())
  const rfqDoc = ref<string>('')
  const rfqSent = ref(false)
  /** 落库后的真实 RFQ 主键 (来自 RfqRecord.id); 未发送/发送失败为 null */
  const persistedRfqId = ref<number | null>(null)
  /** 落库后的真实 RFQ 编号 (RFQ-YYYY-NNNN); 用于 UI 展示替代内存 MF- ID */
  const persistedRfqNumber = ref<string | null>(null)
  /** 发送 RFQ 到后端的进行中状态 */
  const rfqSending = ref(false)
  /** 发送 RFQ 到后端的错误 (显式出口, 不静默) */
  const rfqSendError = ref<string | null>(null)
  const leadGrade = ref<LeadGrade | null>(null)
  const errors = ref<string[]>([])

  // ── 流式进度 / 错误状态 ──
  const isStreaming = ref(false)
  const streamProgress = ref('')
  const matchError = ref<string | null>(null)
  const progress = ref<{ agent: string; status: string }[]>([])
  /** 传输层错误（断流/网络异常/解析连续失败），agent 无关,驱动 UI 错误条 */
  const streamError = ref<string | null>(null)
  /** 非致命流警告（如个别 SSE 帧解析失败），驱动 UI 提示条 */
  const streamNotice = ref<string | null>(null)

  // ── 历史记录版本号（每次会话保存后自增，驱动侧边栏刷新）──
  const historyVersion = ref(0)

  // ── 兼容性状态 (同步自 selectedSupplierIds / alternatives) ──
  const selectedAlternative = ref<any | null>(null)
  const selectedSuppliers = ref<any[]>([])

  let controller: AbortController | null = null

  /** citation 事件按 agent 分桶,后到的同 agent 事件覆盖旧值 */
  const citationsByAgent: Record<string, Citation[]> = {}

  function onCitationEvent(agent: string, citations: Citation[]) {
    if (!agent || !Array.isArray(citations)) return
    citationsByAgent[agent] = citations
    chatCitations.value = Object.values(citationsByAgent).flat()
  }

  /** 信息不足: 无解析结果且无替代料 */
  const isVague = computed(
    () => errors.value.length > 0 && alternatives.value.length === 0 && !parsedSpec.value,
  )

  function setAgent(name: AgentName, status: AgentState['status'], message?: string) {
    const agent = agents.value.find((x) => x.name === name)
    if (!agent) return
    agent.status = status
    agent.message = message
    if (status === 'running') {
      agent.startedAt = Date.now()
      agent.endedAt = undefined
    }
    if (status === 'done' || status === 'error') {
      agent.endedAt = Date.now()
    }
  }

  function applyState(state: Partial<ProcureState>) {
    if (state.thread_id) threadId.value = state.thread_id
    if (state.raw_query !== undefined) rawQuery.value = state.raw_query
    if (state.parsed_spec !== undefined) {
      parsedSpec.value = toSpecFieldFormat(state.parsed_spec as Record<string, any>)
    }
    if (state.normalized_spec !== undefined) {
      normalizedSpec.value = toSpecFieldFormat(state.normalized_spec as Record<string, any>)
    }
    if (state.alternatives !== undefined) {
      alternatives.value = state.alternatives
      // 同步 selectedAlternative
      if (state.alternatives.length > 0 && !selectedAlternative.value) {
        const best = state.alternatives.find((a: any) => a.level === 'L1') || state.alternatives[0]
        selectedAlternative.value = best
      }
    }
    if (state.matched_suppliers !== undefined) {
      matchedSuppliers.value = state.matched_suppliers
      matchError.value = null
    }
    if (state.rfq_doc !== undefined && state.rfq_doc !== null) rfqDoc.value = state.rfq_doc
    if (state.rfq_id !== undefined) rfqId.value = state.rfq_id
    if (state.chat_response !== undefined) chatResponse.value = state.chat_response
    if (state.lead_grade !== undefined) leadGrade.value = state.lead_grade
    if (state.errors !== undefined) errors.value = state.errors
  }

  function reset() {
    controller?.abort()
    threadId.value = ''
    rfqId.value = null
    rawQuery.value = ''
    chatResponse.value = null
    chatStreamingText.value = ''
    chatCitations.value = []
    for (const k of Object.keys(citationsByAgent)) delete citationsByAgent[k]
    phase.value = 'idle'
    agents.value = AGENT_ORDER.map((name) => ({ name, status: 'pending' as const }))
    parsedSpec.value = null
    normalizedSpec.value = null
    alternatives.value = []
    matchedSuppliers.value = []
    selectedSupplierIds.value = new Set()
    rfqDoc.value = ''
    rfqSent.value = false
    persistedRfqId.value = null
    persistedRfqNumber.value = null
    rfqSending.value = false
    rfqSendError.value = null
    leadGrade.value = null
    errors.value = []
    isStreaming.value = false
    streamProgress.value = ''
    progress.value = []
    matchError.value = null
    streamError.value = null
    streamNotice.value = null
    selectedAlternative.value = null
    selectedSuppliers.value = []
  }

  /** 阶段1: 发起寻源, 跑 parse + normalize, 然后停在规格确认门控 */
  function startProcure(query: string) {
    reset()
    rawQuery.value = query
    phase.value = 'spec'
    isStreaming.value = true
    streamProgress.value = '正在解析需求…'

    const userId = getUserId()

    controller = streamProcure({ query, phase: 'spec', user_id: userId }, {
      onStart: (tid, rid) => {
        threadId.value = tid
        if (rid) rfqId.value = rid
      },
      onToken: (text, agent) => {
        // chat 等文本 Agent 的流式 token
        if (agent && chatStreamingText.value !== null) {
          chatStreamingText.value += text
        }
      },
      onCitation: onCitationEvent,
      onProgress: (agent, status, result) => {
        setAgent(agent, status)
        progress.value.push({ agent, status })
        // 后端 chat 智能体不在 AgentName 枚举内,按字符串比较
        const agentName = agent as string
        if (agentName === 'chat' && status === 'running') {
          chatStreamingText.value = ''  // 清空缓冲区，开始流式接收
        }
        if (agentName === 'chat' && status === 'done' && result) {
          chatResponse.value = typeof result === 'string' ? result : JSON.stringify(result)
          chatStreamingText.value = ''  // 流式结束，清空缓冲区
        }
        if (agent === 'parse' && status === 'running') {
          streamProgress.value = '正在解析需求…'
        }
        if (agent === 'normalize' && status === 'running') {
          streamProgress.value = '正在标准化规格…'
        }
        if (agent === 'parse' && status === 'done' && result) {
          parsedSpec.value = toSpecFieldFormat(result as Record<string, any>)
        }
        if (agent === 'normalize' && status === 'done' && result) {
          normalizedSpec.value = toSpecFieldFormat(result as Record<string, any>)
        }
      },
      onError: (agent, message) => {
        if (agent) setAgent(agent, 'error', message)
        if (!agent) streamError.value = message || '连接中断，请重试'
        errors.value.push(message)
        if (phase.value === 'spec') phase.value = 'done'
      },
      onParseError: () => {
        streamNotice.value = '部分服务数据无法解析，已自动跳过'
      },
      onResult: (state) => applyState(state),
      onEnd: () => {
        isStreaming.value = false
        streamProgress.value = ''
        if (phase.value === 'spec' && !errors.value.length) {
          phase.value = 'gating'
        } else if (phase.value === 'match') {
          phase.value = 'done'
        }
      },
    })
  }

  /** 阶段2: 用户确认规格后, 继续 alternatives + match + gen_rfq + grade */
  function confirmSpec(editedSpec: Record<string, SpecField>) {
    normalizedSpec.value = editedSpec
    phase.value = 'match'
    isStreaming.value = true
    streamProgress.value = '正在查找替代料…'
    const restAgents: AgentName[] = ['alternatives', 'match', 'gen_rfq', 'grade']
    restAgents.forEach((name) => setAgent(name, 'pending'))
    rfqDoc.value = ''
    matchError.value = null
    streamError.value = null
    streamNotice.value = null

    // 将 SpecField 格式转回后端期望的简单键值对
    const simpleSpec: Record<string, string> = {}
    for (const [k, v] of Object.entries(editedSpec)) {
      simpleSpec[k] = v.value
    }
    controller = streamProcure(
      { query: rawQuery.value, thread_id: threadId.value, confirmed_spec: simpleSpec, phase: 'match', user_id: getUserId() },
      {
        onStart: (tid, rid) => {
          threadId.value = tid
          if (rid) rfqId.value = rid
        },
        onProgress: (agent, status, result) => {
          setAgent(agent, status)

          // 流式进度提示
          if (agent === 'alternatives' && status === 'running') {
            streamProgress.value = '正在查找替代料…'
          }
          if (agent === 'match' && status === 'running') {
            streamProgress.value = '正在匹配供应商…'
          }
          if (agent === 'gen_rfq' && status === 'running') {
            streamProgress.value = '正在生成询价单…'
          }

          if (agent === 'alternatives' && status === 'done' && result) {
            alternatives.value = result as Alternative[]
            // 设置默认选中替代料
            if (Array.isArray(result) && result.length > 0 && !selectedAlternative.value) {
              const best = (result as Alternative[]).find((a) => a.level === 'L1') || (result as Alternative[])[0]
              selectedAlternative.value = best
            }
            streamProgress.value = `已找到 ${Array.isArray(result) ? result.length : 0} 个替代料，正在匹配供应商…`
          }
          if (agent === 'match' && status === 'done' && result) {
            matchedSuppliers.value = result as Supplier[]
            const count = Array.isArray(result) ? result.length : 0
            streamProgress.value = `已匹配 ${count} 家供应商，正在生成询价单…`
          }
        },
        onToken: (text) => {
          rfqDoc.value += text
        },
        onCitation: onCitationEvent,
        onError: (agent, message) => {
          if (agent) setAgent(agent, 'error', message)
          if (!agent) streamError.value = message || '连接中断，请重试'
          errors.value.push(message)
          if (agent === 'match') {
            matchError.value = `供应商匹配失败: ${message}`
          }
          if (agent === 'gen_rfq') {
            rfqDoc.value = `# RFQ 生成失败\n\n后端寻源服务暂时不可用，请稍后重试。\n\n错误信息: ${message}`
          }
        },
        onParseError: () => {
          streamNotice.value = '部分服务数据无法解析，已自动跳过'
        },
        onResult: (state) => applyState(state),
        onEnd: () => {
          isStreaming.value = false
          streamProgress.value = ''
          phase.value = 'done'
        },
      },
    )
  }

  // ── 供应商选择操作 ──
  function toggleSupplier(id: string) {
    const ids = new Set(selectedSupplierIds.value)
    if (ids.has(id)) {
      ids.delete(id)
    } else {
      ids.add(id)
    }
    selectedSupplierIds.value = ids
    syncSelectedSuppliers()
  }

  function selectAllSuppliers() {
    const ids = new Set<string>()
    matchedSuppliers.value.forEach((s) => ids.add(s.id))
    selectedSupplierIds.value = ids
    syncSelectedSuppliers()
  }

  function deselectAllSuppliers() {
    selectedSupplierIds.value = new Set()
    syncSelectedSuppliers()
  }

  function syncSelectedSuppliers() {
    selectedSuppliers.value = matchedSuppliers.value.filter((s) =>
      selectedSupplierIds.value.has(s.id),
    )
  }

  // ── RFQ 操作 ──
  function setRfqDoc(text: string) {
    rfqDoc.value = text
  }

  /** 从 normalizedSpec (SpecField 格式) 取字段原始值 */
  function specVal(key: string): string {
    const spec = normalizedSpec.value || parsedSpec.value
    if (!spec) return ''
    const f = spec[key]
    if (f == null) return ''
    if (typeof f === 'object' && 'value' in (f as any)) return String((f as any).value ?? '')
    return String(f)
  }

  /** 品类 -> 中文品名 (与后端 gen_rfq._CATEGORY_TO_NAME 对齐, 用于 RFQ title) */
  function categoryToName(category: string): string {
    const map: Record<string, string> = {
      mlcc: '多层陶瓷贴片电容(MLCC)',
      resistor: '贴片电阻',
      capacitor: '电容器',
      inductor: '电感器',
      ic: '集成电路',
      connector: '连接器',
      diode: '二极管',
      transistor: '三极管',
    }
    const k = (category || '').trim().toLowerCase()
    return map[k] || category || '电子元器件'
  }

  /**
   * 把 AI 寻源产物发送到真实后端, 创建 kb_rfqs 记录并发送给候选供应商。
   *
   * - 正式模式 (is_demo=false): 调 POST /rfqs + POST /rfqs/{id}/send,
   *   回填 persistedRfqId/Number, rfqSent=true。
   * - demo 模式 (is_demo=true): 仅翻本地 rfqSent flag, 不落库 (保持 demo 与 kb 表隔离)。
   * - 失败: 写 rfqSendError, 不翻 rfqSent, 不静默。
   */
  async function sendRfqToBackend() {
    rfqSendError.value = null
    const auth = useAuthStore()
    const isDemo = !!auth.user?.is_demo

    // demo 模式: 保持旧本地 flag 行为, 不接通真实闭环
    if (isDemo) {
      rfqSent.value = true
      return
    }

    // 取 buyer_company_id: 优先 auth.user.company_id, 后备从 localStorage 读当前企业
    let buyerCompanyId = auth.user?.company_id
    if (!buyerCompanyId) {
      const saved = Number(window.localStorage.getItem('matchforge-current-enterprise-id'))
      if (Number.isFinite(saved) && saved > 0) {
        buyerCompanyId = saved
      }
    }
    if (!buyerCompanyId) {
      rfqSendError.value = '当前账号未绑定企业, 无法创建 RFQ'
      return
    }

    rfqSending.value = true
    try {
      const partNumber = specVal('part_number')
      const category = specVal('category')
      const monthlyQty = parseInt(specVal('monthly_qty'), 10)
      const leadWeeks = parseInt(specVal('lead_time_weeks'), 10)

      // 候选供应商: 优先用户选中的, 否则用全部 matched; 携带 match_score/match_reason
      const pool = selectedSuppliers.value.length > 0 ? selectedSuppliers.value : matchedSuppliers.value
      const candidateDetails: RfqCandidateDetail[] = []
      for (const s of pool) {
        const sid = parseInt(s.id, 10)
        if (!Number.isFinite(sid)) continue
        const reason = [
          (s as any).brand_coverage ? `品牌覆盖:${(s as any).brand_coverage}` : '',
          (s as any).rag_insights ? `知识匹配:${String((s as any).rag_insights).slice(0, 80)}` : '',
          s.region ? `地区:${s.region}` : '',
        ].filter(Boolean).join(' | ')
        const detail: RfqCandidateDetail = {
          supplier_company_id: sid,
          match_score: s.match_score,
        }
        if (reason) detail.match_reason = reason
        candidateDetails.push(detail)
      }

      const payload: RfqCreatePayload = {
        buyer_company_id: buyerCompanyId,
        title: `${categoryToName(category)} 采购询价${partNumber ? ` - ${partNumber}` : ''}`,
        part_number: partNumber || undefined,
        part_name: categoryToName(category),
        quantity: Number.isFinite(monthlyQty) && monthlyQty > 0 ? monthlyQty : 1,
        unit: '个',
        lead_time_days: Number.isFinite(leadWeeks) && leadWeeks > 0 ? leadWeeks * 7 : undefined,
        accept_alternatives: alternatives.value.length > 0,
        scenario: 'sourcing',
        raw_query: rawQuery.value || undefined,
        candidate_details: candidateDetails.length > 0 ? candidateDetails : undefined,
        lead_grade: leadGrade.value ? { ...leadGrade.value } : undefined,
      }

      const createRes = await createRfq(payload)
      const rfq = createRes?.data?.rfq
      if (!rfq || !rfq.id) {
        throw new Error('后端未返回 RFQ 记录')
      }
      persistedRfqId.value = rfq.id
      persistedRfqNumber.value = rfq.rfq_number || null

      // 发送给候选供应商 (生成 supplier leads + 审核项)
      await sendRfq(rfq.id)
      rfqSent.value = true
    } catch (e: any) {
      rfqSendError.value =
        e?.response?.data?.detail || e?.message || 'RFQ 发送失败, 请稍后重试'
      // 不翻 rfqSent, 允许用户重试
    } finally {
      rfqSending.value = false
    }
  }

  /** 兼容旧调用: 标记已发送 (内部按模式分发) */
  function markRfqSent() {
    sendRfqToBackend()
  }

  function regenerateRfq() {
    // 重新触发 gen_rfq：通过 SSE 重新生成
    if (!normalizedSpec.value) return
    rfqDoc.value = ''
    isStreaming.value = true
    streamProgress.value = '正在重新生成询价单…'
    streamError.value = null
    streamNotice.value = null
    setAgent('gen_rfq', 'running')

    controller = streamProcure(
      { thread_id: threadId.value, confirmed_spec: normalizedSpec.value as Record<string, SpecField>, phase: 'match', user_id: getUserId() },
      {
        onStart: () => {},
        onProgress: (agent, status, result) => {
          setAgent(agent, status)
          if (agent === 'gen_rfq' && status === 'done' && result) {
            rfqDoc.value = result as string
          }
        },
        onToken: (text) => {
          rfqDoc.value += text
        },
        onError: (agent, message) => {
          if (agent) setAgent(agent, 'error', message)
          if (!agent) streamError.value = message || '连接中断，请重试'
          if (agent === 'gen_rfq') {
            rfqDoc.value = `# RFQ 生成失败\n\n错误信息: ${message}`
          }
        },
        onParseError: () => {
          streamNotice.value = '部分服务数据无法解析，已自动跳过'
        },
        onResult: (state) => applyState(state),
        onEnd: () => {
          isStreaming.value = false
          streamProgress.value = ''
        },
      },
    )
  }

  // ── 重试匹配 ──
  function retryMatch() {
    if (!normalizedSpec.value) return
    matchError.value = null
    isStreaming.value = true
    streamProgress.value = '正在重新匹配供应商…'
    streamError.value = null
    streamNotice.value = null
    setAgent('match', 'running')
    setAgent('gen_rfq', 'pending')
    setAgent('grade', 'pending')

    controller = streamProcure(
      { thread_id: threadId.value, confirmed_spec: normalizedSpec.value as Record<string, SpecField>, phase: 'match', user_id: getUserId() },
      {
        onStart: () => {},
        onProgress: (agent, status, result) => {
          setAgent(agent, status)
          if (agent === 'match' && status === 'done' && result) {
            matchedSuppliers.value = result as Supplier[]
            matchError.value = null
            streamProgress.value = '正在生成询价单…'
          }
          if (agent === 'gen_rfq' && status === 'done' && result) {
            // result 可能是 rfq_doc string
          }
        },
        onToken: (text) => {
          rfqDoc.value += text
        },
        onError: (agent, message) => {
          if (agent) setAgent(agent, 'error', message)
          if (!agent) streamError.value = message || '连接中断，请重试'
          if (agent === 'match') {
            matchError.value = `供应商匹配失败: ${message}`
          }
        },
        onParseError: () => {
          streamNotice.value = '部分服务数据无法解析，已自动跳过'
        },
        onResult: (state) => applyState(state),
        onEnd: () => {
          isStreaming.value = false
          streamProgress.value = ''
        },
      },
    )
  }

  function abort() {
    controller?.abort()
    isStreaming.value = false
    streamProgress.value = ''
  }

  function clearStreamError() {
    streamError.value = null
  }

  function clearStreamNotice() {
    streamNotice.value = null
  }

  /** 从历史会话恢复状态（不重新执行 SSE） */
  async function loadFromSession(sessionId: string): Promise<boolean> {
    // 使用 useHistory().getDetail() 优先 API、降级 localStorage
    const { getDetail } = useHistory()
    const detail = await getDetail(sessionId)
    if (!detail || !detail.state) return false

    const st = detail.state
    reset()
    threadId.value = detail.thread_id
    rawQuery.value = st.raw_query || detail.title
    phase.value = 'done'

    // 恢复解析结果
    if (st.parsed_spec) {
      parsedSpec.value = toSpecFieldFormat(st.parsed_spec as Record<string, any>)
    }
    if (st.normalized_spec) {
      normalizedSpec.value = toSpecFieldFormat(st.normalized_spec as Record<string, any>)
    }

    // 恢复替代料
    if (st.alternatives?.length) {
      alternatives.value = st.alternatives
      const best = st.alternatives.find((a: any) => a.level === 'L1') || st.alternatives[0]
      selectedAlternative.value = best
    }

    // 恢复供应商
    if (st.matched_suppliers?.length) {
      matchedSuppliers.value = st.matched_suppliers
    }

    // 恢复 RFQ
    if (st.rfq_doc) {
      rfqDoc.value = st.rfq_doc
    }
    if (st.rfq_id) {
      rfqId.value = st.rfq_id
    }

    // 恢复聊天回复
    if (st.chat_response) {
      chatResponse.value = st.chat_response
    }

    // 恢复线索分级
    if (st.lead_grade) {
      leadGrade.value = st.lead_grade
    }

    // 恢复错误
    if (st.errors?.length) {
      errors.value = st.errors
    }

    // 标记所有 Agent 为已完成
    agents.value.forEach((a) => {
      a.status = 'done'
      a.endedAt = Date.now()
    })

    return true
  }

  return {
    threadId,
    rfqId,
    rawQuery,
    chatResponse,
    chatStreamingText,
    chatCitations,
    phase,
    agents,
    progress,
    parsedSpec,
    normalizedSpec,
    alternatives,
    matchedSuppliers,
    selectedSupplierIds,
    rfqDoc,
    rfqSent,
    persistedRfqId,
    persistedRfqNumber,
    rfqSending,
    rfqSendError,
    leadGrade,
    errors,
    isStreaming,
    streamProgress,
    matchError,
    streamError,
    streamNotice,
    selectedAlternative,
    selectedSuppliers,
    isVague,
    startProcure,
    confirmSpec,
    reset,
    abort,
    clearStreamError,
    clearStreamNotice,
    toggleSupplier,
    selectAllSuppliers,
    deselectAllSuppliers,
    setRfqDoc,
    markRfqSent,
    sendRfqToBackend,
    regenerateRfq,
    retryMatch,
    applyState,
    loadFromSession,
    historyVersion,
  }
})