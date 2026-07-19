<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { getChatPartners, partnerChat, type ChatPartner } from '@/api/enterprise'
import { mapRetrievedToCitations } from '@/api/kb'
import { useEnterpriseContext } from '@/composables/useEnterpriseContext'
import { useProgressiveReveal } from '@/composables/useProgressiveReveal'
import ChatMessage, { type ChatMessageData } from '@/components/chat/ChatMessage.vue'
import ChatInput from '@/components/chat/ChatInput.vue'

const { current, currentEnterpriseId } = useEnterpriseContext()
const partners = ref<ChatPartner[]>([])
const selectedId = ref<number | null>(null)
const mode = ref<'product' | 'business'>('product')
const query = ref('')
const sending = ref(false)
const chatBody = ref<HTMLElement | null>(null)
const messages = ref<ChatMessageData[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
let msgId = 0
function uid() { return `cc-${++msgId}` }

// kb 协同问答接口暂无流式后端,完整答案到达后客户端渐进式 reveal (过渡方案,见 useProgressiveReveal)
const { revealing, start: startReveal, stop: stopReveal } = useProgressiveReveal()
/** 渐进式 reveal 的文本目标,绑定到最后一条 assistant 消息 */
const revealText = ref('')
let revealMsg: ChatMessageData | null = null
const busy = computed(() => sending.value || revealing.value)

async function fetchPartners(companyId: number) {
  loading.value = true
  error.value = null
  try {
    const res = await getChatPartners(companyId)
    partners.value = (res.data?.items || []) as ChatPartner[]
    selectedId.value = partners.value[0]?.company_id || null
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '协同伙伴接口不可用'
    partners.value = []
    selectedId.value = null
  } finally {
    loading.value = false
  }
}

watch(currentEnterpriseId, (id) => {
  if (!id) return
  stopRevealing()
  messages.value = []
  fetchPartners(id)
}, { immediate: true })

const selectedPartner = computed<ChatPartner | undefined>(() =>
  partners.value.find((p) => p.company_id === selectedId.value),
)

const quickQuestions = computed(() => {
  if (mode.value === 'product') return ['有哪些可供型号和规格？', 'MOQ、价格阶梯和交期分别是多少？', '是否有可替代型号？']
  return ['合作流程是什么？', '供货区域和售后责任怎么划分？', '付款方式和合同条款有哪些注意点？']
})

/** 切换伙伴：在途响应期间阻断（busy 守卫），避免回答归属错乱 */
function selectPartner(id: number) {
  if (busy.value || id === selectedId.value) return
  selectedId.value = id
  stopRevealing()
  messages.value = []
}

async function send(q?: string) {
  const text = (q ?? query.value).trim()
  // 快照发送时的企业与伙伴：在途响应按快照归属，不受后续切换影响
  const partner = selectedPartner.value
  const enterpriseId = currentEnterpriseId.value
  if (!text || busy.value || !partner) return
  query.value = ''
  messages.value.push({ id: uid(), role: 'user', content: text, timestamp: Date.now() })
  sending.value = true
  await scrollBottom(true)

  try {
    const res = await partnerChat(enterpriseId, {
      partner_company_id: partner.company_id,
      query: text,
      scope: mode.value,
    })
    // 响应返回时企业已切换：丢弃，避免串会话
    if (currentEnterpriseId.value !== enterpriseId) return
    const answer = res.data?.answer || res.data?.response || res.data?.message
    // 引用回显: partner-chat 检索伙伴私域知识, company_id 缺省回退为伙伴 id
    const citations = mapRetrievedToCitations(res.data?.retrieved, partner.company_id)
    const msg: ChatMessageData = {
      id: uid(),
      role: 'assistant',
      content: '',
      resultType: answer ? undefined : 'error',
      citations: citations.length ? citations : undefined,
      streaming: true,
      timestamp: Date.now(),
    }
    messages.value.push(msg)
    revealMsg = msg
    // 渐进式 reveal: 逐帧写入 revealText → msg.content,期间显示光标
    await startReveal(revealText, answer || '伙伴企业知识库暂未返回答案，请换个问法再试。')
    msg.streaming = false
    if (!answer) msg.content = '伙伴企业知识库暂未返回答案，请换个问法再试。'
    revealMsg = null
  } catch (e: any) {
    if (currentEnterpriseId.value !== enterpriseId) return
    const detail = e?.response?.status === 403
      ? '当前企业只能与直接上下游或支撑企业协同问答。'
      : '当前无法连接上下游协同知识库，请确认后端 RAG 服务、企业关系和认证状态是否正常。'
    messages.value.push({ id: uid(), role: 'assistant', content: detail, resultType: 'error', timestamp: Date.now() })
  } finally {
    sending.value = false
    await scrollBottom()
  }
}

/** 重试 / 重新生成：重发最后一条用户消息 */
function retryLast() {
  const lastUser = [...messages.value].reverse().find((m) => m.role === 'user')
  if (lastUser) send(lastUser.content)
}

/** 停止渐进式展示: 保留已 reveal 的部分文本,光标消失,输入框恢复 */
function stopRevealing() {
  stopReveal()
  if (revealMsg) {
    revealMsg.streaming = false
    revealMsg = null
  }
}

// revealText 同步到最后一条 assistant 消息 (reveal 期间每帧滚动)
watch(revealText, async (text) => {
  if (revealMsg) {
    revealMsg.content = text
    await scrollBottom()
  }
})

onUnmounted(() => stopReveal())

// ── 自动滚动：用户上翻时不强制拉回；自己发消息时强制到底 ──
const stickToBottom = ref(true)
function onChatScroll() {
  const el = chatBody.value
  if (!el) return
  stickToBottom.value = el.scrollHeight - el.scrollTop - el.clientHeight < 80
}
async function scrollBottom(force = false) {
  await nextTick()
  const el = chatBody.value
  if (el && (force || stickToBottom.value)) el.scrollTop = el.scrollHeight
}

function directionLabel(direction: string) {
  return { upstream: '上游', downstream: '下游', support: '支撑' }[direction] || direction
}
</script>

<template>
  <div class="chat-page">
    <aside class="relation-panel">
      <div class="panel-head">
        <span class="eyebrow">{{ current.company.name }}</span>
        <h2>直接上下游</h2>
        <p>只能选择与当前企业直接相关的企业，不能全链路任意选择。</p>
      </div>
      <div v-if="loading" class="loading-line">加载协同伙伴中...</div>
      <div v-else-if="error" class="loading-line">协同伙伴接口不可用：{{ error }}</div>
      <div v-else class="relation-list">
        <button
          v-for="partner in partners"
          :key="partner.company_id"
          class="relation-item"
          :class="{ active: selectedPartner?.company_id === partner.company_id }"
          :disabled="busy"
          @click="selectPartner(partner.company_id)"
        >
          <div>
            <b>{{ partner.company_name }}</b>
            <span>{{ directionLabel(partner.direction) }} · {{ partner.segment_name || partner.role }}</span>
          </div>
          <small>{{ partner.product_scope.join('、') }}</small>
        </button>
        <div v-if="!partners.length" class="loading-line">当前企业暂无直接上下游</div>
      </div>
      <p v-if="busy" class="switch-hint">正在生成回答，完成后可切换协同对象。</p>
    </aside>

    <section class="chat-main">
      <header class="chat-header">
        <div>
          <span class="eyebrow">上下游协同问答 · {{ mode === 'product' ? '产品方面' : '业务方面' }}</span>
          <h1>{{ selectedPartner?.company_name || '请选择协同对象' }}</h1>
          <p v-if="selectedPartner">
            {{ directionLabel(selectedPartner.direction) }} · {{ selectedPartner.segment_name || selectedPartner.role }}
            · 范围：{{ mode === 'product' ? selectedPartner.product_scope.join('、') : selectedPartner.business_scope.join('、') }}
          </p>
        </div>
      </header>

      <div class="chat-panel">
        <div class="chat-body" ref="chatBody" role="log" aria-live="polite" @scroll.passive="onChatScroll">
          <div v-if="!messages.length" class="chat-empty">
            <p>协同问答是 AI 基于伙伴企业私域知识的问答，不是真人聊天。</p>
            <div class="quick-questions">
              <button v-for="item in quickQuestions" :key="item" class="chip" @click="send(item)">{{ item }}</button>
            </div>
          </div>
          <ChatMessage
            v-for="message in messages"
            :key="message.id"
            :message="message"
            @retry="retryLast"
            @regenerate="retryLast"
          />
          <ChatMessage
            v-if="sending"
            :message="{ id: '__pending', role: 'assistant', content: '正在检索直接上下游协同知识…', resultType: 'progress' }"
          />
        </div>

        <div class="chat-input-bar">
          <ChatInput
            v-model="query"
            :busy="busy"
            :disabled="!selectedPartner"
            :placeholder="mode === 'product' ? '询问型号、规格、价格、MOQ、交期、替代品…' : '询问合作流程、合同条款、售后、付款方式…'"
            menu-label="问答范围与常用问题"
            @send="send()"
            @stop="stopRevealing"
          >
            <template #menu>
              <p class="chat-menu-title">问答范围</p>
              <button type="button" class="chat-menu-item" :class="{ 'chat-menu-item--active': mode === 'product' }" @click="mode = 'product'">
                产品方面<span v-if="mode === 'product'" class="chat-menu-item__check">✓</span>
              </button>
              <button type="button" class="chat-menu-item" :class="{ 'chat-menu-item--active': mode === 'business' }" @click="mode = 'business'">
                业务方面<span v-if="mode === 'business'" class="chat-menu-item__check">✓</span>
              </button>
              <p class="chat-menu-title">常用问题</p>
              <button v-for="item in quickQuestions" :key="item" type="button" class="chat-menu-item" @click="send(item)">
                {{ item }}
              </button>
            </template>
          </ChatInput>
          <p class="chat-hint">Enter 发送 · Shift+Enter 换行</p>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.chat-page {
  --chat-col: 800px;
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: var(--space-4);
  height: calc(100vh - var(--header-h));
  padding: var(--space-5);
}
.relation-panel,
.chat-header,
.chat-panel {
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  background: var(--bg-surface);
}
.relation-panel {
  overflow-y: auto;
}
.panel-head {
  padding: var(--space-4);
  border-bottom: 1px solid var(--border-subtle);
}
.eyebrow {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  font-weight: 700;
}
h1,
h2 {
  color: var(--text-primary);
}
.panel-head h2 {
  font-size: var(--font-size-lg);
  line-height: var(--leading-lg);
  margin-top: var(--space-1);
}
.panel-head p,
.chat-header p {
  margin-top: var(--space-2);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
}
.loading-line {
  padding: var(--space-3) var(--space-4);
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  text-align: center;
}
.relation-list {
  display: grid;
  gap: var(--space-1);
  padding: var(--space-2);
}
.relation-item {
  display: grid;
  gap: var(--space-1);
  width: 100%;
  text-align: left;
  padding: var(--space-3);
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  background: none;
  cursor: pointer;
  transition: background-color var(--transition-fast), border-color var(--transition-fast);
}
.relation-item:hover:not(:disabled),
.relation-item.active {
  background: var(--bg-subtle);
  border-color: var(--border-default);
}
.relation-item.active {
  border-color: var(--accent-border);
}
.relation-item:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
.relation-item b {
  display: block;
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
}
.relation-item span,
.relation-item small {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
}
.switch-hint {
  margin: 0 var(--space-3) var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  color: var(--warning);
  background: var(--warning-soft);
  border: 1px solid var(--warning-border);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
}
.chat-main {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  overflow: hidden;
}
.chat-header {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  align-items: flex-start;
  padding: var(--space-4);
}
.chat-header h1 {
  font-size: var(--font-size-xl);
  line-height: var(--leading-xl);
  margin-top: var(--space-1);
}
.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4) 0;
}
.chat-empty {
  max-width: var(--chat-col);
  margin: 0 auto;
  padding: var(--space-6) var(--space-4);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  text-align: center;
}
.quick-questions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  justify-content: center;
  margin-top: var(--space-4);
}
.chip {
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  color: var(--text-secondary);
  border-radius: var(--radius-full);
  padding: var(--space-1) var(--space-3);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  cursor: pointer;
  transition: color var(--transition-fast), border-color var(--transition-fast), background-color var(--transition-fast);
}
.chip:hover {
  border-color: var(--accent-border);
  color: var(--accent-text);
  background: var(--accent-soft);
}
.chat-input-bar {
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--border-subtle);
}
.chat-input-bar :deep(.chat-input) {
  max-width: var(--chat-col);
  margin: 0 auto;
}
.chat-hint {
  max-width: var(--chat-col);
  margin: var(--space-2) auto 0;
  text-align: center;
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  color: var(--text-tertiary);
}
@media (max-width: 920px) {
  .chat-page {
    grid-template-columns: 1fr;
    height: auto;
  }
  .chat-panel {
    min-height: 60vh;
  }
}
</style>
