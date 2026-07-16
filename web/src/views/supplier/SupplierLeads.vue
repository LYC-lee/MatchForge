<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useEnterpriseContext } from '@/composables/useEnterpriseContext'
import {
  getSupplierLeads,
  viewLead,
  declineLead,
  createQuotation,
  type SupplierLead,
} from '@/api/enterprise'
import AppButton from '@/components/ui/AppButton.vue'

const { current, currentEnterpriseId } = useEnterpriseContext()

const leads = ref<SupplierLead[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const activeTab = ref<'all' | 'sent' | 'viewed' | 'quoted' | 'declined'>('all')
const quoteLead = ref<SupplierLead | null>(null)
const quoteForm = ref({
  unit_price: 0,
  moq: undefined as number | undefined,
  lead_time_days: undefined as number | undefined,
  stock_qty: undefined as number | undefined,
  is_in_stock: false,
  note: '',
})
const submitting = ref(false)
const submitError = ref<string | null>(null)

async function fetchLeads(companyId: number) {
  loading.value = true
  error.value = null
  try {
    const res = await getSupplierLeads(companyId)
    leads.value = (res.data?.items || []) as SupplierLead[]
  } catch (e: any) {
    error.value = e?.message || '供应商线索接口不可用'
    leads.value = []
  } finally {
    loading.value = false
  }
}

watch(currentEnterpriseId, (id) => {
  if (id) fetchLeads(id)
}, { immediate: true })

const filteredLeads = computed(() => {
  if (activeTab.value === 'all') return leads.value
  return leads.value.filter((l) => l.status === activeTab.value)
})

const stats = computed(() => ({
  total: leads.value.length,
  new: leads.value.filter((l) => l.status === 'sent' || l.status === 'pending').length,
  viewed: leads.value.filter((l) => l.status === 'viewed').length,
  quoted: leads.value.filter((l) => l.status === 'quoted').length,
}))

function statusLabel(s: string) {
  const map: Record<string, string> = {
    pending: '待发送', sent: '新线索', viewed: '已查看', quoted: '已报价', declined: '已拒绝',
  }
  return map[s] || s
}

function statusClass(s: string) {
  const map: Record<string, string> = {
    pending: 'tag-gray', sent: 'tag-blue', viewed: 'tag-yellow', quoted: 'tag-green', declined: 'tag-gray',
  }
  return map[s] || 'tag-gray'
}

async function handleView(lead: SupplierLead) {
  try {
    await viewLead(lead.id)
    await fetchLeads(currentEnterpriseId.value)
  } catch {
    // 静默失败
  }
}

async function handleDecline(lead: SupplierLead) {
  const note = prompt('拒绝理由（可选）:')
  try {
    await declineLead(lead.id, note || undefined)
    await fetchLeads(currentEnterpriseId.value)
  } catch {
    // 静默失败
  }
}

function openQuote(lead: SupplierLead) {
  quoteLead.value = lead
  quoteForm.value = {
    unit_price: lead.target_price || 0,
    moq: undefined,
    lead_time_days: lead.lead_time_days || undefined,
    stock_qty: undefined,
    is_in_stock: false,
    note: '',
  }
  submitError.value = null
}

async function submitQuote() {
  if (!quoteLead.value) return
  submitting.value = true
  submitError.value = null
  try {
    await createQuotation(quoteLead.value.rfq_id, {
      supplier_company_id: currentEnterpriseId.value,
      part_number: quoteLead.value.part_number || undefined,
      unit_price: quoteForm.value.unit_price,
      moq: quoteForm.value.moq,
      lead_time_days: quoteForm.value.lead_time_days,
      stock_qty: quoteForm.value.stock_qty,
      is_in_stock: quoteForm.value.is_in_stock,
      note: quoteForm.value.note || undefined,
    })
    quoteLead.value = null
    await fetchLeads(currentEnterpriseId.value)
  } catch (e: any) {
    submitError.value = e?.message || '报价提交失败'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="supplier-page">
    <div class="page-head">
      <div>
        <span class="eyebrow">{{ current.company.name }}</span>
        <h2 class="page-title">供应商线索</h2>
        <p class="page-desc">查看当前企业收到的 RFQ 线索, 标记查看/拒绝, 并在线提交报价。</p>
      </div>
    </div>

    <div v-if="loading" class="card"><div class="card__body"><div v-for="i in 3" :key="i" class="skeleton" style="height: 60px; margin-bottom: 8px" /></div></div>
    <div v-else-if="error" class="notice-bar">供应商线索接口不可用: {{ error }}</div>

    <template v-else>
      <!-- 统计 -->
      <div class="stats-row">
        <div class="stat-chip"><span class="stat-chip__num">{{ stats.total }}</span><span class="stat-chip__label">全部线索</span></div>
        <div class="stat-chip"><span class="stat-chip__num">{{ stats.new }}</span><span class="stat-chip__label">新线索</span></div>
        <div class="stat-chip"><span class="stat-chip__num">{{ stats.viewed }}</span><span class="stat-chip__label">已查看</span></div>
        <div class="stat-chip"><span class="stat-chip__num">{{ stats.quoted }}</span><span class="stat-chip__label">已报价</span></div>
      </div>

      <!-- Tabs -->
      <div class="tabs">
        <button class="tab" :class="{ active: activeTab === 'all' }" @click="activeTab = 'all'">全部</button>
        <button class="tab" :class="{ active: activeTab === 'sent' }" @click="activeTab = 'sent'">新线索</button>
        <button class="tab" :class="{ active: activeTab === 'viewed' }" @click="activeTab = 'viewed'">已查看</button>
        <button class="tab" :class="{ active: activeTab === 'quoted' }" @click="activeTab = 'quoted'">已报价</button>
        <button class="tab" :class="{ active: activeTab === 'declined' }" @click="activeTab = 'declined'">已拒绝</button>
      </div>

      <div v-if="filteredLeads.length === 0" class="card">
        <div class="card__body empty-state">
          <p class="empty-icon">📋</p>
          <p>暂无线索</p>
        </div>
      </div>

      <div v-else class="leads-list">
        <div v-for="lead in filteredLeads" :key="lead.id" class="lead-card card">
          <div class="lead-card__head">
            <div class="lead-card__info">
              <div class="lead-card__title">{{ lead.rfq_title || lead.rfq_number }}</div>
              <div class="lead-card__spec mono">{{ lead.rfq_number }} · {{ lead.part_name || lead.part_number || '未指定零件' }}</div>
            </div>
            <div class="lead-card__badges">
              <span class="tag" :class="statusClass(lead.status)">{{ statusLabel(lead.status) }}</span>
            </div>
          </div>

          <div class="lead-card__meta">
            <div class="lead-meta-item"><span class="meta-label">采购方</span><span>{{ lead.buyer_name || `企业${lead.buyer_company_id}` }}</span></div>
            <div class="lead-meta-item"><span class="meta-label">零件</span><span>{{ lead.part_name || lead.part_number || '-' }}</span></div>
            <div class="lead-meta-item"><span class="meta-label">数量</span><span>{{ lead.quantity?.toLocaleString() || '-' }} {{ lead.unit || '' }}</span></div>
            <div class="lead-meta-item"><span class="meta-label">目标价</span><span>{{ lead.target_price != null ? `¥${lead.target_price}` : '-' }}</span></div>
            <div class="lead-meta-item"><span class="meta-label">交期</span><span>{{ lead.lead_time_days ? `${lead.lead_time_days}天` : '-' }}</span></div>
            <div class="lead-meta-item"><span class="meta-label">接受替代</span><span>{{ lead.accept_alternatives ? '是' : '否' }}</span></div>
          </div>

          <div class="lead-card__actions">
            <AppButton v-if="lead.status === 'sent' || lead.status === 'pending'" variant="ghost" size="sm" @click="handleView(lead)">标记已查看</AppButton>
            <AppButton v-if="lead.status !== 'quoted' && lead.status !== 'declined'" variant="danger" size="sm" @click="handleDecline(lead)">拒绝</AppButton>
            <AppButton v-if="lead.status !== 'declined' && lead.status !== 'quoted'" variant="primary" size="sm" @click="openQuote(lead)">提交报价</AppButton>
            <span v-if="lead.status === 'quoted'" class="quoted-tag">已报价</span>
          </div>
        </div>
      </div>
    </template>

    <!-- 报价弹层 -->
    <div v-if="quoteLead" class="modal-overlay" @click.self="quoteLead = null">
      <div class="modal">
        <div class="modal-head">
          <h3>提交报价 - {{ quoteLead.rfq_number }}</h3>
          <button class="btn-close" @click="quoteLead = null">✕</button>
        </div>
        <div class="modal-body">
          <div class="modal-info">
            <span>采购方: {{ quoteLead.buyer_name }}</span>
            <span>零件: {{ quoteLead.part_name || quoteLead.part_number }}</span>
            <span>数量: {{ quoteLead.quantity }} {{ quoteLead.unit }}</span>
            <span v-if="quoteLead.target_price">目标价: ¥{{ quoteLead.target_price }}</span>
          </div>
          <div class="quote-form">
            <label><span>单价 (¥) *</span><input v-model.number="quoteForm.unit_price" type="number" step="0.01" class="input" /></label>
            <label><span>MOQ</span><input v-model.number="quoteForm.moq" type="number" class="input" /></label>
            <label><span>交期 (天)</span><input v-model.number="quoteForm.lead_time_days" type="number" class="input" /></label>
            <label><span>库存数量</span><input v-model.number="quoteForm.stock_qty" type="number" class="input" /></label>
            <label class="checkbox-label"><input v-model="quoteForm.is_in_stock" type="checkbox" /><span>有现货</span></label>
            <label class="full"><span>备注</span><textarea v-model="quoteForm.note" class="input" rows="2" /></label>
          </div>
          <div v-if="submitError" class="form-error">{{ submitError }}</div>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="quoteLead = null">取消</button>
          <button class="btn-submit" :disabled="submitting || quoteForm.unit_price <= 0" @click="submitQuote">{{ submitting ? '提交中…' : '提交报价' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.supplier-page {
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
.eyebrow { color: var(--text-tertiary); font-size: var(--font-size-xs); font-weight: 700; }
.page-title { font-size: var(--font-size-xl); font-weight: 700; margin-top: 4px; }
.page-desc { color: var(--text-secondary); margin-top: 4px; font-size: var(--font-size-sm); }
.notice-bar { padding: var(--space-3) var(--space-4); border-radius: 6px; border: 1px solid rgba(234, 179, 8, 0.25); background: var(--warning-soft); color: var(--warning); font-size: var(--font-size-sm); }
.stats-row { display: flex; gap: var(--space-3); margin-bottom: var(--space-4); }
.stat-chip { flex: 1; display: flex; flex-direction: column; gap: 4px; padding: var(--space-3) var(--space-4); background: var(--bg-2); border: 1px solid var(--border-default); border-radius: 8px; }
.stat-chip__num { font-size: var(--font-size-2xl); font-weight: 700; color: var(--text-primary); }
.stat-chip__label { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.tabs { display: flex; gap: 0; margin-bottom: var(--space-4); border-bottom: 1px solid var(--border-default); }
.tab { padding: 8px 20px; border: none; background: none; font-size: var(--font-size-sm); color: var(--text-secondary); cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.15s; }
.tab:hover { color: var(--text-primary); }
.tab.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
.card { background: var(--bg-2); border: 1px solid var(--border-default); border-radius: 8px; margin-bottom: var(--space-3); }
.card__body { padding: var(--space-4); }
.leads-list { display: flex; flex-direction: column; gap: var(--space-3); }
.lead-card { padding: var(--space-4); }
.lead-card__head { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-3); margin-bottom: var(--space-3); }
.lead-card__title { font-weight: 600; font-size: var(--font-size-md); color: var(--text-primary); }
.lead-card__spec { font-size: var(--font-size-sm); color: var(--text-tertiary); margin-top: 4px; }
.lead-card__badges { display: flex; gap: var(--space-2); align-items: center; flex-shrink: 0; }
.lead-card__meta { display: flex; gap: var(--space-5); margin-bottom: var(--space-3); font-size: var(--font-size-sm); flex-wrap: wrap; }
.lead-meta-item { display: flex; gap: 6px; }
.meta-label { color: var(--text-tertiary); }
.lead-card__actions { display: flex; justify-content: flex-end; gap: var(--space-2); padding-top: var(--space-3); border-top: 1px solid var(--border-subtle); }
.quoted-tag { color: var(--success); font-size: var(--font-size-sm); font-weight: 600; padding: 4px 8px; }
.tag { font-size: var(--font-size-xs); padding: 2px 8px; border-radius: var(--radius-sm); }
.tag-blue { color: var(--accent); background: var(--accent-soft); }
.tag-yellow { color: var(--warning); background: var(--warning-soft); }
.tag-green { color: var(--success); background: var(--success-soft); }
.tag-gray { color: var(--text-tertiary); background: var(--bg-3); }
.mono { font-family: var(--font-mono); font-size: var(--font-size-xs); }
.empty-state { text-align: center; padding: var(--space-8); color: var(--text-tertiary); }
.empty-icon { font-size: 40px; margin-bottom: var(--space-3); opacity: 0.4; }
.skeleton { background: linear-gradient(90deg, var(--bg-3) 25%, var(--border-subtle) 50%, var(--bg-3) 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite; border-radius: var(--radius-sm); }
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }

/* Modal */
.modal-overlay { position: fixed; inset: 0; z-index: 100; background: rgba(0, 0, 0, 0.6); display: flex; align-items: center; justify-content: center; padding: var(--space-4); }
.modal { width: 100%; max-width: 520px; background: var(--bg-1); border: 1px solid var(--border-default); border-radius: 12px; overflow: hidden; }
.modal-head { display: flex; justify-content: space-between; align-items: center; padding: var(--space-4); border-bottom: 1px solid var(--border-subtle); }
.modal-head h3 { color: var(--text-primary); font-size: var(--font-size-md); }
.btn-close { color: var(--text-tertiary); font-size: var(--font-size-md); background: none; border: none; cursor: pointer; }
.modal-body { padding: var(--space-4); }
.modal-info { display: grid; gap: 6px; margin-bottom: var(--space-4); padding: var(--space-3); background: var(--bg-2); border-radius: 6px; font-size: var(--font-size-sm); color: var(--text-secondary); }
.quote-form { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-3); }
.quote-form label { display: grid; gap: 4px; }
.quote-form label.full { grid-column: 1 / -1; }
.quote-form label.checkbox-label { flex-direction: row; align-items: center; gap: var(--space-2); display: flex; }
.quote-form span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.input { padding: 8px 10px; border: 1px solid var(--border-default); border-radius: 6px; background: var(--bg-2); color: var(--text-primary); font-size: var(--font-size-sm); width: 100%; box-sizing: border-box; }
.form-error { margin-top: var(--space-3); padding: var(--space-2) var(--space-3); border-radius: 4px; background: var(--danger-soft); color: var(--danger); font-size: var(--font-size-xs); }
.modal-footer { display: flex; justify-content: flex-end; gap: var(--space-2); padding: var(--space-4); border-top: 1px solid var(--border-subtle); }
.btn-cancel { padding: 8px 16px; border-radius: 6px; border: 1px solid var(--border-default); background: var(--bg-2); color: var(--text-secondary); font-size: var(--font-size-sm); cursor: pointer; }
.btn-submit { padding: 8px 16px; border-radius: 6px; background: var(--gradient-accent); color: #fff; font-size: var(--font-size-sm); font-weight: 600; border: none; cursor: pointer; }
.btn-submit:disabled { opacity: 0.5; cursor: not-allowed; }
@media (max-width: 768px) { .stats-row { flex-wrap: wrap; } .stat-chip { min-width: calc(50% - var(--space-3)); } .quote-form { grid-template-columns: 1fr; } }
</style>
