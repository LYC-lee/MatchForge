<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useEnterpriseContext } from '@/composables/useEnterpriseContext'
import type { RelationCompany } from '@/mock/enterpriseContext'

const { current } = useEnterpriseContext()
const selectedId = ref<number | null>(null)
const mode = ref<'product' | 'business'>('product')
const query = ref('')
const sending = ref(false)
const chatBody = ref<HTMLElement | null>(null)
const messages = ref<{ role: 'user' | 'assistant'; content: string }[]>([])

const selectedRelation = computed<RelationCompany | undefined>(() =>
  current.value.relations.find((item) => item.id === (selectedId.value ?? current.value.relations[0]?.id)),
)

const quickQuestions = computed(() => {
  if (mode.value === 'product') return ['有哪些可供型号和规格？', 'MOQ、价格阶梯和交期分别是多少？', '是否有可替代型号？']
  return ['合作流程是什么？', '供货区域和售后责任怎么划分？', '付款方式和合同条款有哪些注意点？']
})

function selectRelation(id: number) {
  selectedId.value = id
  messages.value = []
}

function buildMockAnswer(text: string) {
  const relation = selectedRelation.value
  if (!relation) return '请先选择一个直接上下游企业。'
  const scope = relation.scope.join('、')
  return `这是 ${current.value.company.name} 与直接${relation.direction}企业 ${relation.name} 的协同问答。当前只围绕 ${scope} 等授权协同范围回答。关于“${text}”，建议先确认 ${relation.products} 的交期、责任边界和是否需要 RFQ/合同补充条款。`
}

async function send(q?: string) {
  const text = (q ?? query.value).trim()
  if (!text || sending.value || !selectedRelation.value) return
  query.value = ''
  messages.value.push({ role: 'user', content: text })
  sending.value = true
  await scrollBottom()
  window.setTimeout(async () => {
    messages.value.push({ role: 'assistant', content: buildMockAnswer(text) })
    sending.value = false
    await scrollBottom()
  }, 260)
}

async function scrollBottom() {
  await nextTick()
  if (chatBody.value) chatBody.value.scrollTop = chatBody.value.scrollHeight
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
      <div class="relation-list">
        <button
          v-for="relation in current.relations"
          :key="relation.id"
          class="relation-item"
          :class="{ active: selectedRelation?.id === relation.id }"
          @click="selectRelation(relation.id)"
        >
          <div>
            <b>{{ relation.name }}</b>
            <span>{{ relation.direction }} · {{ relation.segment }}</span>
          </div>
          <small>{{ relation.products }}</small>
        </button>
      </div>
    </aside>

    <section class="chat-main">
      <header class="chat-header">
        <div>
          <span class="eyebrow">上下游协同问答</span>
          <h1>{{ selectedRelation?.name || '请选择协同对象' }}</h1>
          <p v-if="selectedRelation">
            {{ selectedRelation.direction }} · {{ selectedRelation.segment }} · 范围：{{ selectedRelation.scope.join('、') }}
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
            <p>协同问答是 AI 基于企业知识的问答，不是真人聊天。</p>
            <div class="quick-questions">
              <button v-for="item in quickQuestions" :key="item" class="chip" @click="send(item)">{{ item }}</button>
            </div>
          </div>
          <div v-for="(message, index) in messages" :key="index" class="msg" :class="`msg--${message.role}`">
            <div class="msg__avatar">{{ message.role === 'user' ? '我' : 'AI' }}</div>
            <div class="msg__content">{{ message.content }}</div>
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
            @keydown.enter="send()"
          />
          <button class="btn-send" :disabled="sending || !query.trim() || !selectedRelation" @click="send()">发送</button>
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
}
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
  .chat-page { grid-template-columns: 1fr; height: auto; }
}
@media (max-width: 640px) {
  .chat-header { flex-direction: column; }
}
</style>
