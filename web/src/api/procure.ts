import { fetchSSE } from './sse'
import type { SseCallbacks, StreamProcureParams } from '@/types/procure'

const API_URL = '/api/v1/procure/stream'

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
