<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useEnterpriseContext } from '@/composables/useEnterpriseContext'
import { chatAsk } from '@/api/enterprise'
import { useDashboard } from '@/composables/useDashboard'
import { useMockInternalQuestions } from '@/composables/useDashboard'

const { current, currentEnterpriseId } = useEnterpriseContext()
const { dashboard } = useDashboard()
const query = ref('')
const sending = ref(false)
const chatBody = ref<HTMLElement | null>(null)
const messages = ref<{ role: 'user' | 'assistant'; content: string; source?: 'api' | 'mock' }[]>([])

const quickQuestions = computed(() => {
  const mockQ = useMockInternalQuestions(currentEnterpriseId.value)
  return [
    ...mockQ,
    '当前缺件会影响哪些订单？',
    '哪些产品本周可以优先生产？',
    '请给我一份采购、生产、销售联动建议。',
  ]
})

function buildFallbackAnswer(text: string) {
  const shortages = (dashboard.value?.shortages?.items || []).slice(0, 2).map((item) => `${item.part_name || item.part_number} 缺口 ${item.shortage_qty}`).join('；')
  const orders = (dashboard.value?.orders_summary?.items || []).filter((o) => o.priority === 'urgent' || o.priority === 'high').map((o) => o.order_number).join('、')
  return `基于 ${current.value.company.name} 的当前经营数据, 建议先处理 ${orders || '高风险订单'}。关键风险是: ${shortages || '暂无缺件'}。下一步可按"先保紧急订单、再锁预测需求、同步上下游承诺"的顺序推进。你刚才问的是: "${text}"。(后端 RAG 不可用, 此为本地降级回答)`
}

async function send(q?: string) {
  const text = (q ?? query.value).trim()
  if (!text || sending.value) return
  query.value = ''
  messages.value.push({ role: 'user', content: text })
  sending.value = true
  await scrollBottom()

  try {
    const res = await chatAsk(currentEnterpriseId.value, text)
    const answer = res.data?.answer || res.data?.response || res.data?.message
    if (answer) {
      messages.value.push({ role: 'assistant', content: answer, source: 'api' })
    } else {
      messages.value.push({ role: 'assistant', content: buildFallbackAnswer(text), source: 'mock' })
    }
  } catch {
    messages.value.push({ role: 'assistant', content: buildFallbackAnswer(text), source: 'mock' })
  } finally {
    sending.value = false
    await scrollBottom()
  }
}

async function scrollBottom() {
  await nextTick()
  if (chatBody.value) chatBody.value.scrollTop = chatBody.value.scrollHeight
}
</script>

<template>
  <div class="assistant-page">
    <aside class="scope-panel">
      <span class="eyebrow">当前企业内部 AI 助手</span>
      <h2>{{ current.company.name }}</h2>
      <p>{{ current.role || current.company.description }}</p>
      <div class="scope-list">
        <span>库存</span>
        <span>订单</span>
        <span>BOM</span>
        <span>产能</span>
        <span>合同</span>
        <span>财务</span>
        <span>人事</span>
        <span>制度流程</span>
      </div>
      <div class="boundary">
        只回答当前企业内部范围的问题, 不跨企业检索; 跨企业协同请使用"上下游协同问答"。
      </div>
    </aside>

    <section class="chat-panel">
      <header class="chat-header">
        <div>
          <span class="eyebrow">企业私域知识</span>
          <h1>问库存、订单、BOM、产能和经营流程</h1>
        </div>
      </header>

      <div class="chat-body" ref="chatBody">
        <div v-if="!messages.length" class="chat-empty">
          <p>我是 {{ current.company.name }} 的内部 AI 助手, 基于企业私域知识库 (RAG) 回答问题。后端不可用时降级到本地数据。</p>
          <div class="quick-questions">
            <button v-for="item in quickQuestions" :key="item" class="chip" @click="send(item)">{{ item }}</button>
          </div>
        </div>
        <div v-for="(message, index) in messages" :key="index" class="msg" :class="`msg--${message.role}`">
          <div class="msg__avatar">{{ message.role === 'user' ? '我' : 'AI' }}</div>
          <div class="msg__content">
            {{ message.content }}
            <span v-if="message.source === 'mock'" class="msg__source">本地降级</span>
            <span v-else-if="message.source === 'api'" class="msg__source msg__source--api">RAG</span>
          </div>
        </div>
        <div v-if="sending" class="msg msg--assistant">
          <div class="msg__avatar">AI</div>
          <div class="msg__content muted">正在检索企业私域知识...</div>
        </div>
      </div>

      <div class="chat-input">
        <input v-model="query" class="input" placeholder="向当前企业内部 AI 助手提问..." @keydown.enter="send()" />
        <button class="btn-send" :disabled="sending || !query.trim()" @click="send()">发送</button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.assistant-page {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: var(--space-4);
  height: calc(100vh - 56px);
  padding: var(--space-5);
}
.scope-panel,
.chat-panel {
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  background: #10131b;
}
.scope-panel { padding: var(--space-4); }
.eyebrow { color: #aab3c4; font-size: var(--font-size-xs); font-weight: 700; }
.scope-panel h2 { color: var(--text-primary); font-size: var(--font-size-xl); margin-top: 6px; }
.scope-panel p { color: #c7cfdd; font-size: var(--font-size-sm); margin-top: 6px; line-height: 1.6; }
.scope-list { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-4); }
.scope-list span,
.chip {
  border: 1px solid var(--border-default);
  background: #171b26;
  color: #d8deea;
  border-radius: 999px;
  padding: 5px 9px;
  font-size: var(--font-size-xs);
}
.boundary {
  margin-top: var(--space-4);
  padding: var(--space-3);
  border-radius: 6px;
  border: 1px solid var(--accent-border);
  background: var(--accent-soft);
  color: #d8deea;
  font-size: var(--font-size-xs);
  line-height: 1.6;
}
.chat-panel { display: flex; flex-direction: column; overflow: hidden; }
.chat-header { padding: var(--space-4); border-bottom: 1px solid var(--border-default); }
.chat-header h1 { color: var(--text-primary); font-size: var(--font-size-xl); margin-top: 4px; }
.chat-body { flex: 1; overflow-y: auto; padding: var(--space-4); }
.chat-empty { color: #d2d8e4; font-size: var(--font-size-sm); }
.quick-questions { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-4); }
.chip { cursor: pointer; }
.chip:hover { border-color: var(--accent-border); color: var(--text-primary); }
.msg { display: flex; gap: var(--space-3); margin-bottom: var(--space-3); }
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
  border-top: 1px solid var(--border-default);
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
.btn-send {
  padding: 0 18px;
  border-radius: 6px;
  background: var(--gradient-accent);
  color: #fff;
  font-size: var(--font-size-sm);
  font-weight: 600;
}
.btn-send:disabled { opacity: 0.5; cursor: not-allowed; }
@media (max-width: 920px) {
  .assistant-page { grid-template-columns: 1fr; height: auto; }
}
</style>
