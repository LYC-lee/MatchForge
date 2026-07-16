<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  getAuditQueue,
  approveAuditItem,
  rejectAuditItem,
  type AuditQueueItem,
} from '@/api/enterprise'
import AppButton from '@/components/ui/AppButton.vue'

const auditItems = ref<AuditQueueItem[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const activeTab = ref<'all' | 'pending' | 'approved' | 'rejected'>('pending')
const searchQuery = ref('')
const noteInputs = ref<Record<number, string>>({})

const filteredItems = computed(() => {
  let items = auditItems.value
  if (activeTab.value !== 'all') {
    items = items.filter((i) => i.status === activeTab.value)
  }
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    items = items.filter(
      (i) =>
        i.title.toLowerCase().includes(q) ||
        i.item_type.toLowerCase().includes(q) ||
        String(i.company_id || '').includes(q),
    )
  }
  return items
})

const stats = computed(() => ({
  pending: auditItems.value.filter((i) => i.status === 'pending').length,
  approved: auditItems.value.filter((i) => i.status === 'approved').length,
  rejected: auditItems.value.filter((i) => i.status === 'rejected').length,
  total: auditItems.value.length,
}))

function typeLabel(t: string) {
  const map: Record<string, string> = {
    supplier_capability: '供应商能力',
    rfq_supplier_match: 'RFQ 供应商匹配',
    quotation_anomaly: '报价异常',
  }
  return map[t] || t
}

function typeClass(t: string) {
  const map: Record<string, string> = {
    supplier_capability: 'tag-blue',
    rfq_supplier_match: 'tag-yellow',
    quotation_anomaly: 'tag-red',
  }
  return map[t] || 'tag-gray'
}

function statusLabel(s: string) {
  return { pending: '待审核', approved: '已通过', rejected: '已驳回' }[s] || s
}

function statusTag(s: string) {
  return { pending: 'tag-yellow', approved: 'tag-green', rejected: 'tag-gray' }[s] || 'tag-gray'
}

function payloadSummary(item: AuditQueueItem) {
  const p = item.payload || {}
  const parts: string[] = []
  if (p.rfq_number) parts.push(`RFQ: ${p.rfq_number}`)
  if (p.supplier_company_id) parts.push(`供应商: ${p.supplier_company_id}`)
  if (p.unit_price) parts.push(`单价: ¥${p.unit_price}`)
  if (p.target_price) parts.push(`目标价: ¥${p.target_price}`)
  if (p.match_score != null) parts.push(`匹配分: ${p.match_score}`)
  return parts.join(' · ') || '无摘要'
}

function formatTime(iso: string | null) {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return iso
  }
}

async function fetchQueue() {
  loading.value = true
  error.value = null
  try {
    const res = await getAuditQueue()
    auditItems.value = (res.data?.items || []) as AuditQueueItem[]
  } catch (e: any) {
    error.value = e?.message || '审核队列接口不可用 (需要 admin 权限)'
    auditItems.value = []
  } finally {
    loading.value = false
  }
}

async function handleApprove(item: AuditQueueItem) {
  try {
    await approveAuditItem(item.id, noteInputs.value[item.id])
    await fetchQueue()
  } catch {
    // 静默失败
  }
}

async function handleReject(item: AuditQueueItem) {
  try {
    await rejectAuditItem(item.id, noteInputs.value[item.id])
    await fetchQueue()
  } catch {
    // 静默失败
  }
}

onMounted(fetchQueue)
</script>

<template>
  <div class="admin-page">
    <div class="page-head">
      <div>
        <h2 class="page-title">审核管理</h2>
        <p class="page-desc">人工审核 RFQ 供应商匹配、报价异常等队列项 (需管理员权限)。</p>
      </div>
    </div>

    <div v-if="loading" class="card"><div class="card__body"><div v-for="i in 3" :key="i" class="skeleton" style="height: 80px; margin-bottom: 8px" /></div></div>
    <div v-else-if="error" class="notice-bar">{{ error }}</div>

    <template v-else>
      <!-- 统计概览 -->
      <div class="stats-row">
        <div class="stat-chip">
          <span class="stat-chip__num">{{ stats.pending }}</span>
          <span class="stat-chip__label">待审核</span>
        </div>
        <div class="stat-chip">
          <span class="stat-chip__num">{{ stats.approved }}</span>
          <span class="stat-chip__label">已通过</span>
        </div>
        <div class="stat-chip">
          <span class="stat-chip__num">{{ stats.rejected }}</span>
          <span class="stat-chip__label">已驳回</span>
        </div>
        <div class="stat-chip">
          <span class="stat-chip__num">{{ stats.total }}</span>
          <span class="stat-chip__label">总计</span>
        </div>
      </div>

      <!-- Tab + 搜索 -->
      <div class="toolbar">
        <div class="tabs">
          <button class="tab" :class="{ active: activeTab === 'pending' }" @click="activeTab = 'pending'">
            待审核
            <span v-if="stats.pending" class="tab-badge">{{ stats.pending }}</span>
          </button>
          <button class="tab" :class="{ active: activeTab === 'approved' }" @click="activeTab = 'approved'">已通过</button>
          <button class="tab" :class="{ active: activeTab === 'rejected' }" @click="activeTab = 'rejected'">已驳回</button>
          <button class="tab" :class="{ active: activeTab === 'all' }" @click="activeTab = 'all'">全部</button>
        </div>
        <input v-model="searchQuery" class="search-input" placeholder="搜索类型/标题/企业ID…" />
      </div>

      <!-- 空态 -->
      <div v-if="!filteredItems.length" class="card">
        <div class="card__body empty-state">
          <p class="empty-icon">✅</p>
          <p><strong>无匹配审核项</strong></p>
        </div>
      </div>

      <!-- 列表 -->
      <div v-else class="audit-list">
        <div v-for="item in filteredItems" :key="item.id" class="audit-card card">
          <div class="audit-card__body">
            <div class="audit-card__head">
              <span class="audit-label">#{{ item.id }}</span>
              <span class="tag" :class="typeClass(item.item_type)">{{ typeLabel(item.item_type) }}</span>
              <span class="audit-title">{{ item.title }}</span>
              <span class="tag" :class="statusTag(item.status)">{{ statusLabel(item.status) }}</span>
            </div>

            <div class="audit-card__meta">
              <div>
                <span class="meta-label">关联企业</span>
                <span class="meta-value">{{ item.company_id || '-' }}</span>
              </div>
              <div>
                <span class="meta-label">实体ID</span>
                <span class="meta-value">{{ item.entity_id }}</span>
              </div>
              <div>
                <span class="meta-label">创建时间</span>
                <span class="meta-value">{{ formatTime(item.created_at) }}</span>
              </div>
              <div>
                <span class="meta-label">审核时间</span>
                <span class="meta-value">{{ formatTime(item.reviewed_at) }}</span>
              </div>
              <div class="meta-full">
                <span class="meta-label">Payload 摘要</span>
                <span class="meta-value mono">{{ payloadSummary(item) }}</span>
              </div>
              <div v-if="item.review_note" class="meta-full">
                <span class="meta-label">审核备注</span>
                <span class="meta-value">{{ item.review_note }}</span>
              </div>
            </div>

            <div v-if="item.status === 'pending'" class="audit-card__actions">
              <input v-model="noteInputs[item.id]" class="source-input" placeholder="审核备注 (可选)" />
              <div class="action-btns">
                <AppButton variant="danger" size="sm" @click="handleReject(item)">驳回</AppButton>
                <AppButton variant="primary" size="sm" @click="handleApprove(item)">通过</AppButton>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.admin-page {
  max-width: 1100px;
  margin: 0 auto;
  padding: var(--space-5);
}
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}
.page-title { font-size: var(--font-size-xl); font-weight: 700; }
.page-desc { color: var(--text-secondary); margin-top: 4px; font-size: var(--font-size-sm); }
.notice-bar { padding: var(--space-3) var(--space-4); border-radius: 6px; border: 1px solid rgba(234, 179, 8, 0.25); background: var(--warning-soft); color: var(--warning); font-size: var(--font-size-sm); }

/* 统计 */
.stats-row { display: flex; gap: var(--space-3); margin-bottom: var(--space-5); }
.stat-chip { flex: 1; display: flex; flex-direction: column; gap: 4px; padding: var(--space-4); background: var(--bg-2); border: 1px solid var(--border-default); border-radius: var(--radius-lg); }
.stat-chip__num { font-size: var(--font-size-2xl); font-weight: 700; color: var(--text-primary); }
.stat-chip__label { font-size: var(--font-size-sm); color: var(--text-tertiary); }

/* 工具条 */
.toolbar { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-4); }
.tabs { display: flex; gap: 0; }
.tab { position: relative; padding: 10px 24px; border: none; background: none; font-size: var(--font-size-sm); color: var(--text-secondary); cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.15s; }
.tab:hover { color: var(--text-primary); }
.tab.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
.tab-badge { display: inline-flex; align-items: center; justify-content: center; min-width: 18px; height: 18px; padding: 0 6px; margin-left: 6px; border-radius: var(--radius-full); background: var(--danger-soft); color: var(--danger); font-size: var(--font-size-xs); font-weight: 700; }
.search-input { width: 240px; padding: 8px 12px; background: var(--bg-3); border: 1px solid var(--border-default); border-radius: var(--radius-md); font-size: var(--font-size-sm); color: var(--text-primary); outline: none; transition: border-color var(--transition-fast); }
.search-input:focus { border-color: var(--accent); }
.search-input::placeholder { color: var(--text-tertiary); }

.card { background: var(--bg-2); border: 1px solid var(--border-default); border-radius: var(--radius-lg); margin-bottom: var(--space-3); }
.card__body { padding: var(--space-4); }
.audit-list { display: flex; flex-direction: column; gap: var(--space-3); }
.audit-card { margin-bottom: 0; }
.audit-card__body { padding: var(--space-4); }
.audit-card__head { display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.audit-label { font-size: var(--font-size-xs); color: var(--text-tertiary); background: var(--bg-3); padding: 2px 8px; border-radius: var(--radius-sm); font-family: var(--font-mono); }
.audit-title { color: var(--text-primary); font-weight: 600; font-size: var(--font-size-sm); flex: 1; min-width: 200px; }
.audit-card__meta { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-2) var(--space-4); margin-bottom: var(--space-3); font-size: var(--font-size-sm); }
.audit-card__meta > div { display: flex; flex-direction: column; gap: 2px; }
.audit-card__meta .meta-full { grid-column: 1 / -1; }
.meta-label { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.meta-value { color: var(--text-secondary); }
.mono { font-family: var(--font-mono); font-size: var(--font-size-xs); }

.audit-card__actions { display: flex; gap: var(--space-3); align-items: center; padding-top: var(--space-3); border-top: 1px solid var(--border-subtle); }
.source-input { flex: 1; padding: 6px 10px; background: var(--bg-3); border: 1px solid var(--border-default); border-radius: var(--radius-sm); font-size: var(--font-size-sm); color: var(--text-primary); outline: none; }
.source-input:focus { border-color: var(--accent); }
.source-input::placeholder { color: var(--text-tertiary); }
.action-btns { display: flex; gap: var(--space-2); flex-shrink: 0; }

.tag { font-size: var(--font-size-xs); padding: 2px 8px; border-radius: var(--radius-sm); white-space: nowrap; }
.tag-yellow { color: var(--warning); background: var(--warning-soft); }
.tag-green { color: var(--success); background: var(--success-soft); }
.tag-gray { color: var(--text-tertiary); background: var(--bg-3); }
.tag-red { color: var(--danger); background: var(--danger-soft); }
.tag-blue { color: var(--accent); background: var(--accent-soft); }

.empty-state { text-align: center; padding: var(--space-8); color: var(--text-tertiary); }
.empty-icon { font-size: 40px; margin-bottom: var(--space-3); opacity: 0.4; }
.skeleton { background: linear-gradient(90deg, var(--bg-3) 25%, var(--border-subtle) 50%, var(--bg-3) 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite; border-radius: var(--radius-sm); }
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }

@media (max-width: 768px) {
  .stats-row { flex-wrap: wrap; }
  .stat-chip { min-width: calc(50% - var(--space-3)); }
  .toolbar { flex-direction: column; align-items: stretch; }
  .search-input { width: 100%; }
  .audit-card__meta { grid-template-columns: repeat(2, 1fr); }
}
</style>
