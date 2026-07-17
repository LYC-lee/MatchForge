<script setup lang="ts">
import { ref, nextTick, watch, onUnmounted, computed } from 'vue'
import { useProcureStore } from '@/stores/procure'
import { saveToLocal } from '@/composables/useHistory'
import type { SpecField, Alternative, Supplier } from '@/types/procure'
import ChatMessage, { type ChatMessageData } from '@/components/chat/ChatMessage.vue'
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

function uid() { return `m-${++msgId}-${Date.now()}` }
function scrollDown() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

// ── 添加消息 ──
function addMsg(role: ChatMessageData['role'], content: string, opts?: Partial<ChatMessageData>) {
  const msg: ChatMessageData = { id: uid(), role, content, timestamp: Date.now(), ...opts }
  messages.value.push(msg)
  scrollDown()
  return msg
}

// ── 开始在对话中显示结果区块 ──
const showSpecConfirm = ref(false)
const showAlternatives = ref(false)
const showSuppliers = ref(false)
const showRfq = ref(false)
const showGrade = ref(false)

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

  // 用户消息
  addMsg('user', q)

  // 处理中
  isProcessing.value = true
  resetResultFlags()
  store.reset()

  // AI 占位 → 启动
  addMsg('assistant', '思考中…', { streaming: true })
  store.startProcure(q)
}

function resetResultFlags() {
  showSpecConfirm.value = false
  showAlternatives.value = false
  showSuppliers.value = false
  showRfq.value = false
  showGrade.value = false
}

// ── 新建对话：清空当前会话，回到初始状态 ──
function newChat() {
  store.abort()
  store.reset()
  messages.value = []
  resetResultFlags()
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
const PROGRESS_PLACEHOLDERS = [
  '思考中…', '⋯',
  '正在识别型号与参数…', '正在标准化规格…', '正在查询替代料…',
  '正在匹配供应商…', '正在生成询价单…', '正在评估线索…',
]

function stopSending() {
  const last = messages.value[messages.value.length - 1]
  store.abort()
  finalizeMsg()
  // 占位/进度文案被中断后没有实际内容,替换为停止标记;已流出的部分文本保留
  if (last && last.role === 'assistant') {
    const text = last.content.trim()
    if (!text || PROGRESS_PLACEHOLDERS.includes(text)) {
      last.content = '已停止生成。'
      last.resultType = undefined
    }
  }
  isProcessing.value = false
}

// ── 以同一用户输入重新发起（重试 / 重新生成共用）──
function reissue(query: string) {
  if (isProcessing.value) return
  isProcessing.value = true
  resetResultFlags()
  store.reset()
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
  if (last && last.role === 'assistant') {
    last.content = text
    last.streaming = true
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

// ── 终结流式状态 ──
function finalizeMsg() {
  const last = messages.value[messages.value.length - 1]
  if (last && last.streaming) {
    last.streaming = false
  }
}

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

// ── 监听 store 阶段变化 ──
watch(() => store.phase, (phase) => {
  if (phase === 'gating') {
    // parse + normalize 完成
    finalizeMsg()
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

    showSpecConfirm.value = true
    addMsg('assistant', '已解析出以下规格信息，请核对修正：')
  }

  if (phase === 'done') {
    finalizeMsg()
    isProcessing.value = false

    // SSE 流失败/断流: 只要没有任何可展示的结果,无论是否有 Agent 跑过,
    // 都把进度提示替换为错误消息（错误气泡自带重试按钮）
    const hasResult =
      !!store.chatResponse ||
      store.alternatives.length > 0 ||
      store.matchedSuppliers.length > 0 ||
      !!store.rfqDoc
    if (!hasResult && store.errors.length > 0) {
      replaceProgressWithError(store.streamError || store.errors[0] || '连接中断，请重试')
      return
    }

    // 纯聊天流（无寻源结果）→ 展示聊天内容
    // 注意：confirmSpec 的 match 阶段也可能有 chatResponse，但此时有 alternatives/suppliers，优先展示寻源结果
    if (store.chatResponse && !store.alternatives.length && !store.matchedSuppliers.length) {
      showChatResponse(store.chatResponse)
      return
    }

    // 保存历史到 localStorage 作为降级备份
    if (!store.isVague) {
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
        },
      })
      // 触发历史侧边栏刷新
      store.historyVersion++
    }

    // 分段展示所有结果
    if (store.alternatives.length) {
      addMsg('assistant', '找到以下替代料建议：')
      showAlternatives.value = true
    }
    if (store.matchedSuppliers.length) {
      addMsg('assistant', '以下供应商有相关供应能力（能力匹配，非现货承诺）：')
      showSuppliers.value = true
    }
    if (store.rfqDoc) {
      addMsg('assistant', '已为您生成询价单，可编辑后发送：')
      showRfq.value = true
    }
    if (store.leadGrade) {
      showGrade.value = true
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

// ── 规格确认回调 ──
function onSpecConfirm(spec: Record<string, SpecField>) {
  showSpecConfirm.value = false
  finalizeMsg()
  isProcessing.value = true
  addMsg('assistant', '规格已确认，正在查询替代料与匹配供应商…', { streaming: true, resultType: 'progress' })
  store.confirmSpec(spec)
}

// ── 供应商 → 询价单 ──
function onGenerateRfq() {
  showRfq.value = true
  addMsg('assistant', '以下是为您生成的询价单，可编辑：')
  scrollDown()
}

// ── 清理 ──
onUnmounted(() => store.abort())

// ── 监听流式结束（兜底: 强制 finalize）──
watch(() => store.isStreaming, (streaming) => {
  if (!streaming) {
    finalizeMsg()
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
  finalizeMsg()
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
          <!-- Agent 进度时间线 -->
          <div v-if="msg.resultType === 'progress' && msg === messages[messages.length - 1]" class="chat__timeline">
            <AgentTimeline
              :agents="store.agents"
              :alternatives-count="store.alternatives.length"
              :suppliers-count="store.matchedSuppliers.length"
            />
          </div>

          <!-- 规格确认：仅最后一条消息 -->
          <SpecConfirm
            v-if="msg === messages[messages.length - 1] && showSpecConfirm && store.normalizedSpec"
            :spec="store.normalizedSpec as Record<string, SpecField>"
            :gating="store.phase === 'gating'"
            @confirm="onSpecConfirm"
          />

          <!-- 替代料：仅最后一条消息 -->
          <AlternativesList
            v-if="msg === messages[messages.length - 1] && showAlternatives && store.alternatives.length"
            :alternatives="store.alternatives as Alternative[]"
            :original-part="(store.parsedSpec as any)?.['型号']?.value as string || ''"
            :original-brand="(store.parsedSpec as any)?.['品牌']?.value as string || ''"
          />

          <!-- 供应商：仅最后一条消息 -->
          <SuppliersMatch
            v-if="msg === messages[messages.length - 1] && showSuppliers && store.matchedSuppliers.length"
            :suppliers="store.matchedSuppliers as Supplier[]"
            :selected-ids="store.selectedSupplierIds"
            :streaming="false"
            :stream-progress="''"
            :error="null"
            @toggle="store.toggleSupplier"
            @select-all="store.selectAllSuppliers"
            @deselect-all="store.deselectAllSuppliers"
            @generate="onGenerateRfq"
            @retry="store.retryMatch()"
          />

          <!-- 询价单：仅最后一条消息 -->
          <RfqEditor
            v-if="msg === messages[messages.length - 1] && showRfq && store.rfqDoc"
            :rfq-doc="store.rfqDoc"
            :rfq-id="store.rfqId"
            :spec="store.normalizedSpec as Record<string, SpecField>"
            :alternatives="store.alternatives as Alternative[]"
            :suppliers="store.matchedSuppliers as Supplier[]"
            :selected-supplier-ids="store.selectedSupplierIds"
            :sent="store.rfqSent"
            :streaming="store.agents.find(a => a.name === 'gen_rfq')?.status === 'running'"
            @update="store.setRfqDoc"
            @sent="store.markRfqSent"
            @regenerate="store.regenerateRfq"
          />

          <!-- 线索分级：仅最后一条消息 -->
          <div v-if="msg === messages[messages.length - 1] && showGrade && store.leadGrade" class="grade-card">
            <div class="grade-card__head">
              <span class="grade-card__label">线索分级</span>
            </div>
            <div class="grade-card__body">
              <div class="grade-card__main">
                <span class="grade-letter" :class="`grade-${store.leadGrade.grade}`">
                  {{ store.leadGrade.grade }}
                </span>
                <span class="grade-score">{{ store.leadGrade.score }} 分</span>
                <Tag
                  :type="store.leadGrade.grade === 'A' || store.leadGrade.grade === 'B' ? 'success' : store.leadGrade.grade === 'C' ? 'warning' : 'danger'"
                  :value="`${store.leadGrade.grade} 级`"
                />
              </div>
              <ul class="grade-card__reasons">
                <li v-for="(r, ri) in store.leadGrade.reasons" :key="ri">{{ r }}</li>
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
      <SessionHistoryPanel @newChat="newChat" @close="showHistory = false" />
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
</style>
