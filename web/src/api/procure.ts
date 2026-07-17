import { fetchSSE } from './sse'
import axios from 'axios'
import type { SseCallbacks, StreamProcureParams, SessionSummary, SessionDetail } from '@/types/procure'

const API_URL = '/api/v1/procure/stream'
const SESSIONS_URL = '/api/v1/procure/sessions'

/** 寻源 SSE 统一入口 — 直接调用真实后端。 */
export function streamProcure(
  params: StreamProcureParams,
  callbacks: SseCallbacks,
): AbortController {
  const controller = new AbortController()

  fetchSSE(
    API_URL,
    {
      raw_query: params.query,
      thread_id: params.thread_id,
      confirmed_spec: params.confirmed_spec,
      phase: params.phase,
      user_id: params.user_id || 'anonymous',
    },
    callbacks,
    controller.signal,
  ).then(() => {
    callbacks.onEnd?.()
  }).catch((err: unknown) => {
    if (err instanceof Error && err.name === 'AbortError') return
    const msg = err instanceof Error ? err.message : '网络异常'
    callbacks.onError?.(undefined, msg)
    callbacks.onEnd?.()
  })

  return controller
}

// ── 会话历史 API ──

/** 获取用户会话历史列表 */
export async function fetchSessions(userId: string): Promise<SessionSummary[]> {
  const res = await axios.get(SESSIONS_URL, { params: { user_id: userId } })
  return res.data?.sessions || []
}

/** 获取单个会话详情（含完整状态快照） */
export async function fetchSessionDetail(threadId: string): Promise<SessionDetail | null> {
  try {
    const res = await axios.get(`${SESSIONS_URL}/${threadId}`)
    return res.data as SessionDetail
  } catch {
    return null
  }
}

/** 删除会话 */
export async function deleteSessionApi(threadId: string): Promise<boolean> {
  try {
    await axios.delete(`${SESSIONS_URL}/${threadId}`)
    return true
  } catch {
    return false
  }
}
