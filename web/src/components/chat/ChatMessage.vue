<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import MarkdownContent from '@/components/chat/MarkdownContent.vue'

export type MessageRole = 'user' | 'assistant' | 'system'

export interface ChatMessageData {
  id: string
  role: MessageRole
  content: string
  streaming?: boolean
  /** 结构化结果类型,非纯文本时标识内容类型 */
  resultType?: 'spec' | 'alternatives' | 'suppliers' | 'rfq' | 'grade' | 'error' | 'progress'
  timestamp?: number
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
    <!-- 头像 -->
    <div class="msg__avatar">
      <span v-if="isUser" class="avatar--user">U</span>
      <span v-else-if="isSystem" class="avatar--system">●</span>
      <span v-else class="avatar--ai">M</span>
    </div>

    <!-- 气泡 -->
    <div class="msg__bubble">
      <div
        v-if="displayContent"
        class="msg__text"
        :class="{ 'msg__text--typing': isStreaming, 'msg__text--md': renderMarkdown }"
      >
        <template v-if="renderMarkdown">
          <MarkdownContent :content="displayContent" :streaming="isStreaming" />
          <span v-if="isStreaming" class="msg__cursor">▌</span>
        </template>
        <template v-else>
          {{ displayContent }}<span v-if="isStreaming" class="msg__cursor">▌</span>
        </template>
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
  max-width: 800px;
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
.msg--assistant .msg__avatar {
  background: var(--gradient-accent);
  color: #fff;
}
.msg--user .msg__avatar {
  background: var(--bg-3);
  color: var(--text-secondary);
  border: 1px solid var(--border-default);
}
.avatar--system {
  color: var(--text-tertiary);
  font-size: 12px;
}

.msg__bubble {
  flex: 1;
  min-width: 0;
  max-width: 640px;
}
.msg--user .msg__bubble {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}
.msg--user .msg__text {
  background: var(--accent-soft);
  color: var(--text-primary);
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-lg) var(--radius-sm) var(--radius-lg) var(--radius-lg);
}
.msg--assistant .msg__text {
  background: var(--bg-2);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm) var(--radius-lg) var(--radius-lg) var(--radius-lg);
  color: var(--text-primary);
}
.msg--system .msg__text {
  background: transparent;
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  text-align: center;
}
.msg--error .msg__text {
  background: var(--danger-soft);
  border-color: rgba(239, 68, 68, 0.3);
  color: var(--danger);
}
.msg--progress .msg__text {
  background: transparent;
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
}

.msg__text {
  padding: var(--space-3) var(--space-4);
  font-size: var(--font-size-md);
  line-height: 1.7;
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

.msg__slot {
  margin-top: var(--space-3);
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
  gap: 3px;
  padding: 2px 4px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.msg__action:hover {
  color: var(--text-primary);
  background: var(--bg-3);
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
  border-color: rgba(239, 68, 68, 0.3);
  background: var(--danger-soft);
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
