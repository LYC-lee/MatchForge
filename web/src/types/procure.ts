// ===== 智能体阶段 =====
export type AgentName = 'parse' | 'normalize' | 'alternatives' | 'match' | 'gen_rfq' | 'grade' | 'chat'
export type AgentStatus = 'pending' | 'running' | 'done' | 'error'

export interface AgentState {
  name: AgentName
  status: AgentStatus
  message?: string
  startedAt?: number
  endedAt?: number
}

// ===== 替代料 =====
/** L1 完全等效 / L2 跨品牌 pin-to-pin / L3 参数有差异 / L4 需工程评估 / L5 仅参考 */
export type AltLevel = 'L1' | 'L2' | 'L3' | 'L4' | 'L5'

export interface ParamDiff {
  field: string
  original: string
  alternative: string
  /** match=一致(绿) diff=差异(黄) risk=风险(红) */
  status: 'match' | 'diff' | 'risk'
  note?: string
}

export interface Alternative {
  part_name: string
  part?: string
  brand: string
  package: string
  key_params: Record<string, string>
  level: AltLevel
  /** 后端有输出才显示(C3),不得默认 */
  confidence?: number
  verified: boolean
  /** 来源枚举(A线 #16): Neo4j:* | llm_inferred* | rule_fallback:query_failed;旧数据可能缺失 */
  source?: string
  updated_at: string
  diffs?: ParamDiff[]
  specs?: Record<string, unknown>
  reason?: string
  diff_items?: {
    param: string
    original: string
    alternative: string
    type: 'match' | 'diff' | 'risk'
  }[]
  note?: string
}

// ===== 供应商 =====
export interface Supplier {
  id: string
  name: string
  score?: number
  category?: string
  region: string
  location?: string
  categories: string[]
  brands: string[]
  qualifications: string[]
  moq: number
  lead_time_weeks?: number
  in_stock?: boolean
  response_speed: string
  data_source: string
  updated_at: string
  /** 首期恒为 false —— 仅能力匹配,非实时库存/报价/交期承诺 */
  confirmed_stock: boolean
  confirmed_lead: boolean
  confirmed_price: boolean
  match_score: number
}

// ===== 线索分级 =====
export interface LeadGrade {
  grade: string
  score: number
  reasons: string[]
}

// ===== 规格字段(带置信度,缺失/低置信用于标黄/问号) =====
export interface SpecField {
  value: string
  /** C3: 后端给了才保留/显示,前端不得虚构 */
  confidence?: number
  missing?: boolean
  editable?: boolean
}

// ===== 引用回显 (C2) =====
export interface Citation {
  /** 手册类型: product | business */
  doc: string
  chunk_id: string
  chunk_uid: string
  score: number
  excerpt: string
  company_id: number
  language: string
}

// ===== 多轮引用快照 (C4, #23/#28) =====
/**
 * 后端在 result 事件与 PG 会话快照中下发 (graph.py:490-506)。
 * 前端持久化最近一次快照, 下一轮请求时放入 confirmed_spec._snapshot 原样回传,
 * 支撑"第N个/刚才那个/它"等追问的引用解析 (graph.py:369-375)。
 */
export interface EntitiesSnapshot {
  current_spec: Record<string, unknown> | null
  alternatives: Alternative[]
  matched_suppliers: Supplier[]
}

// ===== ProcureState =====
export interface ProcureState {
  thread_id: string
  raw_query: string
  chat_response: string | null
  parsed_spec: Record<string, SpecField | string> | null
  normalized_spec: Record<string, SpecField | string> | null
  alternatives: Alternative[]
  matched_suppliers: Supplier[]
  rfq_doc: string | null
  rfq_id: string | null
  lead_grade: LeadGrade | null
  errors: string[]
  /** C4: 最近一次 result 事件携带的实体快照, 多轮追问时回传 */
  entities_snapshot?: EntitiesSnapshot | null
}

// ===== SSE 事件契约 =====
export type SseEvent =
  | { type: 'start'; thread_id: string; rfq_id?: string }
  | { type: 'progress'; agent: AgentName; status: AgentStatus; result?: unknown }
  | { type: 'token'; agent?: AgentName | string; text: string }
  | { type: 'citation'; agent: string; citations: Citation[] }
  | { type: 'error'; agent?: AgentName; message: string }
  | { type: 'result'; state: Partial<ProcureState> }
  | { type: 'end' }

export interface SseCallbacks {
  onStart?: (threadId: string, rfqId?: string) => void
  onProgress?: (agent: AgentName, status: AgentStatus, result?: unknown) => void
  onToken?: (text: string, agent?: AgentName | string) => void
  /** 引用回显(C2): alternatives / rag_enrich 智能体产出引用片段 */
  onCitation?: (agent: string, citations: Citation[]) => void
  onError?: (agent: AgentName | undefined, message: string) => void
  onResult?: (state: Partial<ProcureState>) => void
  onEnd?: () => void
  /** 单个 SSE 帧 JSON 解析失败时回调（不中断流，由实现侧累计阈值后报错） */
  onParseError?: (raw: string, error: unknown) => void
}

export interface StreamProcureParams {
  query?: string
  thread_id?: string
  confirmed_spec?: Record<string, SpecField | string> | null
  phase: 'spec' | 'match'
  user_id?: string
  /** C4: 上一轮实体快照, 仅 phase=spec 的新查询需要 (回传为 confirmed_spec._snapshot) */
  snapshot?: EntitiesSnapshot | null
}

// ===== 会话历史 =====
export interface SessionSummary {
  thread_id: string
  user_id: string
  title: string
  phase: string
  status: string
  created_at: string
  updated_at: string
}

export interface SessionDetail {
  thread_id: string
  user_id: string
  title: string
  phase: string
  status: string
  state: ProcureState
  created_at: string
  updated_at: string
}
