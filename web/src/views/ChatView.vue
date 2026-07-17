<script setup lang="ts">
import { ref, nextTick, watch, onUnmounted, computed } from 'vue'
import { useProcureStore } from '@/stores/procure'
import { saveToLocal, loadLocalMessages, useHistory } from '@/composables/useHistory'
import type { SpecField, Alternative, Supplier, LeadGrade } from '@/types/procure'
import ChatMessage, { type ChatMessageData, type TurnPayload } from '@/components/chat/ChatMessage.vue'
import SpecConfirm from '@/components/procure/SpecConfirm.vue'
import AlternativesList from '@/components/procure/AlternativesList.vue'
import SuppliersMatch from '@/components/procure/SuppliersMatch.vue'
import RfqEditor from '@/components/procure/RfqEditor.vue'
import Tag from '@/components/ui/Tag.vue'
import SessionHistoryPanel from '@/components/procure/SessionHistoryPanel.vue'
import AgentTimeline from '@/components/procure/AgentTimeline.vue'

const store = useProcureStore()

// ── 历史记录侧边栏 ──
const showHistory = ref(false)

// ── 消息 ──
const messages = ref<ChatMessageData[]>([])
const inputText = ref('')
const isProcessing = ref(false)
const chatContainer = ref<HTMLElement | null>(null)
let msgId = 0

/**
 * 当前活跃轮次 id (#28)。
 * 每次发送/重试自增; 仅 turnId 与之一致且未冻结的消息可交互、从 store 实时取数,
 * 历史轮次的消息一律从各自 payload 冻结渲染 —— 发新消息不再清空历史渲染状态。
 */
const activeTurnId = ref(0)

/** 历史会话恢复期间置位: 抑制 phase watcher, 避免 loadFromSession 触发"done"重复加卡片 */
const restoringSession = ref(false)

function uid() { return `m-${++msgId}-${Date.now()}` }
function scrollDown() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

const deepCopy = <T,>(v: T): T => JSON.parse(JSON.stringify(v))

// ── 添加消息 ──
function addMsg(role: ChatMessageData['role'], content: string, opts?: Partial<ChatMessageData>) {
  const msg: ChatMessageData = {
    id: uid(),
    role,
    content,
    timestamp: Date.now(),
    turnId: activeTurnId.value,
    ...opts,
  }
  messages.value.push(msg)
  scrollDown()
  return msg
}

/** 是否当前活跃轮的消息(可交互、卡片从 store 实时取数) */
function isLiveMsg(msg: ChatMessageData) {
  return !msg.frozen && msg.turnId === activeTurnId.value
}

// ── 卡片取数: 冻结消息读 payload, 活跃消息读 store ──
function specFor(msg: ChatMessageData): Record<string, SpecField> | null {
  return (msg.frozen ? msg.payload?.normalizedSpec ?? null : store.normalizedSpec) as Record<string, SpecField> | null
}
function alternativesFor(msg: ChatMessageData): Alternative[] {
  return (msg.frozen ? msg.payload?.alternatives ?? [] : store.alternatives) as Alternative[]
}
function originalPartFor(msg: ChatMessageData): string {
  if (msg.frozen) return msg.payload?.originalPart ?? ''
  return ((store.parsedSpec as any)?.['型号']?.value as string) || ''
}
function originalBrandFor(msg: ChatMessageData): string {
  if (msg.frozen) return msg.payload?.originalBrand ?? ''
  return ((store.parsedSpec as any)?.['品牌']?.value as string) || ''
}
function suppliersFor(msg: ChatMessageData): Supplier[] {
  return (msg.frozen ? msg.payload?.matchedSuppliers ?? [] : store.matchedSuppliers) as Supplier[]
}
function selectedIdsFor(msg: ChatMessageData): Set<string> {
  return msg.frozen ? new Set(msg.payload?.selectedSupplierIds ?? []) : store.selectedSupplierIds
}
function rfqDocFor(msg: ChatMessageData): string {
  return msg.frozen ? msg.payload?.rfqDoc ?? '' : store.rfqDoc
}
function rfqIdFor(msg: ChatMessageData): string | null {
  return msg.frozen ? msg.payload?.rfqId ?? null : store.rfqId
}
function rfqSentFor(msg: ChatMessageData): boolean {
  return msg.frozen ? !!msg.payload?.rfqSent : store.rfqSent
}
function rfqStreaming(msg: ChatMessageData): boolean {
  return isLiveMsg(msg) && store.agents.find((a) => a.name === 'gen_rfq')?.status === 'running'
}
function gradeFor(msg: ChatMessageData): LeadGrade | null {
  return msg.frozen ? msg.payload?.leadGrade ?? null : store.leadGrade
}
function timelineAgents(msg: ChatMessageData) {
  return msg.payload?.agents ?? []
}
function timelineDoneCount(msg: ChatMessageData) {
  return timelineAgents(msg).filter((a) => a.status === 'done').length
}

// ── 进度占位文案(沉淀/停止时识别并清除) ──
const PROGRESS_PLACEHOLDERS = [
  '思考中…', '⋯',
  '正在识别型号与参数…', '正在标准化规格…', '正在查询替代料…',
  '正在匹配供应商…', '正在生成询价单…', '正在评估线索…',
]

// ── 卡片数据快照 ──
/** 按消息的结果类型, 从 store 快照一份 payload(不改变冻结状态) */
function snapshotPayload(msg: ChatMessageData): TurnPayload {
  const payload: TurnPayload = { ...(msg.payload ?? {}) }
  switch (msg.resultType) {
    case 'spec':
      payload.normalizedSpec = deepCopy(store.normalizedSpec)
      payload.parsedSpec = deepCopy(store.parsedSpec)
      break
    case 'alternatives':
      payload.alternatives = deepCopy(store.alternatives)
      payload.originalPart = originalPartFor(msg)
      payload.originalBrand = originalBrandFor(msg)
      break
    case 'suppliers':
      payload.matchedSuppliers = deepCopy(store.matchedSuppliers)
      payload.selectedSupplierIds = [...store.selectedSupplierIds]
      break
    case 'rfq':
      payload.rfqDoc = store.rfqDoc
      payload.rfqId = store.rfqId
      payload.rfqSent = store.rfqSent
      payload.normalizedSpec = deepCopy(store.normalizedSpec)
      payload.alternatives = deepCopy(store.alternatives)
      payload.matchedSuppliers = deepCopy(store.matchedSuppliers)
      payload.selectedSupplierIds = [...store.selectedSupplierIds]
      break
    case 'grade':
      payload.leadGrade = deepCopy(store.leadGrade)
      break
  }
  return payload
}

/** 冻结一条消息: 快照数据进 payload, 之后只读渲染, 不再跟随 store */
function freezeMsg(msg: ChatMessageData) {
  if (msg.frozen) return
  msg.payload = snapshotPayload(msg)
  msg.frozen = true
}

/** 为当前轮活跃的结果消息快照 payload(不冻结), 供 localStorage 持久化重建 */
function captureLivePayloads() {
  for (const m of messages.value) {
    if (m.frozen || m.turnId !== activeTurnId.value) continue
    if (!m.resultType || m.resultType === 'error' || m.resultType === 'progress') continue
    m.payload = snapshotPayload(m)
  }
}

/** 新一轮开始前: 冻结上一轮所有可交互消息, 卡片随消息各自沉淀 (#28, 替代 store.reset) */
function freezeCurrentTurn() {
  for (const m of messages.value) {
    if (m.turnId !== activeTurnId.value || m.frozen) continue
    if (m.streaming) m.streaming = false
    sedimentProgressMsg(m)
    freezeMsg(m)
  }
  gatingGuard = false
}

// ── 过程沉淀 (#28): 生成完成后把 Agent 时间线冻结进消息, 默认折叠可展开回看 ──
function sedimentProgressMsg(msg: ChatMessageData | undefined) {
  if (!msg || msg.resultType !== 'progress') return
  msg.streaming = false
  msg.payload = {
    ...(msg.payload ?? {}),
    agents: deepCopy(store.agents),
    alternativesCount: store.alternatives.length,
    suppliersCount: store.matchedSuppliers.length,
  }
  const text = msg.content.trim()
  if (!text || PROGRESS_PLACEHOLDERS.includes(text)) msg.content = ''
  msg.resultType = undefined
  msg.frozen = true
}

/** 终结最后一条流式消息并沉淀其时间线 */
function finalizeLastMsg() {
  const last = messages.value[messages.value.length - 1]
  if (!last) return
  if (last.streaming) last.streaming = false
  sedimentProgressMsg(last)
}

/** 仅清除流式标记(不沉淀), 用于兜底 watcher */
function finalizeStreamingFlag() {
  const last = messages.value[messages.value.length - 1]
  if (last && last.streaming) {
    last.streaming = false
  }
}

// ── 发送 ──
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

function send() {
  const q = inputText.value.trim()
  if (!q || isProcessing.value) return
  inputText.value = ''

  // #28: 冻结上一轮(卡片/时间线沉淀到各自消息), 不再 store.reset()
  freezeCurrentTurn()
  activeTurnId.value++

  // 用户消息
  addMsg('user', q)

  // 处理中
  isProcessing.value = true

  // AI 占位 → 启动
  addMsg('assistant', '思考中…', { streaming: true })
  store.startProcure(q)
}

// ── 新建对话：清空当前会话，回到初始状态 ──
function newChat() {
  store.abort()
  store.reset()  // 全量重置: 新会话新 threadId, 实体快照一并清空
  messages.value = []
  isProcessing.value = false
  inputText.value = ''
  // 滚动到顶部
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = 0
    }
  })
}

// ── 停止生成: 中断 SSE,输入框恢复可用 ──
function stopSending() {
  const last = messages.value[messages.value.length - 1]
  store.abort()
  if (last && last.role === 'assistant') {
    if (last.streaming) last.streaming = false
    const text = last.content.trim()
    sedimentProgressMsg(last)  // 已执行的部分沉淀为可回看时间线
    // 占位/进度文案被中断后没有实际内容,替换为停止标记;已流出的部分文本保留
    if (!text || PROGRESS_PLACEHOLDERS.includes(text)) {
      last.content = '已停止生成。'
      last.resultType = undefined
      last.citations = undefined  // abort 后 citation 帧若到达,不再挂到停止标记上
    }
  }
  isProcessing.value = false
}

// ── 以同一用户输入重新发起（重试 / 重新生成共用）──
function reissue(query: string) {
  if (isProcessing.value) return
  freezeCurrentTurn()
  activeTurnId.value++
  isProcessing.value = true
  addMsg('assistant', '思考中…', { streaming: true })
  store.startProcure(query)
}

// ── 错误重试: 重发最后一条用户消息 ──
function retryLast() {
  const lastUser = [...messages.value].reverse().find((m) => m.role === 'user')
  if (lastUser) reissue(lastUser.content)
}

// ── 重新生成: 找到该助手消息之前最近的一条用户输入,重新发起 ──
function regenerate(msgId: string) {
  const idx = messages.value.findIndex((m) => m.id === msgId)
  if (idx < 0) return
  const userMsg = [...messages.value.slice(0, idx)].reverse().find((m) => m.role === 'user')
  if (userMsg) reissue(userMsg.content)
}

// ── 进度 → 更新最后一条 AI 消息 ──
function updateProgressText(label: string) {
  const last = messages.value[messages.value.length - 1]
  if (last && last.role === 'assistant' && last.streaming) {
    last.content = label
    scrollDown()
  }
}

// ── 流式 token → 实时更新最后一条 AI 消息 ──
watch(() => store.chatStreamingText, (text) => {
  if (!text) return
  const last = messages.value[messages.value.length - 1]
  // 仅更新仍处于流式状态的 AI 消息: 结构化卡片消息 (SpecConfirm/RfqEditor 等)
  // streaming=false, token 流不会影响它们;abort 后 finalize 同样置 false,天然忽略迟到帧
  if (last && last.role === 'assistant' && last.streaming) {
    last.content = text
    scrollDown()
  }
})

// ── 引用回显(C2): citation 事件 → 挂到当前(最后一条) AI 消息 ──
watch(() => store.chatCitations, (cits) => {
  if (!cits.length) return
  const last = messages.value[messages.value.length - 1]
  if (last && last.role === 'assistant') {
    last.citations = cits
    scrollDown()
  }
}, { deep: true })

// ── 将最后一条 AI 进度消息替换为错误消息（SSE 流失败或解析失败时调用）──
function replaceProgressWithError(errMsg: string) {
  const last = messages.value[messages.value.length - 1]
  if (last && last.role === 'assistant') {
    last.streaming = false
    last.content = errMsg
    last.resultType = 'error'
  }
}

// ── 将最后一条 AI 消息替换为聊天回复（闲聊时调用，不显示 AgentTimeline）──
function showChatResponse(text: string) {
  const last = messages.value[messages.value.length - 1]
  if (last && last.role === 'assistant') {
    last.streaming = false
    last.content = text
    last.resultType = undefined  // 移除 resultType，AgentTimeline 不会显示
  }
}

// ── 本地持久化: 状态快照 + 可重建的多轮消息列表 ──
function serializeMessages() {
  return deepCopy(messages.value.map((m) => ({ ...m, streaming: false })))
}

function persistLocal() {
  saveToLocal({
    id: store.threadId,
    thread_id: store.threadId,
    raw_query: store.rawQuery,
    created_at: new Date().toISOString(),
    rfq_sent: store.rfqSent,
    state: {
      thread_id: store.threadId,
      raw_query: store.rawQuery,
      parsed_spec: store.parsedSpec,
      normalized_spec: store.normalizedSpec,
      alternatives: store.alternatives,
      matched_suppliers: store.matchedSuppliers,
      rfq_doc: store.rfqDoc,
      rfq_id: store.rfqId,
      lead_grade: store.leadGrade,
      errors: store.errors,
      entities_snapshot: store.entitiesSnapshot,  // C4: 恢复会话后追问仍可引用
    },
    messages: serializeMessages(),
  })
  // 触发历史侧边栏刷新
  store.historyVersion++
}

// ── 监听 store 阶段变化 ──
watch(() => store.phase, (phase) => {
  if (restoringSession.value) return  // 历史会话恢复触发的 phase 变化不产出新消息

  if (phase === 'gating') {
    // parse + normalize 完成: 沉淀本轮时间线
    finalizeLastMsg()
    isProcessing.value = false

    // 如果是 chat 回复（非寻源内容），直接展示聊天回复，不显示 AgentTimeline
    if (store.chatResponse) {
      showChatResponse(store.chatResponse)
      return
    }

    if (!store.parsedSpec || store.errors.length > 0) {
      // 解析失败：替换进度消息为错误
      replaceProgressWithError(store.errors[0] || '未能识别到有效型号，请补充更多信息。')
      return
    }

    addMsg('assistant', '已解析出以下规格信息，请核对修正：', { resultType: 'spec' })
  }

  if (phase === 'done') {
    finalizeLastMsg()
    isProcessing.value = false

    // SSE 流失败/断流: 只要没有任何可展示的结果,无论是否有 Agent 跑过,
    // 都把进度提示替换为错误消息（错误气泡自带重试按钮）
    const hasResult =
      !!store.chatResponse ||
      store.alternatives.length > 0 ||
      store.matchedSuppliers.length > 0 ||
      !!store.rfqDoc
    if (!hasResult && store.errors.length > 0) {
      // token 流中途断开: 已流出实质文本则保留在气泡里,断流由 streamError 条 + 重试承载;
      // 仅占位/进度文案替换为错误气泡
      const last = messages.value[messages.value.length - 1]
      const partial = last?.role === 'assistant' ? last.content.trim() : ''
      if (!partial || PROGRESS_PLACEHOLDERS.includes(partial)) {
        replaceProgressWithError(store.streamError || store.errors[0] || '连接中断，请重试')
      }
      return
    }

    // 纯聊天流（无寻源结果）→ 展示聊天内容
    // 注意：confirmSpec 的 match 阶段也可能有 chatResponse，但此时有 alternatives/suppliers，优先展示寻源结果
    if (store.chatResponse && !store.alternatives.length && !store.matchedSuppliers.length) {
      showChatResponse(store.chatResponse)
      return
    }

    // 分段展示所有结果: 卡片挂在各自消息下, 追问时不消失 (#28)
    if (store.alternatives.length) {
      addMsg('assistant', '找到以下替代料建议：', { resultType: 'alternatives' })
    }
    if (store.matchedSuppliers.length) {
      addMsg('assistant', '以下供应商有相关供应能力（能力匹配，非现货承诺）：', { resultType: 'suppliers' })
    }
    if (store.rfqDoc) {
      addMsg('assistant', '已为您生成询价单，可编辑后发送：', { resultType: 'rfq' })
    }
    if (store.leadGrade) {
      addMsg('assistant', '线索分级结果：', { resultType: 'grade' })
    }

    // 保存历史到 localStorage 作为降级备份(含可重建消息列表)
    if (!store.isVague) {
      captureLivePayloads()
      persistLocal()
    }
  }
})

// ── 监听进度 ──
watch(() => store.progress.length, () => {
  const p = store.progress
  if (!p.length) return

  const firstAgent = p[0].agent
  const lastProgress = p[p.length - 1]

  const labels: Record<string, string> = {
    parse: '正在识别型号与参数…',
    normalize: '正在标准化规格…',
    alternatives: '正在查询替代料…',
    match: '正在匹配供应商…',
    gen_rfq: '正在生成询价单…',
    grade: '正在评估线索…',
  }

  // 首个 Agent 不是 chat → 寻源流程 → 显示 AgentTimeline
  if (firstAgent !== 'chat') {
    const lastMsg = messages.value[messages.value.length - 1]
    if (lastMsg && lastMsg.role === 'assistant' && lastMsg.streaming && !lastMsg.resultType) {
      lastMsg.resultType = 'progress'
    }
    // 更新进度文字（寻源 Agent 的标签）
    if (lastProgress.status === 'running' && labels[lastProgress.agent]) {
      updateProgressText(labels[lastProgress.agent])
    }
  }
  // chat 的进度文字由流式 token watcher 处理，不在此覆盖
})

// ── 规格确认回调: 冻结确认后的规格卡, 开启本轮 match 阶段 ──
function onSpecConfirm(msg: ChatMessageData, spec: Record<string, SpecField>) {
  if (!isLiveMsg(msg)) return
  msg.payload = {
    ...(msg.payload ?? {}),
    normalizedSpec: deepCopy(spec),
    parsedSpec: deepCopy(store.parsedSpec),
  }
  msg.frozen = true
  isProcessing.value = true
  addMsg('assistant', '规格已确认，正在查询替代料与匹配供应商…', { streaming: true, resultType: 'progress' })
  store.confirmSpec(spec)
}

// ── 供应商 → 询价单 (仅活跃轮可触发) ──
function onGenerateRfq(msg: ChatMessageData) {
  if (!isLiveMsg(msg)) return
  const exists = messages.value.some(
    (m) => m.turnId === activeTurnId.value && !m.frozen && m.resultType === 'rfq',
  )
  if (!exists) {
    addMsg('assistant', '以下是为您生成的询价单，可编辑：', { resultType: 'rfq' })
  }
  scrollDown()
}

// ── 卡片交互守卫: 仅当前活跃轮的消息允许写回 store ──
function onToggleSupplier(msg: ChatMessageData, id: string) {
  if (isLiveMsg(msg)) store.toggleSupplier(id)
}
function onSelectAll(msg: ChatMessageData) {
  if (isLiveMsg(msg)) store.selectAllSuppliers()
}
function onDeselectAll(msg: ChatMessageData) {
  if (isLiveMsg(msg)) store.deselectAllSuppliers()
}
function onRetryMatch(msg: ChatMessageData) {
  if (isLiveMsg(msg)) store.retryMatch()
}
function onRfqUpdate(msg: ChatMessageData, text: string) {
  if (isLiveMsg(msg)) store.setRfqDoc(text)
}
function onRfqSent(msg: ChatMessageData) {
  if (!isLiveMsg(msg)) return
  store.markRfqSent()
  if (msg.payload) msg.payload.rfqSent = true
}
function onRfqRegenerate(msg: ChatMessageData) {
  if (isLiveMsg(msg)) store.regenerateRfq()
}

// ── 历史会话重建 (#28): 对话内恢复聊天气泡, 不再跳转向导页 ──
const openingSession = ref(false)

async function openSession(threadId: string) {
  if (openingSession.value) return
  openingSession.value = true
  restoringSession.value = true
  try {
    if (isProcessing.value) store.abort()
    isProcessing.value = false

    const { getDetail } = useHistory()
    const detail = await getDetail(threadId)
    // 恢复 store (threadId / 实体快照 / 各结果数据), preload 避免重复请求
    const ok = await store.loadFromSession(threadId, detail)
    if (!ok) {
      restoringSession.value = false
      addMsg('system', '未能加载该会话（可能已被删除，且本地无备份）。')
      return
    }

    // 气泡来源: 优先 localStorage 保存的多轮消息列表;
    // 无则(老会话/跨设备)由服务端状态快照合成单轮气泡 —— 服务端不存逐轮消息, 只能还原最后一轮
    const localMsgs = loadLocalMessages(threadId)
    if (localMsgs) {
      messages.value = localMsgs.map((m: any) => ({
        ...m,
        id: m.id || uid(),
        streaming: false,
        frozen: true,
        turnId: -1,
      }))
    } else {
      messages.value = synthesizeFromStore(Date.parse(detail!.updated_at) || Date.now())
    }

    activeTurnId.value++  // 重建消息均为冻结历史, 后续追问从新一轮开始
    inputText.value = ''
    scrollDown()
    showHistory.value = false
    await nextTick()  // 让 loadFromSession 触发的 watcher 在抑制标记内冲刷完毕
  } finally {
    restoringSession.value = false
    openingSession.value = false
  }
}

/** 服务端/本地状态快照 → 合成单轮气泡(快照不含逐轮消息与时间线, 尽力还原) */
function synthesizeFromStore(ts: number): ChatMessageData[] {
  const msgs: ChatMessageData[] = []
  const frozenCommon: Pick<ChatMessageData, 'frozen' | 'turnId' | 'streaming'> = {
    frozen: true,
    turnId: -1,
    streaming: false,
  }
  if (store.rawQuery) {
    msgs.push({ id: uid(), role: 'user', content: store.rawQuery, timestamp: ts, ...frozenCommon })
  }
  if (store.chatResponse) {
    msgs.push({ id: uid(), role: 'assistant', content: store.chatResponse, timestamp: ts, ...frozenCommon })
  }
  if (store.normalizedSpec) {
    msgs.push({
      id: uid(), role: 'assistant', content: '已解析出以下规格信息：', timestamp: ts, ...frozenCommon,
      resultType: 'spec',
      payload: { normalizedSpec: deepCopy(store.normalizedSpec), parsedSpec: deepCopy(store.parsedSpec) },
    })
  }
  if (store.alternatives.length) {
    msgs.push({
      id: uid(), role: 'assistant', content: '找到以下替代料建议：', timestamp: ts, ...frozenCommon,
      resultType: 'alternatives',
      payload: {
        alternatives: deepCopy(store.alternatives),
        originalPart: ((store.parsedSpec as any)?.['型号']?.value as string) || '',
        originalBrand: ((store.parsedSpec as any)?.['品牌']?.value as string) || '',
      },
    })
  }
  if (store.matchedSuppliers.length) {
    msgs.push({
      id: uid(), role: 'assistant', content: '以下供应商有相关供应能力（能力匹配，非现货承诺）：', timestamp: ts, ...frozenCommon,
      resultType: 'suppliers',
      payload: {
        matchedSuppliers: deepCopy(store.matchedSuppliers),
        selectedSupplierIds: [...store.selectedSupplierIds],
      },
    })
  }
  if (store.rfqDoc) {
    msgs.push({
      id: uid(), role: 'assistant', content: '已生成询价单：', timestamp: ts, ...frozenCommon,
      resultType: 'rfq',
      payload: {
        rfqDoc: store.rfqDoc,
        rfqId: store.rfqId,
        rfqSent: store.rfqSent,
        normalizedSpec: deepCopy(store.normalizedSpec),
        alternatives: deepCopy(store.alternatives),
        matchedSuppliers: deepCopy(store.matchedSuppliers),
        selectedSupplierIds: [...store.selectedSupplierIds],
      },
    })
  }
  if (store.leadGrade) {
    msgs.push({
      id: uid(), role: 'assistant', content: '线索分级结果：', timestamp: ts, ...frozenCommon,
      resultType: 'grade',
      payload: { leadGrade: deepCopy(store.leadGrade) },
    })
  }
  return msgs
}

// ── 清理 ──
onUnmounted(() => store.abort())

// ── 监听流式结束（兜底: 强制 finalize）──
watch(() => store.isStreaming, (streaming) => {
  if (!streaming) {
    finalizeStreamingFlag()
  }
})

// ── 兜底: 所有已触发的 Agent 完成后自动触发门控 ──
// 注意: store.onEnd 已负责 phase → gating 的转换，此兜底只预防 onEnd 未触发的情况
let gatingGuard = false
const nonPendingAgentsDone = computed(() => {
  const nonPending = store.agents.filter((a) => a.status !== 'pending')
  return nonPending.length > 0 && nonPending.every((a) => a.status === 'done' || a.status === 'error')
})

watch(nonPendingAgentsDone, (done) => {
  if (!done || store.phase !== 'spec' || gatingGuard) return
  gatingGuard = true
  store.isStreaming = false
  finalizeStreamingFlag()
  if (store.parsedSpec && store.errors.length === 0) {
    store.phase = 'gating'
  }
})

// ── 示例 ──
const examples = [
  'TMK212BJ105KG-T 缺货，找替代',
  '0805 10uF X7R 50V MLCC，月用量50万，要国巨或华新科',
  '寻找 GRM188R61A106KE69D 的替代料',
]
</script>

<template>
  <div class="chat-view">
    <!-- 历史记录侧边栏切换按钮 -->
    <button class="chat__history-toggle" :class="{ active: showHistory }" @click="showHistory = !showHistory" title="历史记录">
      <span v-if="showHistory">✕</span>
      <span v-else>☰</span>
    </button>

    <!-- 消息列表 -->
    <div ref="chatContainer" class="chat__msgs">
      <!-- 空态 -->
      <div v-if="messages.length === 0" class="chat__welcome">
        <div class="welcome__mark">M</div>
        <h1 class="welcome__title">对话寻源</h1>
        <p class="welcome__sub">输入型号或需求描述，AI 自动解析、推荐替代料、匹配供应商。</p>
        <div class="welcome__examples">
          <button v-for="ex in examples" :key="ex" class="welcome__chip" @click="inputText = ex">
            {{ ex }}
          </button>
        </div>
      </div>

      <!-- 消息 -->
      <template v-for="msg in messages" :key="msg.id">
        <ChatMessage :message="msg" @retry="retryLast" @regenerate="regenerate(msg.id)">
          <!-- Agent 进度时间线: 生成中展开; 完成后沉淀进消息, 默认折叠可展开回看 (#28) -->
          <div v-if="msg.resultType === 'progress' || timelineAgents(msg).length" class="chat__timeline">
            <AgentTimeline
              v-if="msg.resultType === 'progress'"
              :agents="store.agents"
              :alternatives-count="store.alternatives.length"
              :suppliers-count="store.matchedSuppliers.length"
            />
            <details v-else class="tl-fold">
              <summary class="tl-fold__summary">
                <span class="tl-fold__caret">▸</span>
                <span>执行过程 · {{ timelineDoneCount(msg) }}/{{ timelineAgents(msg).length }} 阶段完成</span>
              </summary>
              <AgentTimeline
                class="tl-fold__body"
                :agents="timelineAgents(msg)"
                :alternatives-count="msg.payload?.alternativesCount ?? 0"
                :suppliers-count="msg.payload?.suppliersCount ?? 0"
                :live="false"
              />
            </details>
          </div>

          <!-- 规格确认卡: 活跃轮可编辑确认, 冻结后轮次只读展示 -->
          <SpecConfirm
            v-if="msg.resultType === 'spec' && specFor(msg)"
            :spec="specFor(msg) as Record<string, SpecField>"
            :gating="isLiveMsg(msg) && store.phase === 'gating'"
            :readonly="!isLiveMsg(msg)"
            @confirm="onSpecConfirm(msg, $event)"
          />

          <!-- 替代料卡: 挂在各自消息下, 追问不消失 -->
          <AlternativesList
            v-if="msg.resultType === 'alternatives' && alternativesFor(msg).length"
            :alternatives="alternativesFor(msg)"
            :original-part="originalPartFor(msg)"
            :original-brand="originalBrandFor(msg)"
          />

          <!-- 供应商卡 -->
          <SuppliersMatch
            v-if="msg.resultType === 'suppliers' && suppliersFor(msg).length"
            :suppliers="suppliersFor(msg)"
            :selected-ids="selectedIdsFor(msg)"
            :streaming="false"
            :stream-progress="''"
            :error="null"
            @toggle="onToggleSupplier(msg, $event)"
            @select-all="onSelectAll(msg)"
            @deselect-all="onDeselectAll(msg)"
            @generate="onGenerateRfq(msg)"
            @retry="onRetryMatch(msg)"
          />

          <!-- 询价单 -->
          <RfqEditor
            v-if="msg.resultType === 'rfq'"
            :rfq-doc="rfqDocFor(msg)"
            :rfq-id="rfqIdFor(msg)"
            :spec="specFor(msg)"
            :alternatives="alternativesFor(msg)"
            :suppliers="suppliersFor(msg)"
            :selected-supplier-ids="selectedIdsFor(msg)"
            :sent="rfqSentFor(msg)"
            :streaming="rfqStreaming(msg)"
            @update="onRfqUpdate(msg, $event)"
            @sent="onRfqSent(msg)"
            @regenerate="onRfqRegenerate(msg)"
          />

          <!-- 线索分级 -->
          <div v-if="msg.resultType === 'grade' && gradeFor(msg)" class="grade-card">
            <div class="grade-card__head">
              <span class="grade-card__label">线索分级</span>
            </div>
            <div class="grade-card__body">
              <div class="grade-card__main">
                <span class="grade-letter" :class="`grade-${gradeFor(msg)!.grade}`">
                  {{ gradeFor(msg)!.grade }}
                </span>
                <span class="grade-score">{{ gradeFor(msg)!.score }} 分</span>
                <Tag
                  :type="gradeFor(msg)!.grade === 'A' || gradeFor(msg)!.grade === 'B' ? 'success' : gradeFor(msg)!.grade === 'C' ? 'warning' : 'danger'"
                  :value="`${gradeFor(msg)!.grade} 级`"
                />
              </div>
              <ul class="grade-card__reasons">
                <li v-for="(r, ri) in gradeFor(msg)!.reasons" :key="ri">{{ r }}</li>
              </ul>
            </div>
          </div>
        </ChatMessage>
      </template>
    </div>

    <!-- 输入栏 -->
    <div class="chat__input-bar">
      <!-- 断流/传输错误条: 无论是否有 Agent 跑过都显示,可手动重试 -->
      <div v-if="store.streamError" class="chat__stream-alert chat__stream-alert--error">
        <span class="stream-alert__text">连接中断，请重试</span>
        <button class="stream-alert__btn" @click="retryLast">重试</button>
        <button class="stream-alert__close" title="关闭" @click="store.clearStreamError()">✕</button>
      </div>
      <!-- 非致命流警告（个别帧解析失败） -->
      <div v-else-if="store.streamNotice" class="chat__stream-alert chat__stream-alert--notice">
        <span class="stream-alert__text">{{ store.streamNotice }}</span>
        <button class="stream-alert__close" title="关闭" @click="store.clearStreamNotice()">✕</button>
      </div>
      <div class="chat__input-wrap">
        <textarea
          v-model="inputText"
          class="chat__input"
          rows="1"
          placeholder="输入型号或需求描述…"
          :disabled="isProcessing"
          @keydown="handleKeydown"
        />
        <button v-if="isProcessing" class="chat__send chat__send--stop" @click="stopSending">
          <span class="stop-icon" />
          <span>停止</span>
        </button>
        <button v-else class="chat__send" :disabled="!inputText.trim()" @click="send">发送</button>
      </div>
      <p class="chat__hint">Enter 发送 · Shift+Enter 换行</p>
    </div>

    <!-- 历史记录侧边栏 -->
    <aside v-if="showHistory" class="chat__history-sidebar">
      <SessionHistoryPanel @newChat="newChat" @close="showHistory = false" @select="openSession" />
    </aside>
  </div>
</template>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  min-height: calc(100vh - 56px);
  max-width: 900px;
  margin: 0 auto;
  position: relative;
}

/* 历史记录切换按钮 */
.chat__history-toggle {
  position: fixed;
  top: 64px;
  right: 12px;
  z-index: 45;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  background: var(--bg-2);
  border: 1px solid var(--border-default);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.chat__history-toggle:hover {
  color: var(--text-primary);
  border-color: var(--accent-border);
}
.chat__history-toggle.active {
  color: var(--accent-hover);
  border-color: var(--accent-border);
  background: var(--accent-soft);
}

/* 历史记录侧边栏 */
.chat__history-sidebar {
  position: fixed;
  top: 56px;
  right: 0;
  bottom: 0;
  width: 280px;
  z-index: 44;
  background: rgba(10, 11, 15, 0.96);
  border-left: 1px solid var(--border-default);
  backdrop-filter: blur(18px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.chat__msgs {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4) 0;
  scroll-behavior: smooth;
}

/* 空态 */
.chat__welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px var(--space-4) 40px;
  text-align: center;
}
.welcome__mark {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--font-size-xl);
  font-weight: 700;
  border-radius: var(--radius-lg);
  background: var(--gradient-accent);
  color: #fff;
  margin-bottom: var(--space-4);
}
.welcome__title {
  font-size: var(--font-size-2xl);
  font-weight: 700;
  margin-bottom: var(--space-2);
}
.welcome__sub {
  color: var(--text-secondary);
  font-size: var(--font-size-md);
  margin-bottom: var(--space-6);
  max-width: 480px;
}
.welcome__examples {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  justify-content: center;
}
.welcome__chip {
  padding: 8px 16px;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  background: var(--bg-2);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-full);
  transition: all var(--transition-fast);
  cursor: pointer;
}
.welcome__chip:hover {
  color: var(--accent-hover);
  border-color: var(--accent-border);
  background: var(--accent-soft);
}

/* 输入栏 */
.chat__input-bar {
  border-top: 1px solid var(--border-default);
  background: var(--bg-1);
  padding: var(--space-3) var(--space-4);
}
.chat__input-wrap {
  display: flex;
  gap: var(--space-3);
  max-width: 800px;
  margin: 0 auto;
  background: var(--bg-2);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: var(--space-2);
  transition: border-color var(--transition-base), box-shadow var(--transition-base);
}
.chat__input-wrap:focus-within {
  border-color: var(--accent-border);
  box-shadow: var(--shadow-glow);
}
.chat__input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  padding: var(--space-2) var(--space-3);
  font-size: var(--font-size-md);
  color: var(--text-primary);
  resize: none;
  max-height: 120px;
  line-height: 1.6;
}
.chat__input::placeholder { color: var(--text-tertiary); }
.chat__input:disabled { opacity: 0.5; }
.chat__send {
  align-self: flex-end;
  padding: 8px 20px;
  background: var(--accent);
  color: #fff;
  font-size: var(--font-size-sm);
  font-weight: 600;
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
  white-space: nowrap;
}
.chat__send:hover:not(:disabled) { background: var(--accent-hover); }
.chat__send:disabled { opacity: 0.4; cursor: not-allowed; }
.chat__send--stop {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.stop-icon {
  display: block;
  width: 10px;
  height: 10px;
  background: #fff;
  border-radius: 2px;
}

/* 断流错误条 / 流警告条 */
.chat__stream-alert {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  max-width: 800px;
  margin: 0 auto var(--space-2);
  padding: var(--space-2) var(--space-3);
  font-size: var(--font-size-sm);
  border-radius: var(--radius-md);
  border: 1px solid;
}
.chat__stream-alert--error {
  color: var(--danger);
  background: var(--danger-soft);
  border-color: rgba(239, 68, 68, 0.3);
}
.chat__stream-alert--notice {
  color: var(--warning);
  background: var(--warning-soft);
  border-color: rgba(234, 179, 8, 0.3);
}
.stream-alert__text { flex: 1; }
.stream-alert__btn {
  padding: 2px 10px;
  font-size: var(--font-size-xs);
  color: var(--danger);
  background: transparent;
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.stream-alert__btn:hover { border-color: var(--danger); }
.stream-alert__close {
  color: inherit;
  background: none;
  border: none;
  font-size: var(--font-size-xs);
  cursor: pointer;
  opacity: 0.7;
}
.stream-alert__close:hover { opacity: 1; }
.chat__hint {
  text-align: center;
  margin-top: var(--space-2);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}

/* 线索卡片 */
.grade-card {
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: var(--bg-2);
}
.grade-card__head {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-subtle);
  font-size: var(--font-size-sm);
  font-weight: 600;
}
.grade-card__body { padding: var(--space-4); }
.grade-card__main {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.grade-letter {
  width: 36px; height: 36px;
  display: flex; align-items: center; justify-content: center;
  font-size: var(--font-size-lg); font-weight: 700;
  border-radius: var(--radius-md);
  font-family: var(--font-mono);
}
.grade-A, .grade-B { color: var(--success); background: var(--success-soft); }
.grade-C { color: var(--warning); background: var(--warning-soft); }
.grade-D { color: var(--danger); background: var(--danger-soft); }
.grade-score {
  font-size: var(--font-size-md);
  color: var(--text-secondary);
  font-family: var(--font-mono);
}
.grade-card__reasons { display: flex; flex-direction: column; gap: var(--space-2); }
.grade-card__reasons li {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  padding-left: var(--space-4);
  position: relative;
}
.grade-card__reasons li::before {
  content: '·';
  position: absolute;
  left: var(--space-2);
  color: var(--text-tertiary);
}

/* Agent 进度时间线 */
.chat__timeline {
  margin: var(--space-3) 0;
  padding: var(--space-3);
  background: var(--bg-1);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
}

/* 沉淀后的折叠时间线 (#28): 默认折叠, 展开回看"它刚才做了什么" */
.tl-fold {
  font-size: var(--font-size-sm);
}
.tl-fold__summary {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  cursor: pointer;
  user-select: none;
  list-style: none;
  padding: var(--space-1) 0;
  transition: color var(--transition-fast);
}
.tl-fold__summary::-webkit-details-marker {
  display: none;
}
.tl-fold__summary:hover {
  color: var(--text-secondary);
}
.tl-fold__caret {
  display: inline-block;
  transition: transform var(--transition-fast);
  font-size: 10px;
}
.tl-fold[open] .tl-fold__caret {
  transform: rotate(90deg);
}
.tl-fold__body {
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}
</style>
