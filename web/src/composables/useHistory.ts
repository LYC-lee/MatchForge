import { ref } from 'vue'
import type { SessionSummary, SessionDetail } from '@/types/procure'
import { fetchSessions, fetchSessionDetail, deleteSessionApi } from '@/api/procure'

const KEY = 'matchforge:history'
const USER_ID_KEY = 'matchforge:uid'

/**
 * 获取或生成用户标识。
 * 登录用户优先使用 account，匿名用户使用 localStorage 持久化的 UUID。
 */
export function getUserId(): string {
  try {
    const userRaw = localStorage.getItem('matchforge:user')
    if (userRaw) {
      const user = JSON.parse(userRaw)
      if (user?.account) return user.account
    }
  } catch { /* ignore */ }

  let uid = localStorage.getItem(USER_ID_KEY)
  if (!uid) {
    uid = 'anon_' + crypto.randomUUID().slice(0, 12)
    localStorage.setItem(USER_ID_KEY, uid)
  }
  return uid
}

// ── localStorage 数据结构 ──

interface LocalRecord {
  id: string
  thread_id: string
  raw_query: string
  created_at: string
  rfq_sent: boolean
  state: any
  /** #28: 可渲染的多轮消息列表(含各消息卡片 payload), 供 ChatView 重建聊天气泡 */
  messages?: any[]
}

function loadLocalRecords(): LocalRecord[] {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function recordsToSummaries(list: LocalRecord[]): SessionSummary[] {
  return list
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .map((r) => ({
      thread_id: r.thread_id,
      user_id: '',
      title: r.raw_query,
      phase: 'match',
      status: 'completed',
      created_at: r.created_at,
      updated_at: r.created_at,
    }))
}

function loadLocalRecord(threadId: string): LocalRecord | undefined {
  return loadLocalRecords().find((r) => r.thread_id === threadId || r.id === threadId)
}

function removeLocalRecord(threadId: string) {
  const list = loadLocalRecords().filter((r) => r.thread_id !== threadId && r.id !== threadId)
  localStorage.setItem(KEY, JSON.stringify(list))
}

// ── 公开 API ──

export function useHistory() {
  const sessions = ref<SessionSummary[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  /** 加载会话列表：API 优先，localStorage 补充 + 降级 */
  async function load(): Promise<SessionSummary[]> {
    loading.value = true
    error.value = null
    const userId = getUserId()

    // 始终先加载 localStorage 数据作为兜底
    const localSummaries = recordsToSummaries(loadLocalRecords())

    try {
      const apiSessions = await fetchSessions(userId)
      if (apiSessions.length > 0) {
        // API 有数据：合并 API + localStorage（API 优先，去重）
        const apiIds = new Set(apiSessions.map((s) => s.thread_id))
        const localOnly = localSummaries.filter((s) => !apiIds.has(s.thread_id))
        sessions.value = [...apiSessions, ...localOnly]
      } else {
        // API 返回空（PG 未连接或无数据）：直接使用 localStorage
        sessions.value = localSummaries
        if (localSummaries.length > 0) {
          error.value = null  // 有本地数据，不显示错误
        }
      }
      return sessions.value
    } catch {
      // API 不可用：降级到 localStorage
      sessions.value = localSummaries
      if (localSummaries.length === 0) {
        error.value = '暂无寻源记录'
      }
      return sessions.value
    } finally {
      loading.value = false
    }
  }

  /** 获取单个会话详情（API 优先，localStorage 降级） */
  async function getDetail(threadId: string): Promise<SessionDetail | null> {
    // 先试 API
    try {
      const detail = await fetchSessionDetail(threadId)
      if (detail && detail.state) return detail
    } catch { /* fall through to localStorage */ }

    // API 不可用或未找到 -> 降级到 localStorage
    const local = loadLocalRecord(threadId)
    if (local) {
      return {
        thread_id: local.thread_id,
        user_id: '',
        title: local.raw_query,
        phase: 'match',
        status: 'completed',
        state: local.state,
        created_at: local.created_at,
        updated_at: local.created_at,
      }
    }

    // localStorage 也没有 -> 调试输出帮助定位
    const all = loadLocalRecords()
    console.warn('[useHistory] 会话未找到', {
      threadId,
      localStorageKeys: all.map((r) => r.thread_id),
      storageKey: KEY,
    })
    return null
  }

  /** 删除会话（API + localStorage 同步删除） */
  async function remove(threadId: string): Promise<boolean> {
    try {
      await deleteSessionApi(threadId)
    } catch { /* ignore API error */ }
    removeLocalRecord(threadId)
    sessions.value = sessions.value.filter((s) => s.thread_id !== threadId)
    return true
  }

  return { sessions, loading, error, load, getDetail, remove }
}

/** 保存到 localStorage（每次对话完成时调用，PG 不可用时作为主存储） */
export function saveToLocal(record: LocalRecord) {
  try {
    const list = loadLocalRecords()
    const idx = list.findIndex((r) => r.id === record.id || r.thread_id === record.thread_id)
    if (idx >= 0) {
      // 同一会话的多轮更新: 保留首条的标题(首个问题)与创建时间, 其余字段取最新
      list[idx] = {
        ...record,
        raw_query: list[idx].raw_query || record.raw_query,
        created_at: list[idx].created_at || record.created_at,
      }
    } else {
      list.push(record)
    }
    // 最多保留 100 条
    if (list.length > 100) {
      list.splice(0, list.length - 100)
    }
    persist(list)
  } catch { /* ignore */ }
}

/** 写入存储, 超出配额时剔除最旧的一半记录后重试一次 */
function persist(list: LocalRecord[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(list))
  } catch {
    try {
      const half = list.slice(Math.floor(list.length / 2))
      localStorage.setItem(KEY, JSON.stringify(half))
    } catch { /* ignore */ }
  }
}

/** 读取本地保存的可渲染消息列表 (#28), 无则返回 null */
export function loadLocalMessages(threadId: string): any[] | null {
  const rec = loadLocalRecord(threadId)
  return rec?.messages?.length ? rec.messages : null
}