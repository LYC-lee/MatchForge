import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { streamProcure } from '@/api/procure'
import { getUserId, useHistory } from '@/composables/useHistory'
import type {
  AgentName,
  AgentState,
  Alternative,
  Citation,
  EntitiesSnapshot,
  LeadGrade,
  ProcureState,
  SessionDetail,
  SpecField,
  Supplier,
} from '@/types/procure'

type Phase = 'idle' | 'spec' | 'gating' | 'match' | 'done'

/**
 * 将后端返回的简单键值对格式转为前端 SpecConfirm 组件期望的 SpecField 格式。
 */
// 后端内部字段，不展示给用户
const INTERNAL_KEYS = new Set(['std_code', 'standard', '_mapped', '_phase', '_snapshot'])

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
  const leadGrade = ref<LeadGrade | null>(null)
  const errors = ref<string[]>([])

  /** C4 (#28): 最近一次 result 事件下发的实体快照, 下一轮请求时回传给后端做引用解析 */
  const entitiesSnapshot = ref<EntitiesSnapshot | null>(null)

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
  /** 手动 abort 后置位: 防御性忽略 abort 后到达的帧 (后端 #35 已知缺陷: 断连后仍可能 yield) */
  let aborted = false

  /**
   * token 事件过滤 (#29):
   * 真流式路径 (graph.py `astream_events`) 中, 所有 `on_chat_model_stream`
   * 都标记为 `agent: "chat"`; 但由于只有 chat_agent 开启 `streaming=True`
   * 并用 `astream`, 其他 Agent (parse/normalize 等 `ainvoke`) 不产生 token。
   * 防御: 一旦寻源结构化 Agent 已启动 (progress 出现), 说明本轮是寻源流程,
   * 忽略 chat 文本 token, 避免污染聊天气泡 / 结构化卡片。
   */
  const TEXT_TOKEN_AGENTS = new Set(['chat', 'rag_enrich'])
  function shouldAcceptChatToken(agent?: string) {
    if (aborted) return false
    if (agent && !TEXT_TOKEN_AGENTS.has(agent)) return false
    return !progress.value.some(
      (p) => !TEXT_TOKEN_AGENTS.has(p.agent) && !['supervisor', '__end__'].includes(p.agent),
    )
  }

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
    if (state.entities_snapshot) entitiesSnapshot.value = state.entities_snapshot
  }

  function reset() {
    controller?.abort()
    aborted = false
    threadId.value = ''
    resetTurnState()
    entitiesSnapshot.value = null
  }

  /** 每轮对话开始前的状态清理 (#28): 清空本轮流式/结果数据, 但保留会话标识与实体快照以支撑多轮追问 */
  function resetForTurn() {
    controller?.abort()
    aborted = false
    resetTurnState()
  }

  /** 单轮级别的状态重置 (threadId / entitiesSnapshot 之外的全部会话数据) */
  function resetTurnState() {
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
    // #28: 多轮对话 — 每轮只清本轮数据, 保留 threadId (同一会话延续) 与 entitiesSnapshot (引用解析回传)
    resetForTurn()
    rawQuery.value = query
    phase.value = 'spec'
    isStreaming.value = true
    streamProgress.value = '正在解析需求…'

    const userId = getUserId()

    controller = streamProcure(
      {
        query,
        phase: 'spec',
        user_id: userId,
        thread_id: threadId.value || undefined,
        snapshot: entitiesSnapshot.value || undefined,
      },
      {
      onStart: (tid, rid) => {
        threadId.value = tid
        if (rid) rfqId.value = rid
      },
      onToken: (text, agent) => {
        // chat 等文本 Agent 的流式 token (寻源 Agent 已启动时忽略,见 shouldAcceptChatToken)
        if (shouldAcceptChatToken(agent)) {
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
          if (aborted) return  // 忽略 abort 后到达的帧
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

  function markRfqSent() {
    rfqSent.value = true
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
          if (aborted) return  // 忽略 abort 后到达的帧
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
          if (aborted) return  // 忽略 abort 后到达的帧
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
    aborted = true
    controller?.abort()
    isStreaming.value = false
    streamProgress.value = ''
    chatStreamingText.value = ''  // 已流出的文本在 ChatView 消息里保留,缓冲区清空防止 watcher 再触发
  }

  function clearStreamError() {
    streamError.value = null
  }

  function clearStreamNotice() {
    streamNotice.value = null
  }

  /** 从历史会话恢复状态（不重新执行 SSE）; preload 可避免调用方重复请求详情接口 */
  async function loadFromSession(sessionId: string, preload?: SessionDetail | null): Promise<boolean> {
    // 使用 useHistory().getDetail() 优先 API、降级 localStorage
    const { getDetail } = useHistory()
    const detail = preload !== undefined ? preload : await getDetail(sessionId)
    if (!detail || !detail.state) return false

    const st = detail.state
    reset()
    threadId.value = detail.thread_id
    rawQuery.value = st.raw_query || detail.title
    phase.value = 'done'

    // C4: 恢复实体快照, 使历史会话中的追问仍可引用"第N个/刚才那个"
    if (st.entities_snapshot) {
      entitiesSnapshot.value = st.entities_snapshot
    }

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
    leadGrade,
    errors,
    isStreaming,
    streamProgress,
    matchError,
    streamError,
    streamNotice,
    selectedAlternative,
    selectedSuppliers,
    entitiesSnapshot,
    isVague,
    startProcure,
    confirmSpec,
    reset,
    resetForTurn,
    abort,
    clearStreamError,
    clearStreamNotice,
    toggleSupplier,
    selectAllSuppliers,
    deselectAllSuppliers,
    setRfqDoc,
    markRfqSent,
    regenerateRfq,
    retryMatch,
    applyState,
    loadFromSession,
    historyVersion,
  }
})