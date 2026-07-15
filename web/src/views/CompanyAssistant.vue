<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  getCompanies, getCompanyDetail, getCompanyKnowledge, chatSingle,
  type CompanyListItem, type CompanyDetail, type ChatResult, type RetrievedChunk,
} from '@/api/kb'

const route = useRoute()
const router = useRouter()

const companies = ref<CompanyListItem[]>([])
const search = ref('')
const current = ref<CompanyDetail | null>(null)
const knowledge = ref<any>(null)
const loadingCompany = ref(false)

const query = ref('')
const messages = ref<{ role: 'user' | 'assistant'; content: string; intent?: string; retrieved?: RetrievedChunk[] }[]>([])
const sending = ref(false)
const chatBody = ref<HTMLElement | null>(null)

const filteredCompanies = computed(() => {
  const kw = search.value.trim().toLowerCase()
  if (!kw) return companies.value
  return companies.value.filter(
    (c) => c.name.toLowerCase().includes(kw) || (c.name_en || '').toLowerCase().includes(kw),
  )
})

async function loadCompanies() {
  const res = await getCompanies()
  companies.value = res.data.items
}

async function selectCompany(id: number) {
  router.replace({ query: { ...route.query, company_id: String(id) } })
  await loadCompany(id)
}

async function loadCompany(id: number) {
  loadingCompany.value = true
  try {
    const [d, k] = await Promise.all([getCompanyDetail(id), getCompanyKnowledge(id)])
    current.value = d.data
    knowledge.value = k.data
    messages.value = []
  } catch (e: any) {
    messages.value = [{ role: 'assistant', content: `加载公司失败: ${e?.message || e}` }]
  } finally {
    loadingCompany.value = false
  }
}

const quickQuestions = computed(() => [
  '你们有哪些产品型号？',
  '主力产品的价格区间是多少？',
  '最小起订量和交期是多久？',
  '业务合作流程是怎样的？',
  'How to start a procurement?',
])

async function send(q?: string) {
  const text = (q ?? query.value).trim()
  if (!text || !current.value || sending.value) return
  query.value = ''
  messages.value.push({ role: 'user', content: text })
  sending.value = true
  await scrollBottom()
  try {
    const res = await chatSingle(current.value.id, text)
    const r: ChatResult = res.data
    const retrieved = Array.isArray(r.retrieved) ? (r.retrieved as RetrievedChunk[]) : []
    messages.value.push({ role: 'assistant', content: r.answer, intent: r.intent, retrieved })
  } catch (e: any) {
    messages.value.push({ role: 'assistant', content: `查询失败: ${e?.message || e}` })
  } finally {
    sending.value = false
    await scrollBottom()
  }
}

async function scrollBottom() {
  await nextTick()
  if (chatBody.value) chatBody.value.scrollTop = chatBody.value.scrollHeight
}

function statusLabel(s: string) {
  return ({ none: '未生成', partial: '部分', ready: '就绪' } as Record<string, string>)[s] || s
}

onMounted(async () => {
  await loadCompanies()
  const id = Number(route.query.company_id) || companies.value[0]?.id
  if (id) await loadCompany(id)
})

watch(() => route.query.company_id, (v) => {
  if (v && Number(v) !== current.value?.id) loadCompany(Number(v))
})
</script>

<template>
  <div class="assistant-page">
    <aside class="company-list">
      <div class="company-list__head">
        <h3>企业知识库</h3>
        <span class="muted small">{{ companies.length }} 家公司</span>
      </div>
      <div class="company-list__search">
        <input v-model="search" placeholder="搜索公司…" class="input" />
      </div>
      <div class="company-list__items">
        <button
          v-for="c in filteredCompanies"
          :key="c.id"
          class="company-item"
          :class="{ active: current?.id === c.id }"
          @click="selectCompany(c.id)"
        >
          <div class="company-item__name">{{ c.name }}</div>
          <div class="company-item__meta">
            <span class="tag">{{ c.segment_name || c.segment_code || '-' }}</span>
            <span class="dot" :class="`dot--${c.knowledge_status}`" />
            <span class="muted small">{{ statusLabel(c.knowledge_status) }}</span>
          </div>
        </button>
      </div>
    </aside>

    <section class="assistant-main">
      <template v-if="current">
        <header class="company-header">
          <div>
            <h2>{{ current.name }}</h2>
            <p v-if="current.name_en" class="muted small">{{ current.name_en }}</p>
          </div>
          <div class="company-header__tags">
            <span class="tag">{{ current.segment_name || '-' }}</span>
            <span class="tag">{{ current.role || '-' }}</span>
            <span class="tag" :class="{ ok: current.knowledge_status === 'ready' }">
              知识{{ statusLabel(current.knowledge_status) }}
            </span>
            <a v-if="current.website" :href="current.website" target="_blank" class="link">官网 ↗</a>
          </div>
        </header>

        <div class="company-desc" v-if="current.description">
          <span class="muted small">公司简介</span>
          <p>{{ current.description }}</p>
        </div>

        <div class="kb-summary" v-if="knowledge">
          <div class="kb-summary__item">
            <span class="muted small">切片总数</span>
            <b>{{ knowledge.chunk_count }}</b>
          </div>
          <div class="kb-summary__item">
            <span class="muted small">产品数</span>
            <b>{{ knowledge.product_count }}</b>
          </div>
          <div class="kb-summary__item" v-for="(_, k) in knowledge.manuals" :key="k">
            <span class="muted small">{{ k }}</span>
            <b class="muted small" style="font-weight:400">✓ 就绪</b>
          </div>
        </div>

        <div class="chat-panel">
          <div class="chat-body" ref="chatBody">
            <div v-if="!messages.length" class="chat-empty">
              <div class="chat-empty__icon">🤖</div>
              <p>这是 <b>{{ current.name }}</b> 的私域 AI 助手。</p>
              <p class="muted small">问答严格限制在当前公司知识范围内，不会跨公司检索。</p>
              <div class="quick-questions">
                <button v-for="q in quickQuestions" :key="q" class="chip" @click="send(q)">{{ q }}</button>
              </div>
            </div>
            <div v-for="(m, i) in messages" :key="i" class="msg" :class="`msg--${m.role}`">
              <div class="msg__avatar">{{ m.role === 'user' ? '我' : 'AI' }}</div>
              <div class="msg__body">
                <div class="msg__content">{{ m.content }}</div>
                <div class="msg__meta" v-if="m.role === 'assistant'">
                  <span v-if="m.intent" class="tag tag--intent">{{ m.intent }}</span>
                  <span v-if="m.retrieved?.length" class="muted small">
                    引用 {{ m.retrieved.length }} 条知识 · 最高分 {{ Math.max(...m.retrieved.map((r) => r.score)).toFixed(3) }}
                  </span>
                </div>
              </div>
            </div>
            <div v-if="sending" class="msg msg--assistant">
              <div class="msg__avatar">AI</div>
              <div class="msg__body"><div class="typing">正在检索企业知识库…</div></div>
            </div>
          </div>
          <div class="chat-input">
            <input
              v-model="query"
              placeholder="向当前企业提问（产品/型号/价格/规格/采购/业务流程）…"
              @keydown.enter="send()"
              :disabled="sending"
              class="input"
            />
            <button class="btn-send" @click="send()" :disabled="sending || !query.trim()">发送</button>
          </div>
        </div>
      </template>
      <div v-else class="empty-state">请从左侧选择一家企业</div>
    </section>
  </div>
</template>

<style scoped>
.assistant-page {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: var(--space-5);
  padding: var(--space-5);
  height: calc(100vh - 56px);
}
.company-list {
  display: flex;
  flex-direction: column;
  background: var(--bg-1);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.company-list__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4);
  border-bottom: 1px solid var(--border-subtle);
}
.company-list__head h3 { font-size: var(--font-size-md); }
.company-list__search { padding: var(--space-2) var(--space-4) var(--space-3); }
.company-list__items { flex: 1; overflow-y: auto; padding: var(--space-2); }
.company-item {
  display: block;
  width: 100%;
  text-align: left;
  padding: var(--space-3);
  margin-bottom: var(--space-1);
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}
.company-item:hover { background: var(--bg-2); color: var(--text-primary); }
.company-item.active {
  background: var(--bg-2);
  border-color: var(--accent-border);
  color: var(--text-primary);
  box-shadow: var(--shadow-glow);
}
.company-item__name { font-size: var(--font-size-sm); font-weight: 600; margin-bottom: 4px; }
.company-item__meta { display: flex; align-items: center; gap: var(--space-2); }
.dot { width: 7px; height: 7px; border-radius: 50%; background: var(--text-tertiary); }
.dot--ready { background: var(--success); }
.dot--partial { background: var(--warning); }
.assistant-main { display: flex; flex-direction: column; gap: var(--space-4); overflow: hidden; }
.company-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  background: var(--bg-1);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: var(--space-4) var(--space-5);
}
.company-header h2 { font-size: var(--font-size-xl); }
.company-header__tags { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: center; }
.tag {
  font-size: var(--font-size-xs);
  padding: 3px 8px;
  border-radius: var(--radius-full);
  background: var(--bg-3);
  color: var(--text-secondary);
  border: 1px solid var(--border-subtle);
}
.tag.ok { color: var(--success); border-color: rgba(34, 197, 94, 0.3); }
.tag--intent { color: var(--accent-hover); border-color: var(--accent-border); }
.link { font-size: var(--font-size-xs); color: var(--accent-hover); }
.muted { color: var(--text-tertiary); }
.small { font-size: var(--font-size-xs); }
.company-desc {
  background: var(--bg-1);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: var(--space-3) var(--space-5);
}
.company-desc p { margin-top: 4px; color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.6; }
.kb-summary {
  display: flex;
  gap: var(--space-4);
  flex-wrap: wrap;
  padding: var(--space-3) var(--space-5);
  background: var(--bg-1);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
}
.kb-summary__item { display: flex; flex-direction: column; }
.kb-summary__item b { font-size: var(--font-size-md); color: var(--text-primary); }
.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--bg-1);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  overflow: hidden;
  min-height: 0;
}
.chat-body { flex: 1; overflow-y: auto; padding: var(--space-4); }
.chat-empty { text-align: center; padding: var(--space-8) var(--space-4); color: var(--text-secondary); }
.chat-empty__icon { font-size: 40px; margin-bottom: var(--space-3); }
.quick-questions { display: flex; flex-direction: column; gap: var(--space-2); align-items: center; margin-top: var(--space-4); }
.chip {
  font-size: var(--font-size-sm);
  padding: 6px 14px;
  border-radius: var(--radius-full);
  background: var(--bg-2);
  border: 1px solid var(--border-default);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}
.chip:hover { border-color: var(--accent-border); color: var(--text-primary); }
.msg { display: flex; gap: var(--space-3); margin-bottom: var(--space-4); }
.msg__avatar {
  width: 30px; height: 30px; flex: 0 0 auto;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: var(--font-size-xs); font-weight: 700;
  background: var(--bg-3); color: var(--text-secondary);
}
.msg--user .msg__avatar { background: var(--gradient-accent); color: #fff; }
.msg__body { flex: 1; }
.msg__content {
  background: var(--bg-2);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  font-size: var(--font-size-sm);
  line-height: 1.7;
  color: var(--text-primary);
  white-space: pre-wrap;
}
.msg--user .msg__content { background: var(--accent-soft); border-color: var(--accent-border); }
.msg__meta { display: flex; gap: var(--space-2); align-items: center; margin-top: 6px; }
.typing { color: var(--text-tertiary); font-size: var(--font-size-sm); padding: var(--space-3); }
.chat-input {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}
.input {
  flex: 1;
  background: var(--bg-2);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: 10px 12px;
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  outline: none;
}
.input:focus { border-color: var(--accent-border); }
.btn-send {
  padding: 0 20px;
  border-radius: var(--radius-md);
  border: none;
  background: var(--gradient-accent);
  color: #fff;
  font-size: var(--font-size-sm);
  font-weight: 600;
  cursor: pointer;
}
.btn-send:disabled { opacity: 0.5; cursor: not-allowed; }
.empty-state {
  display: flex; align-items: center; justify-content: center;
  color: var(--text-tertiary); font-size: var(--font-size-md);
  height: 100%;
}
@media (max-width: 920px) {
  .assistant-page { grid-template-columns: 1fr; height: auto; }
  .company-list { max-height: 240px; }
}
</style>
