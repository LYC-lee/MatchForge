<script setup lang="ts">
import { ref, nextTick, watch, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useProcureStore } from '@/stores/procure'
import { useHistory, type HistoryRecord } from '@/composables/useHistory'
import type { SpecField, Alternative, Supplier } from '@/types/procure'
import ChatMessage, { type ChatMessageData } from '@/components/chat/ChatMessage.vue'
import SpecConfirm from '@/components/procure/SpecConfirm.vue'
import AlternativesList from '@/components/procure/AlternativesList.vue'
import SuppliersMatch from '@/components/procure/SuppliersMatch.vue'
import RfqEditor from '@/components/procure/RfqEditor.vue'
import Tag from '@/components/ui/Tag.vue'

const router = useRouter()
const store = useProcureStore()
const { saveRecord } = useHistory()

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
  addMsg('assistant', '正在解析需求…', { streaming: true, resultType: 'progress' })
  store.startProcure(q)
}

function resetResultFlags() {
  showSpecConfirm.value = false
  showAlternatives.value = false
  showSuppliers.value = false
  showRfq.value = false
  showGrade.value = false
}

// ── 进度 → 更新最后一条 AI 消息 ──
function updateProgressText(label: string) {
  const last = messages.value[messages.value.length - 1]
  if (last && last.role === 'assistant' && last.streaming) {
    last.content = label
    scrollDown()
  }
}

// ── 终结流式状态 ──
function finalizeMsg() {
  const last = messages.value[messages.value.length - 1]
  if (last && last.streaming) {
    last.streaming = false
  }
}

// ── 监听 store 阶段变化 ──
watch(() => store.phase, (phase) => {
  if (phase === 'gating') {
    // parse + normalize 完成
    finalizeMsg()
    isProcessing.value = false

    if (!store.parsedSpec || store.errors.length > 0) {
      // 解析失败
      addMsg('assistant', store.errors[0] || '未能识别到有效型号，请补充更多信息。', { resultType: 'error' })
      return
    }

    showSpecConfirm.value = true
    addMsg('assistant', '已解析出以下规格信息，请核对修正：')
  }

  if (phase === 'done') {
    finalizeMsg()
    isProcessing.value = false

    // 保存历史
    if (!store.isVague) {
      saveRecord({
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
      } as HistoryRecord)
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
  const labels: Record<string, string> = {
    parse: '正在识别型号与参数…',
    normalize: '正在标准化规格…',
    alternatives: '正在查询替代料…',
    match: '正在匹配供应商…',
    gen_rfq: '正在生成询价单…',
    grade: '正在评估线索…',
  }
  const last = p[p.length - 1]
  if (last.status === 'running') {
    updateProgressText(labels[last.agent] || '处理中…')
  }
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

// ── 示例 ──
const examples = [
  'TMK212BJ105KG-T 缺货，找替代',
  '0805 10uF X7R 50V MLCC，月用量50万，要国巨或华新科',
  '寻找 GRM188R61A106KE69D 的替代料',
]
</script>

<template>
  <div class="chat-view">
    <!-- 消息列表 -->
    <div ref="chatContainer" class="chat__msgs">
      <!-- 空态 -->
      <div v-if="messages.length === 0" class="chat__welcome">
        <div class="welcome__mark">M</div>
        <h1 class="welcome__title">对话寻源</h1>
        <p class="welcome__sub">输入型号或需求描述，AI 自动解析、推荐替代料、匹配供应商</p>
        <div class="welcome__examples">
          <button v-for="ex in examples" :key="ex" class="welcome__chip" @click="inputText = ex">
            {{ ex }}
          </button>
        </div>
      </div>

      <!-- 消息 -->
      <template v-for="msg in messages" :key="msg.id">
        <ChatMessage :message="msg">
          <!-- 规格确认 -->
          <SpecConfirm
            v-if="showSpecConfirm && store.normalizedSpec"
            :spec="store.normalizedSpec as Record<string, SpecField>"
            :gating="store.phase === 'gating'"
            @confirm="onSpecConfirm"
          />

          <!-- 替代料 -->
          <AlternativesList
            v-if="showAlternatives && store.alternatives.length"
            :alternatives="store.alternatives as Alternative[]"
            :original-part="(store.parsedSpec as any)?.['型号']?.value as string || ''"
            :original-brand="(store.parsedSpec as any)?.['品牌']?.value as string || ''"
          />

          <!-- 供应商 -->
          <SuppliersMatch
            v-if="showSuppliers && store.matchedSuppliers.length"
            :suppliers="store.matchedSuppliers as Supplier[]"
            :selected-ids="store.selectedSupplierIds"
            @toggle="store.toggleSupplier"
            @generate="onGenerateRfq"
          />

          <!-- 询价单 -->
          <RfqEditor
            v-if="showRfq && store.rfqDoc"
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
          />

          <!-- 线索分级 -->
          <div v-if="showGrade && store.leadGrade" class="grade-card">
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
      <div class="chat__input-wrap">
        <textarea
          v-model="inputText"
          class="chat__input"
          rows="1"
          placeholder="输入型号或需求描述…"
          :disabled="isProcessing"
          @keydown="handleKeydown"
        />
        <button class="chat__send" :disabled="!inputText.trim() || isProcessing" @click="send">
          <span v-if="isProcessing" class="send-spinner" />
          <span v-else>发送</span>
        </button>
      </div>
      <p class="chat__hint">Enter 发送 · Shift+Enter 换行</p>
    </div>
  </div>
</template>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 56px);
  max-width: 900px;
  margin: 0 auto;
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
.send-spinner {
  display: block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
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
</style>
