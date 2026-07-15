import { fetchSSE } from './sse'
import { mockSseProcure } from '@/mock/sse'
import type { SseCallbacks, StreamProcureParams } from '@/types/procure'

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'
const API_URL = '/api/v1/procure'

/**
 * 寻源 SSE 统一入口。
 * - mock(默认):本地定时器按真实契约模拟事件流,后端未就绪时可独立演示
 * - real:POST /api/v1/procure,fetch + ReadableStream 消费
 * 切换:环境变量 VITE_USE_MOCK=false 连真实后端
 */
export function streamProcure(
  params: StreamProcureParams,
  callbacks: SseCallbacks,
): AbortController {
  const controller = new AbortController()

  if (USE_MOCK) {
    mockSseProcure(params, callbacks, controller.signal)
    return controller
  }

  fetchSSE(
    API_URL,
    {
      query: params.query,
      thread_id: params.thread_id,
      confirmed_spec: params.confirmed_spec,
      phase: params.phase,
    },
    callbacks,
    controller.signal,
  ).catch((err: unknown) => {
    if (err instanceof Error && err.name === 'AbortError') return
    const msg = err instanceof Error ? err.message : '网络异常'
    callbacks.onError?.(undefined, msg)
    callbacks.onEnd?.()
  })

  return controller
}
