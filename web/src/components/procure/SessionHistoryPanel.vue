<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useHistory } from '@/composables/useHistory'
import { useProcureStore } from '@/stores/procure'
import type { SessionSummary } from '@/types/procure'

const emit = defineEmits<{
  (e: 'newChat'): void
  (e: 'close'): void
}>()

const router = useRouter()
const route = useRoute()
const store = useProcureStore()
const { loading, load, remove } = useHistory()

const list = ref<SessionSummary[]>([])

async function refresh() {
  list.value = await load()
}

onMounted(refresh)

// 路由变化时刷新列表
watch(() => route.fullPath, refresh)

// 会话保存后自动刷新（historyVersion 自增）
watch(() => store.historyVersion, refresh)

function viewSession(threadId: string) {
  router.push(`/procure/${threadId}`)
}

async function doRemove(threadId: string) {
  await remove(threadId)
  list.value = list.value.filter((s) => s.thread_id !== threadId)
}

function newChat() {
  emit('newChat')
  emit('close')
}

function formatDate(iso: string) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const now = Date.now()
    const diff = now - d.getTime()
    if (diff < 60_000) return '刚刚'
    if (diff < 3600_000) return `${Math.floor(diff / 60_000)}分钟前`
    if (diff < 86400_000) return `${Math.floor(diff / 3600_000)}小时前`
    if (diff < 604800_000) return `${Math.floor(diff / 86400_000)}天前`
    return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
  } catch { return iso.slice(0, 10) }
}

const isActiveSession = (s: SessionSummary) => {
  return route.params.id === s.thread_id
}
</script>

<template>
  <div class="sess-panel">
    <!-- 新建对话按钮 -->
    <div class="sess-panel__new">
      <button class="sess-new-btn" @click="newChat">
        <span class="sess-new-btn__icon">+</span>
        <span>新建对话</span>
      </button>
    </div>

    <!-- 标题 -->
    <div class="sess-panel__head">
      <span class="sess-panel__title">历史记录</span>
      <span v-if="loading" class="sess-panel__spinner" />
    </div>

    <!-- 加载中 -->
    <div v-if="loading && !list.length" class="sess-panel__loading">
      加载中…
    </div>

    <!-- 空状态 -->
    <div v-else-if="!list.length" class="sess-panel__empty">
      <span class="sess-panel__empty-icon">💬</span>
      <span>暂无对话记录</span>
      <span class="sess-panel__empty-hint">开始寻源后自动保存</span>
    </div>

    <!-- 会话列表 -->
    <div v-else class="sess-panel__list">
      <div
        v-for="s in list"
        :key="s.thread_id"
        class="sess-item"
        :class="{ 'sess-item--active': isActiveSession(s) }"
        @click="viewSession(s.thread_id)"
      >
        <div class="sess-item__info">
          <span class="sess-item__title">{{ s.title || '未命名会话' }}</span>
          <span class="sess-item__time">{{ formatDate(s.created_at) }}</span>
        </div>
        <button
          class="sess-item__del"
          title="删除"
          @click.stop="doRemove(s.thread_id)"
        >×</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sess-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

/* 新建对话按钮 */
.sess-panel__new {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-subtle);
}
.sess-new-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-default);
  background: var(--bg-2);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.sess-new-btn:hover {
  border-color: var(--accent-border);
  background: var(--accent-soft);
}
.sess-new-btn__icon {
  font-size: 18px;
  font-weight: 300;
  color: var(--accent);
}

/* 标题 */
.sess-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-4);
  flex-shrink: 0;
}
.sess-panel__title {
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.sess-panel__spinner {
  width: 14px; height: 14px;
  border: 2px solid var(--accent-soft);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* 加载/空状态 */
.sess-panel__loading,
.sess-panel__empty {
  padding: var(--space-6) var(--space-4);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
}
.sess-panel__empty-icon { font-size: 24px; }
.sess-panel__empty-hint {
  font-size: 11px;
  color: var(--text-tertiary);
  opacity: 0.6;
}

/* 列表 */
.sess-panel__list {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-1) 0;
}
.sess-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  cursor: pointer;
  transition: background var(--transition-fast);
  border-left: 2px solid transparent;
}
.sess-item:hover {
  background: var(--bg-2);
}
.sess-item--active {
  background: var(--accent-soft);
  border-left-color: var(--accent);
}
.sess-item__info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.sess-item__title {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sess-item--active .sess-item__title {
  color: var(--text-primary);
}
.sess-item__time {
  font-size: 11px;
  color: var(--text-tertiary);
}
.sess-item__del {
  width: 20px; height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  font-size: 14px;
  color: var(--text-tertiary);
  background: none;
  border: none;
  cursor: pointer;
  opacity: 0;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}
.sess-item:hover .sess-item__del {
  opacity: 1;
}
.sess-item__del:hover {
  color: var(--danger);
  background: var(--danger-soft);
}
</style>