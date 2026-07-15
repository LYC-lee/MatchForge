<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import {
  getCompanies, chatSingle, chatCompare,
  type CompanyListItem, type ChatResult, type RetrievedChunk,
} from '@/api/kb'

const companies = ref<CompanyListItem[]>([])
const search = ref('')
const selected = ref<number[]>([])  // 选中的公司
const mode = ref<'single' | 'compare'>('single')

const query = ref('')
const messages = ref<{ role: 'user' | 'assistant'; content: string; intent?: string; mode?: string; retrieved?: any[] }[]>([])
const sending = ref(false)
const chatBody = ref<HTMLElement | null>(null)

const filteredCompanies = computed(() => {
  const kw = search.value.trim().toLowerCase()
  if (!kw) return companies.value
  return companies.value.filter(
    (c) => c.name.toLowerCase().includes(kw) || (c.name_en || '').toLowerCase().includes(kw),
  )
})

const selectedCompanies = computed(() =>
  selected.value.map((id) => companies.value.find((c) => c.id === id)).filter(Boolean) as CompanyListItem[],
)

const canSend = computed(() => {
  if (sending.value || !query.value.trim()) return false
  if (mode.value === 'single') return selected.value.length === 1
  return selected.value.length >= 2
})

function toggleCompany(id: number) {
  const idx = selected.value.indexOf(id)
  if (mode.value === 'single') {
    selected.value = idx >= 0 ? [] : [id]
  } else {
    if (idx >= 0) selected.value.splice(idx, 1)
    else if (selected.value.length < 6) selected.value.push(id)
  }
}

function switchMode(m: 'single' | 'compare') {
  mode.value = m
  if (m === 'single' && selected.value.length > 1) selected.value = selected.value.slice(0, 1)
}

async function send() {
  const text = query.value.trim()
  if (!text || !canSend.value) return
  query.value = ''
  messages.value.push({ role: 'user', content: text })
  sending.value = true
  await scrollBottom()
  try {
    let r: ChatResult
    if (mode.value === 'single') {
      r = (await chatSingle(selected.value[0], text)).data
    } else {
      r = (await chatCompare(selected.value, text)).data
    }
    const retrieved = Array.isArray(r.retrieved) ? (r.retrieved as RetrievedChunk[]) : []
    messages.value.push({
      role: 'assistant',
      content: r.answer,
      intent: r.intent,
      mode: r.mode,
      retrieved,
    })
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

onMounted(async () => {
  const res = await getCompanies()
  companies.value = res.data.items
})
</script>

<template>
  <div class="chat-page">
    <aside class="picker">
      <div class="picker__head">
        <h3>全局企业问答</h3>
      </div>
      <div class="mode-switch">
        <button :class="{ active: mode === 'single' }" @click="switchMode('single')">单企业问答</button>
        <button :class="{ active: mode === 'compare' }" @click="switchMode('compare')">产品对比</button>
      </div>
      <div class="picker__hint muted small">
        {{ mode === 'single' ? '选择 1 家企业进行私域问答' : '选择 2-6 家企业进行产品对比' }}
      </div>
      <div class="picker__search">
        <input v-model="search" placeholder="搜索公司…" class="input" />
      </div>
      <div class="picker__items">
        <button
          v-for="c in filteredCompanies"
          :key="c.id"
          class="company-item"
          :class="{ active: selected.includes(c.id) }"
          @click="toggleCompany(c.id)"
        >
          <div class="company-item__row">
            <span class="company-item__name">{{ c.name }}</span>
            <span v-if="selected.includes(c.id)" class="check">✓</span>
          </div>
          <span class="tag small">{{ c.segment_name || c.segment_code || '-' }}</span>
        </button>
      </div>
      <div class="picker__selected" v-if="selectedCompanies.length">
        <div class="muted small">已选 ({{ selectedCompanies.length }})</div>
        <div class="selected-chips">
          <span v-for="c in selectedCompanies" :key="c.id" class="selected-chip" @click="toggleCompany(c.id)">
            {{ c.name }} ✕
          </span>
        </div>
      </div>
    </aside>

    <section class="chat-main">
      <header class="chat-header">
        <div>
          <h2>{{ mode === 'single' ? '单企业 AI 问答' : '多企业产品对比' }}</h2>
          <p class="muted small">
            <template v-if="selectedCompanies.length">
              当前范围：{{ selectedCompanies.map((c) => c.name).join(' · ') }}
            </template>
            <template v-else>请从左侧选择企业</template>
          </p>
        </div>
        <span class="tag tag--scope" v-if="mode === 'compare'">分别检索 · 不全库搜索</span>
      </header>

      <div class="chat-panel">
        <div class="chat-body" ref="chatBody">
          <div v-if="!messages.length" class="chat-empty">
            <div class="chat-empty__icon">💬</div>
            <p v-if="mode === 'single'">选择一家企业后，提出你的问题。</p>
            <p v-else>选择多家企业后，对它们的产品进行对比。</p>
            <p class="muted small">中文提问优先检索中文知识，英文提问优先检索英文知识。</p>
          </div>
          <div v-for="(m, i) in messages" :key="i" class="msg" :class="`msg--${m.role}`">
            <div class="msg__avatar">{{ m.role === 'user' ? '我' : 'AI' }}</div>
            <div class="msg__body">
              <div class="msg__content">{{ m.content }}</div>
              <div class="msg__meta" v-if="m.role === 'assistant'">
                <span v-if="m.intent" class="tag tag--intent">{{ m.intent }}</span>
                <span v-if="m.mode" class="tag">{{ m.mode }}</span>
                <span v-if="m.retrieved?.length" class="muted small">引用 {{ m.retrieved.length }} 条</span>
              </div>
            </div>
          </div>
          <div v-if="sending" class="msg msg--assistant">
            <div class="msg__avatar">AI</div>
            <div class="msg__body"><div class="typing">{{ mode === 'compare' ? '正在分别检索各公司知识…' : '正在检索企业知识库…' }}</div></div>
          </div>
        </div>
        <div class="chat-input">
          <input
            v-model="query"
            :placeholder="mode === 'single' ? '向选中企业提问…' : '输入产品对比问题，如：对比三家的MLCC型号和价格'"
            @keydown.enter="send()"
            :disabled="sending || !canSend"
            class="input"
          />
          <button class="btn-send" @click="send()" :disabled="!canSend">发送</button>
        </div>
        <div class="chat-foot muted small" v-if="!canSend && query.trim()">
          {{ mode === 'single' ? '请选择 1 家企业' : '请选择至少 2 家企业' }}
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.chat-page {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: var(--space-5);
  padding: var(--space-5);
  height: calc(100vh - 56px);
}
.picker {
  display: flex;
  flex-direction: column;
  background: var(--bg-1);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.picker__head { padding: var(--space-4); border-bottom: 1px solid var(--border-subtle); }
.picker__head h3 { font-size: var(--font-size-md); }
.mode-switch { display: flex; gap: 4px; padding: var(--space-2) var(--space-4); }
.mode-switch button {
  flex: 1;
  padding: 7px;
  font-size: var(--font-size-xs);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-default);
  background: var(--bg-2);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}
.mode-switch button.active {
  background: var(--accent-soft);
  border-color: var(--accent-border);
  color: var(--text-primary);
}
.picker__hint { padding: 0 var(--space-4) var(--space-2); }
.picker__search { padding: var(--space-2) var(--space-4) var(--space-2); }
.picker__items { flex: 1; overflow-y: auto; padding: var(--space-2); }
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
}
.company-item__row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.company-item__name { font-size: var(--font-size-sm); font-weight: 600; }
.check { color: var(--success); font-weight: 700; }
.tag {
  font-size: var(--font-size-xs);
  padding: 2px 7px;
  border-radius: var(--radius-full);
  background: var(--bg-3);
  color: var(--text-secondary);
  border: 1px solid var(--border-subtle);
}
.small { font-size: var(--font-size-xs); }
.tag--intent { color: var(--accent-hover); border-color: var(--accent-border); }
.tag--scope { color: var(--warning); border-color: rgba(234, 179, 8, 0.3); }
.picker__selected { padding: var(--space-3); border-top: 1px solid var(--border-subtle); }
.selected-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
.selected-chip {
  font-size: var(--font-size-xs);
  padding: 3px 8px;
  border-radius: var(--radius-full);
  background: var(--accent-soft);
  border: 1px solid var(--accent-border);
  color: var(--text-primary);
  cursor: pointer;
}
.muted { color: var(--text-tertiary); }
.chat-main { display: flex; flex-direction: column; gap: var(--space-4); overflow: hidden; }
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  background: var(--bg-1);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: var(--space-4) var(--space-5);
}
.chat-header h2 { font-size: var(--font-size-xl); }
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
.msg { display: flex; gap: var(--space-3); margin-bottom: var(--space-4); }
.msg__avatar {
  width: 30px; height: 30px; flex: 0 0 auto;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: var(--font-size-xs); font-weight: 700;
  background: var(--bg-3); color: var(--text-secondary);
}
.msg--user .msg__avatar { background: var(--gradient-accent); color: #fff; }
.msg__body { flex: 1; min-width: 0; }
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
.msg__meta { display: flex; gap: var(--space-2); align-items: center; margin-top: 6px; flex-wrap: wrap; }
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
.chat-foot { padding: 0 var(--space-4) var(--space-2); }
@media (max-width: 920px) {
  .chat-page { grid-template-columns: 1fr; height: auto; }
  .picker { max-height: 280px; }
}
</style>
