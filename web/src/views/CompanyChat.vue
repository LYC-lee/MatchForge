<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { getChatPartners, partnerChat, type ChatPartner } from '@/api/enterprise'
import { mapRetrievedToCitations } from '@/api/kb'
import { useEnterpriseContext } from '@/composables/useEnterpriseContext'
import { useProgressiveReveal } from '@/composables/useProgressiveReveal'
import MarkdownContent from '@/components/chat/MarkdownContent.vue'
import CitationList from '@/components/chat/CitationList.vue'
import type { Citation } from '@/types/procure'

const { current, currentEnterpriseId } = useEnterpriseContext()
const partners = ref<ChatPartner[]>([])
const selectedId = ref<number | null>(null)
const mode = ref<'product' | 'business'>('product')
const query = ref('')
const sending = ref(false)
const chatBody = ref<HTMLElement | null>(null)
const messages = ref<{ role: 'user' | 'assistant'; content: string; source?: 'api' | 'error'; citations?: Citation[]; streaming?: boolean }[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

// kb 协同问答接口暂无流式后端,完整答案到达后客户端渐进式 reveal (过渡方案,见 useProgressiveReveal)
const { revealing, start: startReveal, stop: stopReveal } = useProgressiveReveal()
/** 渐进式 reveal 的文本目标,绑定到最后一条 assistant 消息 */
const revealText = ref('')
let revealMsg: { content: string; streaming?: boolean } | null = null
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

function selectPartner(id: number) {
  selectedId.value = id
  stopRevealing()
  messages.value = []
}

async function send(q?: string) {
  const text = (q ?? query.value).trim()
  if (!text || busy.value || !selectedPartner.value) return
  query.value = ''
  messages.value.push({ role: 'user', content: text })
  sending.value = true
  await scrollBottom()

  try {
    const res = await partnerChat(currentEnterpriseId.value, {
      partner_company_id: selectedPartner.value.company_id,
      query: text,
      scope: mode.value,
    })
    const answer = res.data?.answer || res.data?.response || res.data?.message
    // 引用回显: partner-chat 检索伙伴私域知识, company_id 缺省回退为伙伴 id
    const citations = mapRetrievedToCitations(
      res.data?.retrieved,
      selectedPartner.value?.company_id ?? currentEnterpriseId.value,
    )
    const msg = {
      role: 'assistant' as const,
      content: '',
      source: (answer ? 'api' : 'error') as 'api' | 'error',
      citations: citations.length ? citations : undefined,
      streaming: true,
    }
    messages.value.push(msg)
    revealMsg = msg
    // 渐进式 reveal: 逐帧写入 revealText → msg.content,期间显示光标
    await startReveal(revealText, answer || '伙伴企业知识库暂未返回答案，请换个问法再试。')
    msg.streaming = false
    revealMsg = null
  } catch (e: any) {
    const detail = e?.response?.status === 403
      ? '当前企业只能与直接上下游或支撑企业协同问答。'
      : '当前无法连接上下游协同知识库，请确认后端 RAG 服务、企业关系和认证状态是否正常。'
    messages.value.push({ role: 'assistant', content: detail, source: 'error' })
  } finally {
    sending.value = false
    await scrollBottom()
  }
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

async function scrollBottom() {
  await nextTick()
  if (chatBody.value) chatBody.value.scrollTop = chatBody.value.scrollHeight
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
    </aside>

    <section class="chat-main">
      <header class="chat-header">
        <div>
          <span class="eyebrow">上下游协同问答</span>
          <h1>{{ selectedPartner?.company_name || '请选择协同对象' }}</h1>
          <p v-if="selectedPartner">
            {{ directionLabel(selectedPartner.direction) }} · {{ selectedPartner.segment_name || selectedPartner.role }}
            · 范围：{{ mode === 'product' ? selectedPartner.product_scope.join('、') : selectedPartner.business_scope.join('、') }}
          </p>
        </div>
        <div class="mode-switch">
          <button :class="{ active: mode === 'product' }" @click="mode = 'product'">产品方面</button>
          <button :class="{ active: mode === 'business' }" @click="mode = 'business'">业务方面</button>
        </div>
      </header>

      <div class="chat-panel">
        <div class="chat-body" ref="chatBody">
          <div v-if="!messages.length" class="chat-empty">
            <p>协同问答是 AI 基于伙伴企业私域知识的问答，不是真人聊天。</p>
            <div class="quick-questions">
              <button v-for="item in quickQuestions" :key="item" class="chip" @click="send(item)">{{ item }}</button>
            </div>
          </div>
          <div v-for="(message, index) in messages" :key="index" class="msg" :class="`msg--${message.role}`">
            <div class="msg__avatar">{{ message.role === 'user' ? '我' : 'AI' }}</div>
            <div class="msg__body">
              <div class="msg__content" :class="{ 'msg__content--md': message.role === 'assistant' }">
                <MarkdownContent v-if="message.role === 'assistant'" :content="message.content" :streaming="message.streaming" />
                <template v-else>{{ message.content }}</template>
                <span v-if="message.streaming" class="msg__cursor">▌</span>
                <template v-if="!message.streaming">
                  <span v-if="message.source === 'api' && !message.citations?.length" class="msg__source msg__source--api">RAG</span>
                  <span v-else-if="message.source === 'error'" class="msg__source">未生成</span>
                </template>
              </div>
              <CitationList
                v-if="message.role === 'assistant' && !message.streaming && message.citations?.length"
                class="msg__citations"
                :citations="message.citations"
              />
            </div>
          </div>
          <div v-if="sending" class="msg msg--assistant">
            <div class="msg__avatar">AI</div>
            <div class="msg__content muted">正在检索直接上下游协同知识...</div>
          </div>
        </div>

        <div class="chat-input">
          <input
            v-model="query"
            class="input"
            :placeholder="mode === 'product' ? '询问型号、规格、价格、MOQ、交期、替代品...' : '询问合作流程、合同条款、售后、付款方式...'"
            :disabled="busy"
            @keydown.enter="send()"
          />
          <button v-if="revealing" class="btn-send btn-send--stop" @click="stopRevealing"><span class="stop-icon" />停止</button>
          <button v-else class="btn-send" :disabled="busy || !query.trim() || !selectedPartner" @click="send()">{{ sending ? '发送中…' : '发送' }}</button>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.chat-page {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: var(--space-4);
  height: calc(100vh - 56px);
  padding: var(--space-5);
}
.relation-panel,
.chat-header,
.chat-panel {
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  background: #10131b;
}
.relation-panel { overflow: hidden; }
.panel-head { padding: var(--space-4); border-bottom: 1px solid var(--border-default); }
.eyebrow { color: #aab3c4; font-size: var(--font-size-xs); font-weight: 700; }
h1,
h2 { color: var(--text-primary); }
.panel-head h2 { font-size: var(--font-size-lg); margin-top: 4px; }
.panel-head p,
.chat-header p { margin-top: 6px; color: #c7cfdd; font-size: var(--font-size-sm); line-height: 1.6; }
.loading-line { padding: var(--space-3) var(--space-4); color: var(--text-tertiary); font-size: var(--font-size-sm); text-align: center; }
.relation-list { display: grid; gap: var(--space-1); padding: var(--space-2); }
.relation-item {
  display: grid;
  gap: 5px;
  width: 100%;
  text-align: left;
  padding: var(--space-3);
  border: 1px solid transparent;
  border-radius: 6px;
  color: #c7cfdd;
  background: none;
  cursor: pointer;
}
.relation-item:hover,
.relation-item.active { background: #171b26; border-color: var(--border-default); }
.relation-item.active { border-color: var(--accent-border); }
.relation-item b { display: block; color: var(--text-primary); font-size: var(--font-size-sm); }
.relation-item span,
.relation-item small { color: #aeb7c8; font-size: var(--font-size-xs); }
.chat-main { display: flex; flex-direction: column; gap: var(--space-4); overflow: hidden; }
.chat-header {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  align-items: flex-start;
  padding: var(--space-4);
}
.chat-header h1 { font-size: var(--font-size-xl); margin-top: 4px; }
.mode-switch {
  display: inline-flex;
  gap: 4px;
  padding: 3px;
  border: 1px solid var(--border-default);
  border-radius: 6px;
  background: var(--bg-2);
}
.mode-switch button {
  padding: 6px 10px;
  border-radius: 4px;
  color: #c7cfdd;
  font-size: var(--font-size-xs);
  background: none;
  border: none;
  cursor: pointer;
}
.mode-switch button.active { color: var(--text-primary); background: var(--bg-3); }
.chat-panel { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.chat-body { flex: 1; overflow-y: auto; padding: var(--space-4); }
.chat-empty { color: #d2d8e4; font-size: var(--font-size-sm); }
.quick-questions { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-4); }
.chip {
  border: 1px solid var(--border-default);
  background: #171b26;
  color: #d8deea;
  border-radius: 999px;
  padding: 5px 9px;
  font-size: var(--font-size-xs);
  cursor: pointer;
}
.chip:hover { border-color: var(--accent-border); color: var(--text-primary); }
.msg { display: flex; gap: var(--space-3); margin-bottom: var(--space-3); }
.msg__body { flex: 1; min-width: 0; }
.msg__citations { margin-top: var(--space-1); padding: 0 var(--space-1); }
.msg__avatar {
  width: 30px;
  height: 30px;
  flex: 0 0 auto;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-3);
  color: #d8deea;
  font-size: var(--font-size-xs);
  font-weight: 700;
}
.msg--user .msg__avatar { color: #fff; background: var(--gradient-accent); }
.msg__content {
  flex: 1;
  padding: var(--space-3);
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-2);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  line-height: 1.7;
  white-space: pre-wrap;
}
/* Markdown 内容自行管理换行,不再保留 pre-wrap */
.msg__content--md {
  white-space: normal;
}
.muted { color: #aeb7c8; }
.msg__source {
  display: inline-block;
  margin-left: 8px;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  color: var(--warning);
  background: var(--warning-soft);
  border: 1px solid rgba(234, 179, 8, 0.3);
  vertical-align: middle;
}
.msg__source--api { color: var(--success); background: var(--success-soft); border-color: rgba(34, 197, 94, 0.3); }
.chat-input {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}
.input {
  flex: 1;
  min-width: 0;
  background: var(--bg-2);
  border: 1px solid var(--border-strong);
  border-radius: 6px;
  padding: 10px 12px;
  color: var(--text-primary);
  font-size: var(--font-size-sm);
}
.input::placeholder { color: #9fa8ba; }
.input:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-send {
  padding: 0 18px;
  border-radius: 6px;
  background: var(--gradient-accent);
  color: #fff;
  font-size: var(--font-size-sm);
  font-weight: 600;
  border: none;
  cursor: pointer;
}
.btn-send:disabled { opacity: 0.5; cursor: not-allowed; }
/* 流式光标 (与 ChatView / CompanyAssistant 一致) */
.msg__cursor {
  animation: blink 0.8s step-end infinite;
  color: var(--accent);
}
@keyframes blink {
  50% { opacity: 0; }
}
/* 停止键 (与 ChatView 一致: 方形图标) */
.btn-send--stop {
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
@media (max-width: 920px) {
  .chat-page { grid-template-columns: 1fr; height: auto; }
}
@media (max-width: 640px) {
  .chat-header { flex-direction: column; }
}
</style>
