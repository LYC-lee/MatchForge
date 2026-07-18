<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useHistory } from '@/composables/useHistory'
import type { SessionSummary } from '@/types/procure'
import Card from '@/components/ui/Card.vue'
import AppButton from '@/components/ui/AppButton.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import EmptyState from '@/components/ui/EmptyState.vue'

const router = useRouter()
const { loading, error, load, remove } = useHistory()

const list = ref<SessionSummary[]>([])

// 搜索与状态筛选
const searchText = ref('')
const statusFilter = ref<'all' | 'completed' | 'error'>('all')

const statusLabel = (s: string) => {
  const map: Record<string, string> = {
    completed: '完成',
    error: '异常',
    done: '完成',
    pending: '进行中',
    running: '进行中',
  }
  return map[s] || s
}

const filteredList = computed(() => {
  const q = searchText.value.trim().toLowerCase()
  return list.value.filter((s) => {
    if (statusFilter.value !== 'all' && s.status !== statusFilter.value) return false
    if (q && !(s.title || '').toLowerCase().includes(q)) return false
    return true
  })
})

onMounted(async () => {
  list.value = await load()
})

// 删除二次确认
const pendingDelete = ref<SessionSummary | null>(null)
const deleteDialogOpen = computed({
  get: () => !!pendingDelete.value,
  set: (v: boolean) => { if (!v) pendingDelete.value = null },
})
const deleting = ref(false)
async function confirmDelete() {
  if (!pendingDelete.value) return
  deleting.value = true
  try {
    await remove(pendingDelete.value.thread_id)
    list.value = list.value.filter((s) => s.thread_id !== pendingDelete.value!.thread_id)
  } finally {
    deleting.value = false
    pendingDelete.value = null
  }
}

function viewSession(threadId: string) {
  router.push(`/procure/${threadId}`)
}

function newProcure() {
  router.push('/chat')
}

function formatDate(iso: string) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const now = new Date()
    const diff = now.getTime() - d.getTime()
    if (diff < 60_000) return '刚刚'
    if (diff < 3600_000) return `${Math.floor(diff / 60_000)} 分钟前`
    if (diff < 86400_000) return `${Math.floor(diff / 3600_000)} 小时前`
    if (diff < 604800_000) return `${Math.floor(diff / 86400_000)} 天前`
    return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
  } catch {
    return iso.slice(0, 10)
  }
}
</script>

<template>
  <div class="history">
    <div class="history__head">
      <h1>历史记录</h1>
      <p class="history__sub">寻源会话记录（跨设备同步）</p>
    </div>

    <!-- 搜索与筛选 -->
    <div v-if="list.length" class="history__filters">
      <input v-model="searchText" type="text" class="history__search" placeholder="按标题关键词搜索…">
      <div class="history__status-filter" role="group" aria-label="状态筛选">
        <button class="filter-btn" :class="{ active: statusFilter === 'all' }" @click="statusFilter = 'all'">全部</button>
        <button class="filter-btn" :class="{ active: statusFilter === 'completed' }" @click="statusFilter = 'completed'">完成</button>
        <button class="filter-btn" :class="{ active: statusFilter === 'error' }" @click="statusFilter = 'error'">异常</button>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="history__loading">
      <span class="history__spinner" />
      <span>加载中…</span>
    </div>

    <!-- 网络错误提示 -->
    <div v-if="error && !loading" class="history__notice" role="alert">
      <span>⚠ {{ error }}</span>
    </div>

    <!-- 空状态 -->
    <EmptyState
      v-if="!loading && !list.length"
      title="还没有寻源记录"
      description="发起一次寻源后会出现在这里。"
    >
      <template #icon>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      </template>
      <template #action>
        <AppButton @click="newProcure">去寻源</AppButton>
      </template>
    </EmptyState>

    <!-- 筛选无结果 -->
    <EmptyState
      v-else-if="!filteredList.length"
      title="没有匹配的记录"
      :description="`没有符合「${searchText || statusLabel(statusFilter)}」的会话，试试换个关键词。`"
      compact
    />

    <!-- 会话列表 -->
    <div v-else class="history__list">
      <Card v-for="s in filteredList" :key="s.thread_id">
        <template #header>
          <div class="rec__head">
            <div class="rec__info">
              <span class="rec__title">{{ s.title || '未命名会话' }}</span>
              <span class="rec__meta">
                <span class="rec__id" :title="s.thread_id">ID: {{ s.thread_id.slice(0, 8) }}</span>
                <span class="rec__sep">·</span>
                <span class="rec__date">{{ formatDate(s.created_at) }}</span>
                <span class="rec__sep">·</span>
                <span :class="s.status === 'error' ? 'rec__status--error' : 'rec__status--ok'">
                  {{ statusLabel(s.status) }}
                </span>
              </span>
            </div>
            <div class="rec__actions">
              <AppButton variant="secondary" size="sm" @click="viewSession(s.thread_id)">查看</AppButton>
              <AppButton variant="danger" size="sm" @click="pendingDelete = s">删除</AppButton>
            </div>
          </div>
        </template>
      </Card>
    </div>

    <ConfirmDialog
      v-model:open="deleteDialogOpen"
      title="删除该寻源记录？"
      :description="pendingDelete ? `将删除「${pendingDelete.title || '未命名会话'}」，删除后不可恢复。` : ''"
      confirm-text="删除"
      danger
      :loading="deleting"
      @confirm="confirmDelete"
    />
  </div>
</template>

<style scoped>
.history {
  max-width: var(--container-sm);
  margin: 0 auto;
  padding: var(--space-6) var(--space-5);
}
.history__head { margin-bottom: var(--space-5); }
.history__head h1 { font-size: var(--font-size-2xl); line-height: var(--leading-2xl); font-weight: 700; }
.history__sub { font-size: var(--font-size-sm); line-height: var(--leading-sm); color: var(--text-tertiary); margin-top: var(--space-1); }

.history__filters {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
  flex-wrap: wrap;
}
.history__search {
  flex: 1;
  min-width: 200px;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  outline: none;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.history__search:focus { border-color: var(--accent-border); box-shadow: 0 0 0 3px var(--accent-soft); }
.history__search::placeholder { color: var(--text-tertiary); }
.history__status-filter {
  display: inline-flex;
  gap: var(--space-1);
  padding: var(--space-1);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: var(--bg-subtle);
}
.filter-btn {
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-sm);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  background: none;
  border: none;
  cursor: pointer;
  transition: color var(--transition-fast), background-color var(--transition-fast);
}
.filter-btn:hover { color: var(--text-secondary); }
.filter-btn.active { color: var(--text-primary); background: var(--bg-surface); }

.history__loading {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-6);
  justify-content: center;
  color: var(--text-tertiary);
}
.history__spinner {
  width: var(--space-4);
  height: var(--space-4);
  border: 2px solid var(--accent-soft);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.history__notice {
  padding: var(--space-3) var(--space-4);
  background: var(--warning-soft);
  border: 1px solid var(--warning-border);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  color: var(--warning);
  margin-bottom: var(--space-4);
}

.history__list { display: flex; flex-direction: column; gap: var(--space-3); }

.rec__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  width: 100%;
}
.rec__info {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}
.rec__title {
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  color: var(--text-primary);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.rec__meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  color: var(--text-tertiary);
}
.rec__id { font-family: var(--font-mono); color: var(--text-tertiary); }
.rec__sep { color: var(--border-default); }
.rec__status--ok { color: var(--success); }
.rec__status--error { color: var(--danger); }
.rec__actions { display: flex; gap: var(--space-2); flex-shrink: 0; }

@media (max-width: 640px) {
  .rec__head { flex-direction: column; align-items: flex-start; }
  .rec__actions { width: 100%; justify-content: flex-end; }
}
</style>
