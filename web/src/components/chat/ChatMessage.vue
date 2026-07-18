<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import MarkdownContent from '@/components/chat/MarkdownContent.vue'
import CitationList from '@/components/chat/CitationList.vue'
import type { AgentState, Alternative, Citation, LeadGrade, SpecField, Supplier } from '@/types/procure'

export type MessageRole = 'user' | 'assistant' | 'system'

/**
 * 单条消息携带的结构化结果快照 (#28)。
 * 生成中的活跃消息从 store 实时取数; 新轮次开始 / 会话重建时把数据冻结进
 * payload, 卡片随消息持久, 追问时上一轮卡片不再消失。
 */
export interface TurnPayload {
  parsedSpec?: Record<string, SpecField> | null
  normalizedSpec?: Record<string, SpecField> | null
  alternatives?: Alternative[]
  originalPart?: string
  originalBrand?: string
  matchedSuppliers?: Supplier[]
  selectedSupplierIds?: string[]
  rfqDoc?: string
  rfqId?: string | null
  rfqSent?: boolean
  leadGrade?: LeadGrade | null
  /** AgentTimeline 沉淀: 本轮 Agent 执行状态快照(生成完成时冻结, 默认折叠回看) */
  agents?: AgentState[]
  alternativesCount?: number
  suppliersCount?: number
}

export interface ChatMessageData {
  id: string
  role: MessageRole
  content: string
  streaming?: boolean
  /** 结构化结果类型,非纯文本时标识内容类型 */
  resultType?: 'spec' | 'alternatives' | 'suppliers' | 'rfq' | 'grade' | 'error' | 'progress'
  timestamp?: number
  /** 引用回显(C2): 助手消息附带的 RAG 引用片段 */
  citations?: Citation[]
  /** 所属轮次 id, 与 ChatView.activeTurnId 相同者为当前活跃轮(可交互) */
  turnId?: number
  /** 冻结标记: true 时卡片从 payload 只读渲染, 不再跟随 store 变化 */
  frozen?: boolean
  /** 冻结的卡片/时间线数据快照 */
  payload?: TurnPayload
}

const props = defineProps<{
  message: ChatMessageData
}>()

const emit = defineEmits<{
  /** 错误消息上的重试 */
  (e: 'retry'): void
  /** 以同一条用户输入重新发起 */
  (e: 'regenerate'): void
}>()

const isUser = computed(() => props.message.role === 'user')
const isSystem = computed(() => props.message.role === 'system')
const isStreaming = computed(() => props.message.streaming)
const isError = computed(() => props.message.resultType === 'error')
const isProgress = computed(() => props.message.resultType === 'progress')
// 仅助手常规消息渲染 Markdown;用户/系统/错误/进度消息保持纯文本
const renderMarkdown = computed(
  () => !isUser.value && !isSystem.value && !isError.value && !isProgress.value,
)
// Perplexity 式溯源: 助手消息带 citations 时,底部展示「N 条依据」汇总行,点击展开引用面板
const citations = computed(() => props.message.citations ?? [])
const showCitations = computed(() => !isUser.value && !isSystem.value && citations.value.length > 0)
const sourcesOpen = ref(false)

const displayContent = computed(() => {
  let text = props.message.content
  if (isStreaming.value && !text) return '⋯'
  return text
})

// ── 时间戳 HH:mm ──
const timeLabel = computed(() => {
  const t = props.message.timestamp
  if (!t) return ''
  const d = new Date(t)
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${hh}:${mm}`
})

// ── 复制（原始 markdown 文本）──
const copied = ref(false)
let copyTimer: ReturnType<typeof setTimeout> | undefined

async function copyContent() {
  const text = props.message.content
  let ok = false
  try {
    await navigator.clipboard.writeText(text)
    ok = true
  } catch {
    // 兜底: execCommand（非安全上下文 / 权限被拒时）
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    try {
      ok = document.execCommand('copy')
    } catch {
      ok = false
    }
    document.body.removeChild(ta)
  }
  if (!ok) return
  copied.value = true
  clearTimeout(copyTimer)
  copyTimer = setTimeout(() => { copied.value = false }, 1500)
}

onUnmounted(() => clearTimeout(copyTimer))

// ── 消息级操作的显示条件 ──
// 复制: 助手消息且有实际内容（复制原始文本而非渲染后 HTML）
const showCopy = computed(
  () => !isUser.value && !isSystem.value && !isStreaming.value && !isProgress.value && !!props.message.content,
)
// 重新生成: 助手的纯文本消息（非结构化卡片、非错误、非进度、非流式占位）
const showRegenerate = computed(
  () =>
    !isUser.value &&
    !isSystem.value &&
    !isStreaming.value &&
    !isError.value &&
    !isProgress.value &&
    !props.message.resultType &&
    !!props.message.content &&
    props.message.content !== '思考中…',
)
const showActions = computed(() => showCopy.value || showRegenerate.value || isError.value)
</script>

<template>
  <div
    class="msg"
    :class="{
      'msg--user': isUser,
      'msg--assistant': !isUser && !isSystem,
      'msg--system': isSystem,
      'msg--streaming': isStreaming,
      'msg--error': isError,
      'msg--progress': isProgress,
    }"
  >
    <!-- 头像：渐变 = AI（全站统一语义），用户 = 中性 -->
    <div class="msg__avatar" aria-hidden="true">
      <span v-if="isUser" class="avatar--user">{{ 'U' }}</span>
      <span v-else-if="isSystem" class="avatar--system">●</span>
      <span v-else class="avatar--ai">M</span>
    </div>

    <div class="msg__bubble">
      <!-- 错误气泡：role="alert" 即时播报 -->
      <div
        v-if="displayContent"
        class="msg__text"
        :class="{ 'msg__text--typing': isStreaming, 'msg__text--md': renderMarkdown }"
        :role="isError ? 'alert' : undefined"
      >
        <template v-if="renderMarkdown">
          <MarkdownContent :content="displayContent" :streaming="isStreaming" />
          <span v-if="isStreaming" class="msg__cursor">▌</span>
        </template>
        <template v-else>
          {{ displayContent }}<span v-if="isStreaming" class="msg__cursor">▌</span>
        </template>
      </div>

      <!-- 溯源汇总行：「N 条依据」点击展开引用面板 -->
      <div v-if="showCitations" class="msg__sources">
        <button
          type="button"
          class="msg__sources-toggle"
          :aria-expanded="sourcesOpen"
          @click="sourcesOpen = !sourcesOpen"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
          </svg>
          <span>{{ citations.length }} 条依据</span>
          <span class="msg__sources-caret" :class="{ 'msg__sources-caret--open': sourcesOpen }">▸</span>
        </button>
        <CitationList v-if="sourcesOpen" class="msg__citations" :citations="citations" />
      </div>

      <!-- 插槽: 嵌入结构化结果卡片 -->
      <div v-if="$slots.default" class="msg__slot">
        <slot />
      </div>

      <!-- 进度提示 -->
      <div v-if="isProgress && !displayContent" class="msg__progress">
        <span class="msg__spinner" />
        <span>处理中…</span>
      </div>

      <!-- 元信息行: 时间戳 + 消息级操作 -->
      <div v-if="!isSystem && (timeLabel || showActions)" class="msg__meta" :class="{ 'msg__meta--error': isError }">
        <span v-if="timeLabel" class="msg__time">{{ timeLabel }}</span>
        <div v-if="showActions" class="msg__actions">
          <button
            v-if="showCopy"
            class="msg__action"
            :class="{ 'msg__action--copied': copied }"
            :title="copied ? '已复制' : '复制'"
            @click="copyContent"
          >
            <svg v-if="!copied" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="9" y="9" width="13" height="13" rx="2" />
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
            </svg>
            <svg v-else width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            <span v-if="copied" class="msg__action-label">已复制</span>
          </button>
          <button
            v-if="showRegenerate"
            class="msg__action"
            title="重新生成"
            @click="emit('regenerate')"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="23 4 23 10 17 10" />
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
            </svg>
          </button>
          <button
            v-if="isError"
            class="msg__action msg__action--retry"
            title="重试"
            @click="emit('retry')"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="23 4 23 10 17 10" />
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
            </svg>
            <span class="msg__action-label">重试</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.msg {
  display: flex;
  gap: var(--space-3);
  max-width: var(--chat-col, 800px);
  margin: 0 auto;
  padding: var(--space-2) var(--space-4);
  animation: fadeIn 0.25s ease;
}
.msg--user {
  flex-direction: row-reverse;
}
.msg--system {
  justify-content: center;
  opacity: 0.7;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.msg__avatar {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: var(--font-size-xs);
  font-weight: 700;
}
/* 渐变 = AI（AI 徽章，渐变三处许可之一） */
.msg--assistant .msg__avatar {
  background: var(--gradient-accent);
  color: var(--on-accent);
}
.msg--user .msg__avatar {
  background: var(--bg-subtle);
  color: var(--text-secondary);
  border: 1px solid var(--border-default);
}
.avatar--system {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}

.msg__bubble {
  flex: 1;
  min-width: 0;
  max-width: 720px;
}
.msg--user .msg__bubble {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

/* 用户消息：轻气泡右对齐 */
.msg--user .msg__text {
  max-width: 640px;
  background: var(--accent-soft);
  color: var(--text-primary);
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-lg) var(--radius-sm) var(--radius-lg) var(--radius-lg);
  padding: var(--space-3) var(--space-4);
}
/* AI 消息：去气泡，文档式排版（限宽 720px 由 .msg__bubble 承载） */
.msg--assistant .msg__text {
  color: var(--text-primary);
  padding: var(--space-1) 0;
}
.msg--system .msg__text {
  background: transparent;
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  text-align: center;
}
/* 错误气泡 + 重试（重试按钮在 meta 行常驻） */
.msg--error .msg__text {
  background: var(--danger-soft);
  border: 1px solid var(--danger-border);
  border-radius: var(--radius-lg);
  padding: var(--space-3) var(--space-4);
  color: var(--danger);
}
.msg--progress .msg__text {
  background: transparent;
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
}

.msg__text {
  font-size: var(--font-size-md);
  line-height: var(--leading-md);
  white-space: pre-wrap;
  word-break: break-word;
}
/* Markdown 内容自行管理换行,不再保留 pre-wrap */
.msg__text--md {
  white-space: normal;
}
.msg__text--typing {
  color: var(--text-secondary);
}
.msg__cursor {
  animation: blink 0.8s step-end infinite;
  color: var(--accent);
}
@keyframes blink {
  50% { opacity: 0; }
}
/* 流式光标：reduced-motion 下静态 */
@media (prefers-reduced-motion: reduce) {
  .msg__cursor {
    animation: none;
  }
}

.msg__slot {
  margin-top: var(--space-3);
}

/* 溯源汇总行 */
.msg__sources {
  margin-top: var(--space-2);
}
.msg__sources-toggle {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-full);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  transition: color var(--transition-fast), border-color var(--transition-fast), background-color var(--transition-fast);
}
.msg__sources-toggle:hover {
  color: var(--accent-text);
  border-color: var(--accent-border);
  background: var(--accent-soft);
}
.msg__sources-caret {
  display: inline-block;
  transition: transform var(--transition-fast);
}
.msg__sources-caret--open {
  transform: rotate(90deg);
}
.msg__citations {
  margin-top: var(--space-1);
  padding: 0 var(--space-1);
}

/* 元信息行: 时间戳 + 消息级操作 */
.msg__meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-1);
  padding: 0 var(--space-1);
  min-height: 18px;
}
.msg--user .msg__meta {
  justify-content: flex-end;
}
.msg__time {
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  color: var(--text-tertiary);
  font-family: var(--font-mono);
}
.msg__actions {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  opacity: 0;
  transition: opacity var(--transition-fast);
}
.msg:hover .msg__actions,
.msg__meta--error .msg__actions {
  opacity: 1;
}
.msg__action {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  cursor: pointer;
  transition: color var(--transition-fast), background-color var(--transition-fast), border-color var(--transition-fast);
}
.msg__action:hover {
  color: var(--text-primary);
  background: var(--bg-subtle);
  border-color: var(--border-default);
}
.msg__action--copied {
  color: var(--success);
}
.msg__action--copied:hover {
  color: var(--success);
}
.msg__action--retry {
  color: var(--danger);
  border-color: var(--danger-border);
  background: var(--danger-soft);
  padding: var(--space-1) var(--space-2);
}
.msg__action--retry:hover {
  color: var(--danger);
  background: var(--danger-soft);
  border-color: var(--danger);
}
.msg__action-label {
  line-height: 1;
}

.msg__progress {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
}
.msg__spinner {
  width: 14px;
  height: 14px;
  border: 2px solid var(--border-default);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
