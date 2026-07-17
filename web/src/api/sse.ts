import type { SseCallbacks, SseEvent } from '@/types/procure'

/**
 * 通过 fetch + ReadableStream 消费 SSE。
 * procure 接口为 POST,EventSource 仅支持 GET,故手解 `text/event-stream`。
 * 事件以空行(\n\n)分隔,每行 `data: <json>`,多行 data 合并。
 */
export async function fetchSSE(
  url: string,
  body: unknown,
  callbacks: SseCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(body),
    signal,
  })

  if (!res.ok || !res.body) {
    const detail = res.status === 422 ? await res.text().catch(() => '') : ''
    throw new Error(`SSE 请求失败: HTTP ${res.status}${detail ? ' ' + detail : ''}`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let idx: number
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const raw = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      handleEvent(raw, callbacks)
    }
  }
  if (buffer.trim()) handleEvent(buffer, callbacks)
}

function handleEvent(raw: string, callbacks: SseCallbacks) {
  const dataLines = raw
    .split('\n')
    .filter((l) => l.startsWith('data:'))
    .map((l) => l.slice(5).trim())
  if (!dataLines.length) return
  try {
    const evt = JSON.parse(dataLines.join('\n')) as SseEvent
    dispatch(evt, callbacks)
  } catch {
    // 忽略无法解析的事件(如心跳注释)
  }
}

function dispatch(evt: SseEvent, cb: SseCallbacks) {
  switch (evt.type) {
    case 'start':
      cb.onStart?.(evt.thread_id, evt.rfq_id)
      break
    case 'progress':
      cb.onProgress?.(evt.agent, evt.status, evt.result)
      break
    case 'token':
      cb.onToken?.(evt.text, evt.agent)
      break
    case 'error':
      cb.onError?.(evt.agent, evt.message)
      break
    case 'result':
      cb.onResult?.(evt.state)
      break
    case 'end':
      cb.onEnd?.()
      break
  }
}
