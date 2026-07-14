import {
  buildAlternatives,
  buildLeadGrade,
  buildNormalizedSpec,
  buildParsedSpec,
  buildRfqStream,
  buildSuppliers,
  buildVagueState,
  isVagueQuery,
} from './data'
import type { SseCallbacks, StreamProcureParams } from '@/types/procure'

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms))

/**
 * Mock SSE:严格按真实事件契约(start/progress/token/error/result/end)调用回调。
 * 分两阶段:phase='spec' 跑 parse+normalize 后停(门控);phase='match' 跑后续四阶段。
 */
export async function mockSseProcure(
  params: StreamProcureParams,
  cb: SseCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const aborted = () => signal?.aborted

  if (params.phase === 'spec') {
    const threadId = params.thread_id || `thd-${Date.now()}`
    cb.onStart?.(threadId)
    await wait(300)
    if (aborted()) return

    cb.onProgress?.('parse', 'running')
    await wait(700)
    if (aborted()) return

    if (isVagueQuery(params.query || '')) {
      cb.onProgress?.('parse', 'done')
      cb.onResult?.(buildVagueState(threadId, params.query || ''))
      cb.onError?.('normalize', '需求信息不足,无法解析出有效规格')
      cb.onEnd?.()
      return
    }

    cb.onProgress?.('parse', 'done', buildParsedSpec())
    await wait(500)
    if (aborted()) return

    cb.onProgress?.('normalize', 'running')
    await wait(800)
    if (aborted()) return

    cb.onProgress?.('normalize', 'done', buildNormalizedSpec())
    cb.onResult?.({
      thread_id: threadId,
      raw_query: params.query || '',
      parsed_spec: buildParsedSpec(),
      normalized_spec: buildNormalizedSpec(),
    })
    cb.onEnd?.()
    return
  }

  // phase === 'match'
  const threadId = params.thread_id || `thd-${Date.now()}`
  cb.onStart?.(threadId)
  const spec = params.confirmed_spec || buildNormalizedSpec()
  const alternatives = buildAlternatives()
  const suppliers = buildSuppliers()

  await wait(300)
  if (aborted()) return
  cb.onProgress?.('alternatives', 'running')
  await wait(900)
  if (aborted()) return
  cb.onProgress?.('alternatives', 'done', alternatives)
  await wait(300)
  if (aborted()) return

  cb.onProgress?.('match', 'running')
  await wait(800)
  if (aborted()) return
  cb.onProgress?.('match', 'done', suppliers)
  await wait(300)
  if (aborted()) return

  // gen_rfq:逐 token 流式
  cb.onProgress?.('gen_rfq', 'running')
  await wait(200)
  const rfqText = buildRfqStream({ spec, alternatives, suppliers })
  const chunks = rfqText.match(/[\s\S]{1,8}/g) || []
  for (const c of chunks) {
    if (aborted()) return
    cb.onToken?.(c)
    await wait(18)
  }
  cb.onProgress?.('gen_rfq', 'done')

  await wait(200)
  if (aborted()) return
  cb.onProgress?.('grade', 'running')
  await wait(600)
  if (aborted()) return
  const grade = buildLeadGrade()
  cb.onProgress?.('grade', 'done', grade)

  cb.onResult?.({
    thread_id: threadId,
    normalized_spec: spec,
    alternatives,
    matched_suppliers: suppliers,
    rfq_doc: rfqText,
    rfq_id: `MF-${Date.now().toString().slice(-8)}`,
    lead_grade: grade,
  })
  cb.onEnd?.()
}
