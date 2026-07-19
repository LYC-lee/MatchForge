<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { chatAsk } from '@/api/enterprise'
import { mapRetrievedToCitations } from '@/api/kb'
import { useEnterpriseContext } from '@/composables/useEnterpriseContext'
import { useProgressiveReveal } from '@/composables/useProgressiveReveal'
import ChatMessage, { type ChatMessageData } from '@/components/chat/ChatMessage.vue'
import ChatInput from '@/components/chat/ChatInput.vue'

const { current, currentEnterpriseId } = useEnterpriseContext()
const query = ref('')
const sending = ref(false)
const chatBody = ref<HTMLElement | null>(null)
const messages = ref<ChatMessageData[]>([])
let msgId = 0
function uid() { return `ca-${++msgId}` }

// kb 问答接口暂无流式后端,完整答案到达后客户端渐进式 reveal (过渡方案,见 useProgressiveReveal)
const { revealing, start: startReveal, stop: stopReveal } = useProgressiveReveal()
/** 渐进式 reveal 的文本目标,绑定到最后一条 assistant 消息 */
const revealText = ref('')
let revealMsg: ChatMessageData | null = null
const busy = computed(() => sending.value || revealing.value)

const quickQuestions = computed(() => [
  '当前缺件会影响哪些订单？',
  '哪些产品本周可以优先生产？',
  '请给我一份采购、生产、销售联动建议。',
  `${current.value.company.name} 的人事入职流程是什么？`,
])

// 切换企业后清空旧会话：避免上一企业的问答残留串到下一企业
watch(currentEnterpriseId, () => {
  stopRevealing()
  messages.value = []
})

async function send(q?: string) {
  const text = (q ?? query.value).trim()
  // 快照发送时的企业：在途响应按快照归属
  const enterpriseId = currentEnterpriseId.value
  if (!text || busy.value) return
  query.value = ''
  messages.value.push({ id: uid(), role: 'user', content: text, timestamp: Date.now() })
  sending.value = true
  await scrollBottom(true)

  try {
    const res = await chatAsk(enterpriseId, text)
    // 响应返回时企业已切换：丢弃，避免串会话
    if (currentEnterpriseId.value !== enterpriseId) return
    const answer = res.data?.answer || res.data?.response || res.data?.message
    // 引用回显: 答案附带的 retrieved 检索片段 → Citation[](契约 C2)
    const citations = mapRetrievedToCitations(res.data?.retrieved, enterpriseId)
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
    await startReveal(revealText, answer || '企业知识库暂未返回答案，请换个问法再试。')
    msg.streaming = false
    if (!answer) msg.content = '企业知识库暂未返回答案，请换个问法再试。'
    revealMsg = null
  } catch {
    if (currentEnterpriseId.value !== enterpriseId) return
    messages.value.push({
      id: uid(),
      role: 'assistant',
      content: '当前无法连接企业知识库，请确认后端 RAG 服务、向量库和认证状态是否正常。',
      resultType: 'error',
      timestamp: Date.now(),
    })
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

      <div class="chat-body" ref="chatBody" role="log" aria-live="polite" @scroll.passive="onChatScroll">
        <div v-if="!messages.length" class="chat-empty">
          <p>我是 {{ current.company.name }} 的内部 AI 助手，基于企业私域知识库回答问题。</p>
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
          :message="{ id: '__pending', role: 'assistant', content: '正在检索企业私域知识…', resultType: 'progress' }"
        />
      </div>

      <div class="chat-input-bar">
        <ChatInput
          v-model="query"
          :busy="busy"
          placeholder="向当前企业内部 AI 助手提问…"
          menu-label="常用问题"
          @send="send()"
          @stop="stopRevealing"
        >
          <template #menu>
            <p class="chat-menu-title">常用问题</p>
            <button v-for="item in quickQuestions" :key="item" type="button" class="chat-menu-item" @click="send(item)">
              {{ item }}
            </button>
          </template>
        </ChatInput>
        <p class="chat-hint">Enter 发送 · Shift+Enter 换行</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.assistant-page {
  --chat-col: 800px;
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: var(--space-4);
  height: calc(100vh - var(--header-h));
  padding: var(--space-5);
}
.scope-panel,
.chat-panel {
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  background: var(--bg-surface);
}
.scope-panel {
  padding: var(--space-4);
  overflow-y: auto;
}
.eyebrow {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  font-weight: 700;
}
.scope-panel h2 {
  color: var(--text-primary);
  font-size: var(--font-size-xl);
  line-height: var(--leading-xl);
  margin-top: var(--space-2);
}
.scope-panel p {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  margin-top: var(--space-2);
}
.scope-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-4);
}
.scope-list span,
.chip {
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  color: var(--text-secondary);
  border-radius: var(--radius-full);
  padding: var(--space-1) var(--space-3);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
}
.boundary {
  margin-top: var(--space-4);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  border: 1px solid var(--accent-border);
  background: var(--accent-soft);
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
}
.chat-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.chat-header {
  padding: var(--space-4);
  border-bottom: 1px solid var(--border-subtle);
}
.chat-header h1 {
  color: var(--text-primary);
  font-size: var(--font-size-xl);
  line-height: var(--leading-xl);
  margin-top: var(--space-1);
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
  .assistant-page {
    grid-template-columns: 1fr;
    height: auto;
  }
  .chat-panel {
    min-height: 60vh;
  }
}
</style>
