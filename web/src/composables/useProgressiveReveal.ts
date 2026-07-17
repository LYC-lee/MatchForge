import { ref } from 'vue'

/**
 * 客户端渐进式展示（伪流式）。
 *
 * ⚠️ 过渡方案 (#29): kb 问答接口 (`/chat/ask`、`/chat/compare`、enterprise
 * chatAsk / partnerChat) 目前**没有 SSE / 流式后端** —— 只有寻源接口
 * `/procure/stream` 实现了真流式 (#33, `astream_events` + token 事件)。
 * 因此在完整答案到达后, 按帧逐步 reveal 文本并显示光标, 模拟流式效果。
 *
 * TODO(#29): 待 A 线为 kb 问答提供流式接口后移除本 composable,
 * 改为直接消费 SSE token 事件 (参考 stores/procure.ts 的 onToken)。
 */

/** 每帧 reveal 的字符数 (20-30 字/帧的中值) */
const CHUNK_SIZE = 25
/** 帧间隔 (ms) */
const FRAME_INTERVAL = 40

export function useProgressiveReveal() {
  /** 当前是否正在 reveal (驱动光标与停止键) */
  const revealing = ref(false)

  let timer: ReturnType<typeof setInterval> | undefined
  let stopped = false

  function clearTimer() {
    if (timer !== undefined) {
      clearInterval(timer)
      timer = undefined
    }
  }

  /**
   * 将 fullText 逐步写入 target.value, 结束后 resolve。
   * 重复调用会先停掉上一轮 reveal。
   */
  function start(target: { value: string }, fullText: string): Promise<void> {
    stop()
    return new Promise<void>((resolve) => {
      if (!fullText) {
        resolve()
        return
      }
      revealing.value = true
      stopped = false
      target.value = ''
      let pos = 0
      timer = setInterval(() => {
        if (stopped) {
          clearTimer()
          revealing.value = false
          resolve()
          return
        }
        pos = Math.min(pos + CHUNK_SIZE, fullText.length)
        target.value = fullText.slice(0, pos)
        if (pos >= fullText.length) {
          clearTimer()
          revealing.value = false
          resolve()
        }
      }, FRAME_INTERVAL)
    })
  }

  /** 手动停止: 保留已 reveal 的部分, 光标消失 */
  function stop() {
    stopped = true
    clearTimer()
    revealing.value = false
  }

  return { revealing, start, stop }
}
