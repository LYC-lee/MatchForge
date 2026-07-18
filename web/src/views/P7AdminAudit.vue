<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import {
  getAuditQueue,
  approveAuditItem,
  rejectAuditItem,
  type AuditQueueItem,
} from '@/api/enterprise'
import { useDemo } from '@/composables/useDemo'
import AppButton from '@/components/ui/AppButton.vue'
import Tag from '@/components/ui/Tag.vue'
import StatusTag from '@/components/ui/StatusTag.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'

const demo = useDemo()
const isDemo = computed(() => demo.isDemo.value)

const auditItems = ref<AuditQueueItem[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const activeTab = ref<'all' | 'pending' | 'approved' | 'rejected'>('pending')
const searchQuery = ref('')
const noteInputs = ref<Record<number, string>>({})

/** 统一审核项列表: demo 模式取 demo.auditQueue, 否则取真实 auditItems */
const unifiedItems = computed(() => {
  if (isDemo.value) {
    const items = demo.auditQueue.value?.items || []
    return items.map((it) => ({
      id: it.audit_id as unknown as number,
      item_type: it.item_type,
      title: it.title,
      detail: it.detail || '',
      status: it.status as 'pending',
      company_id: it.company_id,
      entity_id: it.audit_id as unknown as number,
      payload: it.payload || {},
      created_at: it.created_at,
      reviewed_at: null,
      review_note: null,
    })) as unknown as AuditQueueItem[]
  }
  return auditItems.value
})

// 风险等级排序：待审核按风险降序置顶
const TYPE_RISK: Record<string, number> = {
  quotation_anomaly: 3,
  no_direct_supplier: 3,
  relationship_missing: 2,
  supplier_capability: 2,
  rfq_supplier_match: 1,
}
function typeRisk(t: string) {
  return TYPE_RISK[t] ?? 0
}

const filteredItems = computed(() => {
  let items = unifiedItems.value
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
  // 待审核按风险等级降序；其他按状态时间稳定排序
  return [...items].sort((a, b) => {
    const ra = a.status === 'pending' ? typeRisk(a.item_type) : -1
    const rb = b.status === 'pending' ? typeRisk(b.item_type) : -1
    return rb - ra
  })
})

const stats = computed(() => {
  const items = unifiedItems.value
  return {
    pending: items.filter((i) => i.status === 'pending').length,
    approved: items.filter((i) => i.status === 'approved').length,
    rejected: items.filter((i) => i.status === 'rejected').length,
    total: items.length,
  }
})

function typeLabel(t: string) {
  const map: Record<string, string> = {
    supplier_capability: '供应商能力',
    rfq_supplier_match: 'RFQ 供应商匹配',
    quotation_anomaly: '报价异常',
    no_direct_supplier: '无直接供应商',
    relationship_missing: '关系缺失',
  }
  return map[t] || t
}

function typeTagType(t: string): 'neutral' | 'notice' | 'warning' | 'danger' {
  if (t === 'quotation_anomaly' || t === 'no_direct_supplier') return 'danger'
  if (t === 'relationship_missing' || t === 'supplier_capability') return 'warning'
  if (t === 'rfq_supplier_match') return 'notice'
  return 'neutral'
}

function payloadSummary(item: AuditQueueItem) {
  const p = item.payload || {}
  const parts: string[] = []
  if (p.rfq_number) parts.push(`RFQ: ${p.rfq_number}`)
  if (p.supplier_company_id) parts.push(`供应商: ${p.supplier_company_id}`)
  if (p.unit_price) parts.push(`单价: ¥${p.unit_price}`)
  if (p.target_price) parts.push(`目标价: ¥${p.target_price}`)
  if (p.part_number) parts.push(`零件: ${p.part_number}`)
  if (p.shortage_qty != null) parts.push(`缺口: ${p.shortage_qty}`)
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
  if (isDemo.value) {
    loading.value = demo.loadingAudit.value
    return
  }
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

// 失败 toast
const toast = ref('')
let toastTimer: ReturnType<typeof setTimeout> | undefined
function showToast(msg: string) {
  toast.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = '' }, 3000)
}

// 通过：ConfirmDialog 确认
const approveTarget = ref<AuditQueueItem | null>(null)
const approveDialogOpen = computed({
  get: () => !!approveTarget.value,
  set: (v: boolean) => { if (!v) approveTarget.value = null },
})
const acting = ref(false)
function startApprove(item: AuditQueueItem) {
  if (isDemo.value) return
  approveTarget.value = item
}
async function doApprove() {
  if (!approveTarget.value) return
  acting.value = true
  const item = approveTarget.value
  try {
    await approveAuditItem(item.id, noteInputs.value[item.id])
    approveTarget.value = null
    await fetchQueue()
  } catch (e: any) {
    showToast(e?.message || '通过失败，请稍后重试')
  } finally {
    acting.value = false
  }
}

// 驳回：自定义弹层 + 强制备注
const rejectTarget = ref<AuditQueueItem | null>(null)
const rejectNote = ref('')
const rejectNoteInput = ref<HTMLTextAreaElement | null>(null)
const rejectError = ref<string | null>(null)
function startReject(item: AuditQueueItem) {
  if (isDemo.value) return
  rejectTarget.value = item
  rejectNote.value = noteInputs.value[item.id] || ''
  rejectError.value = null
  nextTick(() => rejectNoteInput.value?.focus())
}
function closeReject() {
  if (acting.value) return
  rejectTarget.value = null
  rejectError.value = null
}
async function doReject() {
  if (!rejectTarget.value) return
  if (!rejectNote.value.trim()) {
    rejectError.value = '驳回必须填写备注，说明判定依据'
    return
  }
  acting.value = true
  const item = rejectTarget.value
  try {
    await rejectAuditItem(item.id, rejectNote.value)
    noteInputs.value[item.id] = rejectNote.value
    rejectTarget.value = null
    await fetchQueue()
  } catch (e: any) {
    showToast(e?.message || '驳回失败，请稍后重试')
  } finally {
    acting.value = false
  }
}

onMounted(fetchQueue)

watch(() => demo.auditQueue.value, () => {}, { deep: true })
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
    <div v-else-if="error" class="notice-bar" role="alert">{{ error }}</div>
    <div v-if="isDemo" class="notice-bar notice-bar--demo">演示沙盘数据 · 审核项从 demo 事件/报价动态派生 (无直接供应商 / 报价异常), 只读队列, 不写回审批状态</div>

    <template v-if="!loading && !error">
      <!-- 统计概览 -->
      <div class="stats-row">
        <div class="stat-chip">
          <span class="stat-chip__num num">{{ stats.pending }}</span>
          <span class="stat-chip__label">待审核</span>
        </div>
        <div class="stat-chip">
          <span class="stat-chip__num num">{{ stats.approved }}</span>
          <span class="stat-chip__label">已通过</span>
        </div>
        <div class="stat-chip">
          <span class="stat-chip__num num">{{ stats.rejected }}</span>
          <span class="stat-chip__label">已驳回</span>
        </div>
        <div class="stat-chip">
          <span class="stat-chip__num num">{{ stats.total }}</span>
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
        <input v-model="searchQuery" class="search-input" placeholder="搜索类型/标题/企业ID…">
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
              <Tag :type="typeTagType(item.item_type)" :value="typeLabel(item.item_type)" />
              <span class="audit-title">{{ item.title }}</span>
              <StatusTag domain="audit" :value="item.status" />
            </div>

            <!-- 判定依据：item.detail 已映射却从不显示，审核员看不到依据 -->
            <p v-if="item.detail" class="audit-detail">{{ item.detail }}</p>

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

            <div v-if="item.status === 'pending' && !isDemo" class="audit-card__actions">
              <input v-model="noteInputs[item.id]" class="source-input" placeholder="审核备注（通过时可选，驳回时在弹层填写）">
              <div class="action-btns">
                <AppButton variant="danger" size="sm" @click="startReject(item)">驳回</AppButton>
                <AppButton size="sm" :loading="acting && approveTarget?.id === item.id" @click="startApprove(item)">通过</AppButton>
              </div>
            </div>
            <div v-if="item.status === 'pending' && isDemo" class="audit-card__readonly">
              <span class="readonly-hint">演示沙盘只读队列 · 通过采购方建立合作关系或人工处理后, 重置场景可清除</span>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- 通过确认 -->
    <ConfirmDialog
      v-model:open="approveDialogOpen"
      title="确认通过该审核项？"
      :description="approveTarget ? `将通过「${approveTarget.title}」。` : ''"
      confirm-text="确认通过"
      :loading="acting"
      @confirm="doApprove"
    />

    <!-- 驳回弹层（强制备注） -->
    <div v-if="rejectTarget" class="modal-overlay" @click.self="closeReject">
      <div
        class="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="reject-modal-title"
        @keydown.esc="closeReject"
      >
        <div class="modal-head">
          <h3 id="reject-modal-title">驳回该审核项</h3>
          <button class="btn-close" aria-label="关闭" :disabled="acting" @click="closeReject">✕</button>
        </div>
        <div class="modal-body">
          <p class="modal-desc">{{ rejectTarget?.title }}</p>
          <label class="reject-note">
            <span>驳回备注 *（说明判定依据）</span>
            <textarea ref="rejectNoteInput" v-model="rejectNote" class="input" rows="3" placeholder="如：报价低于市场价 30%，疑似异常…">
            </textarea>
          </label>
          <p v-if="rejectError" class="form-error" role="alert">{{ rejectError }}</p>
        </div>
        <div class="modal-footer">
          <AppButton variant="secondary" :disabled="acting" @click="closeReject">取消</AppButton>
          <AppButton variant="danger" :loading="acting" @click="doReject">确认驳回</AppButton>
        </div>
      </div>
    </div>

    <Transition name="toast">
      <div v-if="toast" class="toast" role="alert">{{ toast }}</div>
    </Transition>
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
.page-title { font-size: var(--font-size-xl); line-height: var(--leading-xl); font-weight: 700; }
.page-desc { color: var(--text-secondary); margin-top: var(--space-1); font-size: var(--font-size-sm); line-height: var(--leading-sm); }
.notice-bar { padding: var(--space-3) var(--space-4); border-radius: var(--radius-md); border: 1px solid var(--warning-border); background: var(--warning-soft); color: var(--warning); font-size: var(--font-size-sm); line-height: var(--leading-sm); margin-bottom: var(--space-4); }
.notice-bar--demo { border: 1px solid var(--accent-border); background: var(--accent-soft); color: var(--accent-text); }
.audit-card__readonly { padding-top: var(--space-3); border-top: 1px solid var(--border-subtle); }
.readonly-hint { color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: var(--leading-xs); }

/* 统计 */
.stats-row { display: flex; gap: var(--space-3); margin-bottom: var(--space-5); }
.stat-chip { flex: 1; display: flex; flex-direction: column; gap: var(--space-1); padding: var(--space-4); background: var(--bg-surface); border: 1px solid var(--border-default); border-radius: var(--radius-lg); }
.stat-chip__num { font-size: var(--font-size-2xl); line-height: var(--leading-2xl); font-weight: 700; color: var(--text-primary); font-family: var(--font-mono); }
.stat-chip__label { font-size: var(--font-size-sm); line-height: var(--leading-sm); color: var(--text-tertiary); }

/* 工具条 */
.toolbar { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-4); }
.tabs { display: flex; gap: 0; }
.tab { position: relative; padding: var(--space-2) var(--space-5); border: none; background: none; font-size: var(--font-size-sm); line-height: var(--leading-sm); color: var(--text-secondary); cursor: pointer; border-bottom: 2px solid transparent; transition: color var(--transition-fast), border-color var(--transition-fast); }
.tab:hover { color: var(--text-primary); }
.tab.active { color: var(--accent-text); border-bottom-color: var(--accent); font-weight: 600; }
.tab-badge { display: inline-flex; align-items: center; justify-content: center; min-width: 18px; height: 18px; padding: 0 var(--space-1); margin-left: var(--space-1); border-radius: var(--radius-full); background: var(--danger-soft); color: var(--danger); font-size: var(--font-size-xs); font-weight: 700; }
.search-input { width: 240px; padding: var(--space-2) var(--space-3); background: var(--bg-surface); border: 1px solid var(--border-default); border-radius: var(--radius-md); font-size: var(--font-size-sm); line-height: var(--leading-sm); color: var(--text-primary); outline: none; transition: border-color var(--transition-fast), box-shadow var(--transition-fast); }
.search-input:focus { border-color: var(--accent-border); box-shadow: 0 0 0 3px var(--accent-soft); }
.search-input::placeholder { color: var(--text-tertiary); }

.card { background: var(--bg-surface); border: 1px solid var(--border-default); border-radius: var(--radius-lg); margin-bottom: var(--space-3); }
.card__body { padding: var(--space-4); }
.audit-list { display: flex; flex-direction: column; gap: var(--space-3); }
.audit-card { margin-bottom: 0; }
.audit-card__body { padding: var(--space-4); }
.audit-card__head { display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.audit-label { font-size: var(--font-size-xs); line-height: var(--leading-xs); color: var(--text-tertiary); background: var(--bg-subtle); padding: var(--space-1) var(--space-2); border-radius: var(--radius-sm); font-family: var(--font-mono); }
.audit-title { color: var(--text-primary); font-weight: 600; font-size: var(--font-size-sm); line-height: var(--leading-sm); flex: 1; min-width: 200px; }
.audit-detail { margin-bottom: var(--space-3); padding: var(--space-2) var(--space-3); background: var(--bg-subtle); border-left: 3px solid var(--accent); border-radius: var(--radius-sm); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: var(--leading-sm); }
.audit-card__meta { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-2) var(--space-4); margin-bottom: var(--space-3); font-size: var(--font-size-sm); line-height: var(--leading-sm); }
.audit-card__meta > div { display: flex; flex-direction: column; gap: var(--space-1); }
.audit-card__meta .meta-full { grid-column: 1 / -1; }
.meta-label { color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: var(--leading-xs); }
.meta-value { color: var(--text-secondary); }
.mono { font-family: var(--font-mono); font-size: var(--font-size-xs); }

.audit-card__actions { display: flex; gap: var(--space-3); align-items: center; padding-top: var(--space-3); border-top: 1px solid var(--border-subtle); }
.source-input { flex: 1; padding: var(--space-1) var(--space-2); background: var(--bg-surface); border: 1px solid var(--border-default); border-radius: var(--radius-sm); font-size: var(--font-size-sm); line-height: var(--leading-sm); color: var(--text-primary); outline: none; transition: border-color var(--transition-fast), box-shadow var(--transition-fast); }
.source-input:focus { border-color: var(--accent-border); box-shadow: 0 0 0 3px var(--accent-soft); }
.source-input::placeholder { color: var(--text-tertiary); }
.action-btns { display: flex; gap: var(--space-2); flex-shrink: 0; }

.empty-state { text-align: center; padding: var(--space-8); color: var(--text-tertiary); }
.empty-icon { font-size: var(--font-size-3xl); margin-bottom: var(--space-3); opacity: 0.4; }
.skeleton { background: linear-gradient(90deg, var(--bg-subtle) 25%, var(--border-subtle) 50%, var(--bg-subtle) 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite; border-radius: var(--radius-sm); }
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }

/* Modal */
.modal-overlay { position: fixed; inset: 0; z-index: var(--z-modal); background: color-mix(in srgb, var(--text-primary) 40%, transparent); display: flex; align-items: center; justify-content: center; padding: var(--space-4); }
[data-theme='dark'] .modal-overlay { background: color-mix(in srgb, var(--bg-canvas) 70%, transparent); }
.modal { width: 100%; max-width: 480px; background: var(--bg-elevated); border: 1px solid var(--border-default); border-radius: var(--radius-lg); overflow: hidden; box-shadow: var(--shadow-lg); }
.modal-head { display: flex; justify-content: space-between; align-items: center; padding: var(--space-4); border-bottom: 1px solid var(--border-subtle); }
.modal-head h3 { color: var(--text-primary); font-size: var(--font-size-md); line-height: var(--leading-md); }
.btn-close { color: var(--text-tertiary); font-size: var(--font-size-md); line-height: var(--leading-md); background: none; border: none; cursor: pointer; }
.modal-body { padding: var(--space-4); }
.modal-desc { color: var(--text-secondary); font-size: var(--font-size-sm); line-height: var(--leading-sm); margin-bottom: var(--space-3); }
.reject-note { display: grid; gap: var(--space-1); }
.reject-note span { color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: var(--leading-xs); }
.reject-note textarea { width: 100%; box-sizing: border-box; resize: vertical; }
.input { padding: var(--space-2) var(--space-3); border: 1px solid var(--border-default); border-radius: var(--radius-md); background: var(--bg-surface); color: var(--text-primary); font-size: var(--font-size-sm); line-height: var(--leading-sm); outline: none; transition: border-color var(--transition-fast), box-shadow var(--transition-fast); }
.input:focus { border-color: var(--accent-border); box-shadow: 0 0 0 3px var(--accent-soft); }
.form-error { margin-top: var(--space-2); padding: var(--space-2) var(--space-3); border-radius: var(--radius-sm); background: var(--danger-soft); border: 1px solid var(--danger-border); color: var(--danger); font-size: var(--font-size-xs); line-height: var(--leading-xs); }
.modal-footer { display: flex; justify-content: flex-end; gap: var(--space-2); padding: var(--space-4); border-top: 1px solid var(--border-subtle); }

/* toast */
.toast { position: fixed; bottom: var(--space-5); left: 50%; transform: translateX(-50%); z-index: var(--z-toast); padding: var(--space-2) var(--space-4); background: var(--bg-elevated); border: 1px solid var(--danger-border); border-radius: var(--radius-md); box-shadow: var(--shadow-lg); color: var(--danger); font-size: var(--font-size-sm); line-height: var(--leading-sm); }
.toast-enter-active, .toast-leave-active { transition: opacity var(--transition-base), transform var(--transition-base); }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateX(-50%) translateY(var(--space-2)); }

@media (max-width: 768px) {
  .stats-row { flex-wrap: wrap; }
  .stat-chip { min-width: calc(50% - var(--space-3)); }
  .toolbar { flex-direction: column; align-items: stretch; }
  .search-input { width: 100%; }
  .audit-card__meta { grid-template-columns: repeat(2, 1fr); }
}
</style>
