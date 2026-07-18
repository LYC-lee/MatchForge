<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useHistory } from '@/composables/useHistory'
import { useProcureStore } from '@/stores/procure'
import type { SessionSummary } from '@/types/procure'

const emit = defineEmits<{
  (e: 'newChat'): void
  (e: 'close'): void
  /** #28: 点击历史会话, 由 ChatView 在对话内重建聊天气泡(不再跳转向导页) */
  (e: 'select', threadId: string): void
}>()

const store = useProcureStore()
const { loading, error, load, remove } = useHistory()

const list = ref<SessionSummary[]>([])

async function refresh() {
  list.value = await load()
}

onMounted(refresh)

// 会话保存后自动刷新（historyVersion 自增）
watch(() => store.historyVersion, refresh)

function viewSession(threadId: string) {
  emit('select', threadId)
}

// 两步内联确认：× -> "确认删除?" 小气泡
const pendingDeleteId = ref<string | null>(null)

// 删除失败 toast（瞬时提示）
const toast = ref('')
let toastTimer: ReturnType<typeof setTimeout> | undefined
function showToast(msg: string) {
  toast.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = '' }, 2500)
}

async function confirmRemove(threadId: string) {
  pendingDeleteId.value = null
  try {
    const ok = await remove(threadId)
    if (!ok) throw new Error('remove returned false')
    list.value = list.value.filter((s) => s.thread_id !== threadId)
  } catch {
    showToast('删除失败，请稍后重试')
  }
}
function cancelRemove() {
  pendingDeleteId.value = null
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

// 当前打开的会话与 store.threadId 一致即高亮
const isActiveSession = (s: SessionSummary) => {
  return !!store.threadId && store.threadId === s.thread_id
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

    <!-- 加载失败态 -->
    <div v-else-if="error && !list.length" class="sess-panel__empty">
      <span class="sess-panel__empty-icon">⚠</span>
      <span>{{ error }}</span>
      <button class="sess-panel__retry" @click="refresh">重试</button>
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

        <!-- 两步确认：× -> 确认删除? -->
        <div v-if="pendingDeleteId === s.thread_id" class="sess-item__confirm" @click.stop>
          <span>确认删除？</span>
          <button class="sess-item__confirm-btn sess-item__confirm-btn--ok" @click.stop="confirmRemove(s.thread_id)">删除</button>
          <button class="sess-item__confirm-btn" @click.stop="cancelRemove">取消</button>
        </div>
        <button
          v-else
          class="sess-item__del"
          title="删除"
          @click.stop="pendingDeleteId = s.thread_id"
        >×</button>
      </div>
    </div>

    <!-- 删除失败 toast -->
    <Transition name="sess-toast">
      <div v-if="toast" class="sess-panel__toast" role="alert">{{ toast }}</div>
    </Transition>
  </div>
</template>

<style scoped>
.sess-panel {
  position: relative;
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
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-default);
  background: var(--bg-subtle);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  cursor: pointer;
  transition: border-color var(--transition-fast), background-color var(--transition-fast);
}
.sess-new-btn:hover {
  border-color: var(--accent-border);
  background: var(--accent-soft);
}
.sess-new-btn__icon {
  font-size: var(--font-size-lg);
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
  line-height: var(--leading-xs);
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.sess-panel__spinner {
  width: var(--space-3);
  height: var(--space-3);
  border: 2px solid var(--accent-soft);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* 加载/空/失败状态 */
.sess-panel__loading,
.sess-panel__empty {
  padding: var(--space-6) var(--space-4);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  color: var(--text-tertiary);
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
}
.sess-panel__empty-icon { font-size: var(--font-size-xl); }
.sess-panel__empty-hint {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  opacity: 0.6;
}
.sess-panel__retry {
  margin-top: var(--space-1);
  padding: var(--space-1) var(--space-3);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  color: var(--accent-text);
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-md);
  background: var(--accent-soft);
  cursor: pointer;
}
.sess-panel__retry:hover {
  color: var(--on-accent);
  background: var(--accent);
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
  transition: background-color var(--transition-fast);
  border-left: 2px solid transparent;
}
.sess-item:hover {
  background: var(--bg-subtle);
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
  gap: var(--space-1);
}
.sess-item__title {
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sess-item--active .sess-item__title {
  color: var(--text-primary);
}
.sess-item__time {
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  color: var(--text-tertiary);
}
.sess-item__del {
  width: var(--space-5);
  height: var(--space-5);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-md);
  color: var(--text-tertiary);
  background: none;
  border: none;
  cursor: pointer;
  opacity: 0;
  transition: color var(--transition-fast), background-color var(--transition-fast), opacity var(--transition-fast);
  flex-shrink: 0;
}
.sess-item:hover .sess-item__del {
  opacity: 1;
}
.sess-item__del:hover {
  color: var(--danger);
  background: var(--danger-soft);
}
/* 两步确认气泡 */
.sess-item__confirm {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex-shrink: 0;
  padding: var(--space-1) var(--space-2);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  color: var(--text-secondary);
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
}
.sess-item__confirm-btn {
  padding: var(--space-1) var(--space-2);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  color: var(--text-secondary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  cursor: pointer;
  transition: color var(--transition-fast), background-color var(--transition-fast), border-color var(--transition-fast);
}
.sess-item__confirm-btn:hover {
  color: var(--text-primary);
  background: var(--bg-subtle);
}
.sess-item__confirm-btn--ok {
  color: var(--danger);
  border-color: var(--danger-border);
  background: var(--danger-soft);
}
.sess-item__confirm-btn--ok:hover {
  color: var(--on-accent);
  background: var(--danger);
  border-color: var(--danger);
}

/* 触屏设备：无 hover，删除按钮常显 */
@media (hover: none) {
  .sess-item__del {
    opacity: 1;
  }
}

/* toast */
.sess-panel__toast {
  position: absolute;
  bottom: var(--space-4);
  left: 50%;
  transform: translateX(-50%);
  padding: var(--space-2) var(--space-4);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  color: var(--danger);
  background: var(--bg-elevated);
  border: 1px solid var(--danger-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  z-index: var(--z-toast);
}
.sess-toast-enter-active,
.sess-toast-leave-active {
  transition: opacity var(--transition-base), transform var(--transition-base);
}
.sess-toast-enter-from,
.sess-toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(var(--space-2));
}
</style>
