<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useHistory } from '@/composables/useHistory'
import type { SessionSummary } from '@/types/procure'
import Card from '@/components/ui/Card.vue'
import AppButton from '@/components/ui/AppButton.vue'

const router = useRouter()
const { sessions, loading, error, load, remove } = useHistory()

const list = ref<SessionSummary[]>([])

onMounted(async () => {
  list.value = await load()
})

async function doRemove(threadId: string) {
  await remove(threadId)
  list.value = list.value.filter((s) => s.thread_id !== threadId)
}

function viewSession(threadId: string) {
  router.push(`/procure/${threadId}`)
}

function newProcure() {
  router.push('/')
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

    <!-- 加载中 -->
    <div v-if="loading" class="history__loading">
      <span class="history__spinner" />
      <span>加载中…</span>
    </div>

    <!-- 网络错误提示 -->
    <div v-if="error && !loading" class="history__notice">
      <span>⚠ {{ error }}</span>
    </div>

    <!-- 空状态 -->
    <div v-if="!loading && !list.length" class="history__empty">
      <div class="history__empty-icon">⊘</div>
      <p class="history__empty-title">还没有寻源记录</p>
      <p class="history__empty-desc">去首页试试</p>
      <AppButton @click="newProcure">开始寻源</AppButton>
    </div>

    <!-- 会话列表 -->
    <div v-else class="history__list">
      <Card v-for="s in list" :key="s.thread_id">
        <template #header>
          <div class="rec__head">
            <div class="rec__info">
              <span class="rec__title">{{ s.title }}</span>
              <span class="rec__meta">
                <span class="rec__id" :title="s.thread_id">ID: {{ s.thread_id.slice(0, 8) }}</span>
                <span class="rec__sep">·</span>
                <span class="rec__date">{{ formatDate(s.created_at) }}</span>
                <span class="rec__sep">·</span>
                <span :class="s.status === 'error' ? 'rec__status--error' : 'rec__status--ok'">
                  {{ s.status === 'error' ? '异常' : '完成' }}
                </span>
              </span>
            </div>
            <div class="rec__actions">
              <AppButton variant="secondary" size="sm" @click="viewSession(s.thread_id)">
                查看
              </AppButton>
              <AppButton variant="danger" size="sm" @click="doRemove(s.thread_id)">
                删除
              </AppButton>
            </div>
          </div>
        </template>
      </Card>
    </div>
  </div>
</template>

<style scoped>
.history {
  max-width: 960px;
  margin: 0 auto;
  padding: var(--space-6) var(--space-5);
}
.history__head { margin-bottom: var(--space-5); }
.history__head h1 { font-size: var(--font-size-2xl); font-weight: 700; }
.history__sub { font-size: var(--font-size-sm); color: var(--text-tertiary); margin-top: var(--space-1); }

.history__loading {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-6);
  justify-content: center;
  color: var(--text-tertiary);
}
.history__spinner {
  width: 18px; height: 18px;
  border: 2px solid var(--accent-soft);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.history__notice {
  padding: var(--space-3) var(--space-4);
  background: var(--warning-soft);
  border: 1px solid rgba(234, 179, 8, 0.3);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  color: var(--warning);
  margin-bottom: var(--space-4);
}

.history__empty {
  text-align: center;
  padding: var(--space-8) var(--space-4);
}
.history__empty-icon { font-size: 40px; color: var(--text-tertiary); margin-bottom: var(--space-3); }
.history__empty-title { font-size: var(--font-size-lg); font-weight: 600; color: var(--text-secondary); margin-bottom: var(--space-2); }
.history__empty-desc { font-size: var(--font-size-sm); color: var(--text-tertiary); margin-bottom: var(--space-4); }

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
  color: var(--text-tertiary);
}
.rec__id {
  font-family: var(--font-mono);
  color: var(--text-tertiary);
}
.rec__sep { color: var(--border-default); }
.rec__status--ok { color: var(--success); }
.rec__status--error { color: var(--danger); }
.rec__actions {
  display: flex;
  gap: var(--space-2);
  flex-shrink: 0;
}

@media (max-width: 640px) {
  .rec__head { flex-direction: column; align-items: flex-start; }
  .rec__actions { width: 100%; justify-content: flex-end; }
}
</style>