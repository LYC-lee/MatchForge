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
  // 解析失败累计阈值: 超过则视为流异常,抛错走与断流相同的错误出口
  const MAX_PARSE_FAILURES = 3
  let parseFailures = 0

  const processFrame = (raw: string) => {
    if (handleEvent(raw, callbacks)) return
    parseFailures++
    if (parseFailures >= MAX_PARSE_FAILURES) {
      throw new Error(`SSE 数据连续 ${MAX_PARSE_FAILURES} 帧解析失败，流已终止`)
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let idx: number
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const raw = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      processFrame(raw)
    }
  }
  if (buffer.trim()) processFrame(buffer)
}

/** 返回 true 表示帧正常（含无 data 行的心跳/注释帧）；false 表示 JSON 解析失败 */
function handleEvent(raw: string, callbacks: SseCallbacks): boolean {
  const dataLines = raw
    .split('\n')
    .filter((l) => l.startsWith('data:'))
    .map((l) => l.slice(5).trim())
  if (!dataLines.length) return true
  // 命名事件帧(event: citation): data 内无 type 时以事件名兜底
  const eventLine = raw.split('\n').find((l) => l.startsWith('event:'))
  const eventName = eventLine ? eventLine.slice(6).trim() : ''
  try {
    const evt = JSON.parse(dataLines.join('\n')) as SseEvent
    if (!evt.type && eventName) (evt as { type?: string }).type = eventName
    dispatch(evt, callbacks)
    return true
  } catch (err) {
    // 不再静默吞掉: 输出警告并上报,由调用方决定提示与阈值处理
    console.warn('[sse] 无法解析的事件帧:', raw, err)
    callbacks.onParseError?.(raw, err)
    return false
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
    case 'citation':
      cb.onCitation?.(evt.agent, evt.citations)
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
