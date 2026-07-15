<script setup lang="ts">
import { computed } from 'vue'

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

const isUser = computed(() => props.message.role === 'user')
const isSystem = computed(() => props.message.role === 'system')
const isStreaming = computed(() => props.message.streaming)
const isError = computed(() => props.message.resultType === 'error')
const isProgress = computed(() => props.message.resultType === 'progress')

const displayContent = computed(() => {
  let text = props.message.content
  if (isStreaming.value && !text) return '⋯'
  return text
})
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
        :class="{ 'msg__text--typing': isStreaming }"
      >
        {{ displayContent }}<span v-if="isStreaming" class="msg__cursor">▌</span>
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
