<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { chatAsk } from '@/api/enterprise'
import { mapRetrievedToCitations } from '@/api/kb'
import { useEnterpriseContext } from '@/composables/useEnterpriseContext'
import { useProgressiveReveal } from '@/composables/useProgressiveReveal'
import MarkdownContent from '@/components/chat/MarkdownContent.vue'
import CitationList from '@/components/chat/CitationList.vue'
import type { Citation } from '@/types/procure'

const { current, currentEnterpriseId } = useEnterpriseContext()
const query = ref('')
const sending = ref(false)
const chatBody = ref<HTMLElement | null>(null)
const messages = ref<{ role: 'user' | 'assistant'; content: string; source?: 'api' | 'error'; citations?: Citation[]; streaming?: boolean }[]>([])

// kb 问答接口暂无流式后端,完整答案到达后客户端渐进式 reveal (过渡方案,见 useProgressiveReveal)
const { revealing, start: startReveal, stop: stopReveal } = useProgressiveReveal()
/** 渐进式 reveal 的文本目标,绑定到最后一条 assistant 消息 */
const revealText = ref('')
let revealMsg: { content: string; streaming?: boolean } | null = null
const busy = computed(() => sending.value || revealing.value)

const quickQuestions = computed(() => [
  '当前缺件会影响哪些订单？',
  '哪些产品本周可以优先生产？',
  '请给我一份采购、生产、销售联动建议。',
  `${current.value.company.name} 的人事入职流程是什么？`,
])

async function send(q?: string) {
  const text = (q ?? query.value).trim()
  if (!text || busy.value) return
  query.value = ''
  messages.value.push({ role: 'user', content: text })
  sending.value = true
  await scrollBottom()

  try {
    const res = await chatAsk(currentEnterpriseId.value, text)
    const answer = res.data?.answer || res.data?.response || res.data?.message
    // 引用回显: 答案附带的 retrieved 检索片段 → Citation[](契约 C2)
    const citations = mapRetrievedToCitations(res.data?.retrieved, currentEnterpriseId.value)
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
    await startReveal(revealText, answer || '企业知识库暂未返回答案，请换个问法再试。')
    msg.streaming = false
    revealMsg = null
  } catch {
    messages.value.push({
      role: 'assistant',
      content: '当前无法连接企业知识库，请确认后端 RAG 服务、向量库和认证状态是否正常。',
      source: 'error',
    })
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
        只回答当前企业内部范围的问题，不跨企业检索；跨企业协同请使用“上下游协同问答”。
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
          <p>我是 {{ current.company.name }} 的内部 AI 助手，基于企业私域知识库回答问题。</p>
          <div class="quick-questions">
            <button v-for="item in quickQuestions" :key="item" class="chip" @click="send(item)">{{ item }}</button>
          </div>
        </div>
        <div v-for="(message, index) in messages" :key="index" class="msg" :class="`msg--${message.role}`">
          <div class="msg__avatar">{{ message.role === 'user' ? '我' : 'AI' }}</div>
          <div class="msg__wrapper">
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
          <div class="msg__wrapper">
            <div class="msg__content muted">正在检索企业私域知识...</div>
          </div>
        </div>
      </div>

      <div class="chat-input">
        <input v-model="query" class="input" placeholder="向当前企业内部 AI 助手提问..." :disabled="busy" @keydown.enter="send()" />
        <button v-if="revealing" class="btn-send btn-send--stop" @click="stopRevealing"><span class="stop-icon" />停止</button>
        <button v-else class="btn-send" :disabled="busy || !query.trim()" @click="send()">{{ sending ? '发送中…' : '发送' }}</button>
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
.msg--user { flex-direction: row-reverse; }
.msg--user .msg__wrapper { align-items: flex-end; }
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
.msg__wrapper {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  max-width: 640px;
}
.msg__content {
  padding: var(--space-3);
  border-radius: 8px;
  background: var(--bg-2);
  border: 1px solid var(--border-default);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  line-height: 1.7;
  white-space: pre-wrap;
}
.msg--user .msg__content {
  background: var(--accent-soft);
  border-color: var(--accent-border);
  border-radius: 8px 8px 0 8px;
}
.msg--assistant .msg__content {
  border-radius: 8px 8px 8px 0;
}
/* Markdown 内容自行管理换行,不再保留 pre-wrap */
.msg__content--md {
  white-space: normal;
}
.muted { color: #aeb7c8; }
.msg__citations {
  margin-top: var(--space-1);
  padding: 0 var(--space-1);
  max-width: 640px;
}
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
.input:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-send {
  padding: 0 18px;
  border-radius: 6px;
  background: var(--gradient-accent);
  color: #fff;
  font-size: var(--font-size-sm);
  font-weight: 600;
}
.btn-send:disabled { opacity: 0.5; cursor: not-allowed; }
/* 流式光标 (与 ChatView / CompanyChat 一致) */
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
  .assistant-page { grid-template-columns: 1fr; height: auto; }
}
</style>
