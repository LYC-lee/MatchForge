<script setup lang="ts">
import { ref, computed, watch, nextTick, onUnmounted } from 'vue'
import { useEnterpriseContext } from '@/composables/useEnterpriseContext'
import { onDemoRefresh } from '@/composables/useDemoRefresh'
import {
  getSupplierLeads,
  viewLead,
  declineLead,
  createQuotation,
  type SupplierLead,
} from '@/api/enterprise'
import { useDemo } from '@/composables/useDemo'
import AppButton from '@/components/ui/AppButton.vue'
import Tag from '@/components/ui/Tag.vue'
import { leadStatusLabel, leadTagType } from '@/data/leadStatus'

const { current, currentEnterpriseId } = useEnterpriseContext()
const demo = useDemo()

const isDemo = computed(() => demo.isDemo.value)

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
  if (isDemo.value) {
    // demo 模式: 供应商视角由 useDemo 管理 (demo_rfqs.candidates_json 动态匹配)
    loading.value = demo.loadingSupplier.value
    return
  }
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

onDemoRefresh(() => {
  if (isDemo.value) {
    demo.fetchSupplierView()
  } else {
    fetchLeads(currentEnterpriseId.value)
  }
})

/** demo 模式: 把 supplierView.items 映射成统一的 lead 形态 */
const demoLeads = computed<SupplierLead[]>(() => {
  const items = demo.supplierView.value?.items || []
  return items.map((i) => ({
    id: i.rfq_id,
    rfq_id: i.rfq_id,
    rfq_number: i.rfq_number,
    rfq_title: i.title || i.rfq_number,
    rfq_status: i.rfq_status,
    buyer_company_id: i.buyer_company_id,
    buyer_name: i.buyer_name || `企业${i.buyer_company_id}`,
    supplier_company_id: currentEnterpriseId.value,
    part_number: i.part_number || null,
    part_name: i.part_name || null,
    quantity: i.quantity,
    unit: i.unit || null,
    target_price: i.target_price ?? null,
    lead_time_days: i.lead_time_days ?? null,
    accept_alternatives: i.accept_alternatives ?? null,
    match_score: i.my_match_score ?? null,
    match_reason: i.my_match_reason ?? null,
    status: i.my_quote ? 'quoted' : (i.rfq_status === 'closed' ? 'declined' : 'sent'),
    sent_at: null,
    viewed_at: null,
    created_at: i.created_at,
    // demo 扩展字段 (my_quote / is_selected) 供模板展示
    _my_quote: i.my_quote,
    _is_selected: i.is_selected,
  } as unknown as SupplierLead))
})

const filteredLeads = computed(() => {
  const source = isDemo.value ? demoLeads.value : leads.value
  if (activeTab.value === 'all') return source
  return source.filter((l) => l.status === activeTab.value)
})

const stats = computed(() => {
  const source = isDemo.value ? demoLeads.value : leads.value
  return {
    total: source.length,
    new: source.filter((l) => l.status === 'sent' || l.status === 'pending').length,
    viewed: source.filter((l) => l.status === 'viewed').length,
    quoted: source.filter((l) => l.status === 'quoted').length,
  }
})

function statusLabel(s: string) {
  return leadStatusLabel(s)
}

function statusTagType(s: string) {
  return leadTagType(s)
}

// 失败提示 toast（替代静默 catch）
const toast = ref('')
let toastTimer: ReturnType<typeof setTimeout> | undefined
function showToast(msg: string) {
  toast.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = '' }, 3000)
}
onUnmounted(() => clearTimeout(toastTimer))

async function handleView(lead: SupplierLead) {
  if (isDemo.value) return // demo 模式只读, 无需标记查看
  try {
    await viewLead(lead.id)
    await fetchLeads(currentEnterpriseId.value)
  } catch (e: any) {
    showToast(e?.message || '标记查看失败，请稍后重试')
  }
}

// 拒绝：自定义弹层 + 内嵌理由输入（替代原生 prompt）
const declineTarget = ref<SupplierLead | null>(null)
const declineNote = ref('')
const declineNoteInput = ref<HTMLTextAreaElement | null>(null)
const declining = ref(false)
function startDecline(lead: SupplierLead) {
  if (isDemo.value) return
  declineTarget.value = lead
  declineNote.value = ''
  nextTick(() => declineNoteInput.value?.focus())
}
function closeDecline() {
  if (declining.value) return
  declineTarget.value = null
  declineNote.value = ''
}
async function confirmDecline() {
  if (!declineTarget.value) return
  declining.value = true
  try {
    await declineLead(declineTarget.value.id, declineNote.value || undefined)
    declineTarget.value = null
    declineNote.value = ''
    await fetchLeads(currentEnterpriseId.value)
  } catch (e: any) {
    showToast(e?.message || '拒绝失败，请稍后重试')
  } finally {
    declining.value = false
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
  nextTick(() => quoteFirstInput.value?.focus())
}

const quoteFirstInput = ref<HTMLInputElement | null>(null)

function closeQuote() {
  quoteLead.value = null
}

async function submitQuote() {
  if (!quoteLead.value) return
  if (isDemo.value) {
    // demo 模式: 报价由买方 simulate-quotes 统一生成; 此处提示用户
    submitError.value = '演示沙盘模式下, 报价由采购方执行「模拟报价」统一生成 (基于供应商品类/直接关系动态计算), 供应商工作台为只读视角。'
    return
  }
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
    <div v-if="isDemo" class="notice-bar notice-bar--demo">演示沙盘数据 · 线索来自当前企业作为候选供应商收到的 demo RFQ (直接关系动态匹配, 供应商视角只读)</div>

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
              <Tag :type="statusTagType(lead.status)" :value="statusLabel(lead.status)" />
            </div>
          </div>

          <div class="lead-card__meta">
            <div class="lead-meta-item"><span class="meta-label">采购方</span><span>{{ lead.buyer_name || `企业${lead.buyer_company_id}` }}</span></div>
            <div class="lead-meta-item"><span class="meta-label">零件</span><span>{{ lead.part_name || lead.part_number || '-' }}</span></div>
            <div class="lead-meta-item"><span class="meta-label">数量</span><span>{{ lead.quantity?.toLocaleString() || '-' }} {{ lead.unit || '' }}</span></div>
            <div class="lead-meta-item"><span class="meta-label">目标价</span><span>{{ lead.target_price != null ? `¥${lead.target_price}` : '-' }}</span></div>
            <div class="lead-meta-item"><span class="meta-label">交期</span><span>{{ lead.lead_time_days ? `${lead.lead_time_days}天` : '-' }}</span></div>
            <div class="lead-meta-item"><span class="meta-label">接受替代</span><span>{{ lead.accept_alternatives ? '是' : '否' }}</span></div>
            <div v-if="isDemo && (lead as any)._my_quote" class="lead-meta-item"><span class="meta-label">我的报价</span><span class="meta-quote">¥{{ (lead as any)._my_quote.unit_price }} · 交期{{ (lead as any)._my_quote.lead_time_days || '-' }}天</span></div>
            <div v-if="isDemo && (lead as any)._is_selected" class="lead-meta-item"><span class="meta-label">中标状态</span><span class="meta-win">已选定</span></div>
          </div>

          <div class="lead-card__actions">
            <AppButton v-if="!isDemo && (lead.status === 'sent' || lead.status === 'pending')" variant="ghost" size="sm" @click="handleView(lead)">标记已查看</AppButton>
            <AppButton v-if="!isDemo && lead.status !== 'quoted' && lead.status !== 'declined'" variant="danger" size="sm" @click="startDecline(lead)">拒绝</AppButton>
            <AppButton v-if="!isDemo && lead.status !== 'declined' && lead.status !== 'quoted'" size="sm" @click="openQuote(lead)">提交报价</AppButton>
            <span v-if="lead.status === 'quoted'" class="quoted-tag">已报价</span>
          </div>
        </div>
      </div>
    </template>

    <!-- 报价弹层 -->
    <div v-if="quoteLead" class="modal-overlay" @click.self="closeQuote">
      <div
        class="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="quote-modal-title"
        @keydown.esc="closeQuote"
      >
        <div class="modal-head">
          <h3 id="quote-modal-title">提交报价 - {{ quoteLead.rfq_number }}</h3>
          <button class="btn-close" aria-label="关闭" @click="closeQuote">✕</button>
        </div>
        <div class="modal-body">
          <div class="modal-info">
            <span>采购方: {{ quoteLead.buyer_name }}</span>
            <span>零件: {{ quoteLead.part_name || quoteLead.part_number }}</span>
            <span>数量: {{ quoteLead.quantity }} {{ quoteLead.unit }}</span>
            <span v-if="quoteLead.target_price">目标价: ¥{{ quoteLead.target_price }}</span>
          </div>
          <div class="quote-form">
            <label><span>单价 (¥) *</span><input ref="quoteFirstInput" v-model.number="quoteForm.unit_price" type="number" step="0.01" class="input" /></label>
            <label><span>MOQ</span><input v-model.number="quoteForm.moq" type="number" class="input" /></label>
            <label><span>交期 (天)</span><input v-model.number="quoteForm.lead_time_days" type="number" class="input" /></label>
            <label><span>库存数量</span><input v-model.number="quoteForm.stock_qty" type="number" class="input" /></label>
            <label class="checkbox-label"><input v-model="quoteForm.is_in_stock" type="checkbox" /><span>有现货</span></label>
            <label class="full"><span>备注</span><textarea v-model="quoteForm.note" class="input" rows="2" /></label>
          </div>
          <div v-if="submitError" class="form-error" role="alert">{{ submitError }}</div>
        </div>
        <div class="modal-footer">
          <AppButton variant="secondary" @click="closeQuote">取消</AppButton>
          <AppButton :loading="submitting" :disabled="quoteForm.unit_price <= 0" @click="submitQuote">提交报价</AppButton>
        </div>
      </div>
    </div>

    <!-- 拒绝确认弹层（内嵌理由输入，替代原生 prompt；焦点圈禁） -->
    <div v-if="declineTarget" class="modal-overlay" @click.self="closeDecline">
      <div
        class="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="decline-modal-title"
        @keydown.esc="closeDecline"
      >
        <div class="modal-head">
          <h3 id="decline-modal-title">拒绝该线索？</h3>
          <button class="btn-close" aria-label="关闭" :disabled="declining" @click="closeDecline">✕</button>
        </div>
        <div class="modal-body">
          <p class="modal-desc">拒绝后将不再展示该线索。可填写拒绝理由（可选）。</p>
          <label class="decline-note">
            <span>拒绝理由（可选）</span>
            <textarea ref="declineNoteInput" v-model="declineNote" class="input" rows="2" placeholder="如：型号不符 / 无库存 / 价格过低…" />
          </label>
        </div>
        <div class="modal-footer">
          <AppButton variant="secondary" :disabled="declining" @click="closeDecline">取消</AppButton>
          <AppButton variant="danger" :loading="declining" @click="confirmDecline">确认拒绝</AppButton>
        </div>
      </div>
    </div>

    <Transition name="toast">
      <div v-if="toast" class="toast" role="alert">{{ toast }}</div>
    </Transition>
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
.eyebrow { color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: var(--leading-xs); font-weight: 700; }
.page-title { font-size: var(--font-size-xl); line-height: var(--leading-xl); font-weight: 700; margin-top: var(--space-1); }
.page-desc { color: var(--text-secondary); margin-top: var(--space-1); font-size: var(--font-size-sm); line-height: var(--leading-sm); }
.notice-bar { padding: var(--space-3) var(--space-4); border-radius: var(--radius-md); border: 1px solid var(--warning-border); background: var(--warning-soft); color: var(--warning); font-size: var(--font-size-sm); line-height: var(--leading-sm); margin-bottom: var(--space-4); }
.notice-bar--demo { border: 1px solid var(--accent-border); background: var(--accent-soft); color: var(--accent-text); }
.meta-quote { color: var(--accent-text); font-weight: 600; }
.meta-win { color: var(--success); font-weight: 700; }
.stats-row { display: flex; gap: var(--space-3); margin-bottom: var(--space-4); }
.stat-chip { flex: 1; display: flex; flex-direction: column; gap: var(--space-1); padding: var(--space-3) var(--space-4); background: var(--bg-surface); border: 1px solid var(--border-default); border-radius: var(--radius-lg); }
.stat-chip__num { font-size: var(--font-size-2xl); line-height: var(--leading-2xl); font-weight: 700; color: var(--text-primary); font-family: var(--font-mono); }
.stat-chip__label { font-size: var(--font-size-xs); line-height: var(--leading-xs); color: var(--text-tertiary); }
.tabs { display: flex; gap: 0; margin-bottom: var(--space-4); border-bottom: 1px solid var(--border-default); }
.tab { padding: var(--space-2) var(--space-5); border: none; background: none; font-size: var(--font-size-sm); line-height: var(--leading-sm); color: var(--text-secondary); cursor: pointer; border-bottom: 2px solid transparent; transition: color var(--transition-fast), border-color var(--transition-fast); }
.tab:hover { color: var(--text-primary); }
.tab.active { color: var(--accent-text); border-bottom-color: var(--accent); font-weight: 600; }
.card { background: var(--bg-surface); border: 1px solid var(--border-default); border-radius: var(--radius-lg); margin-bottom: var(--space-3); }
.card__body { padding: var(--space-4); }
.leads-list { display: flex; flex-direction: column; gap: var(--space-3); }
.lead-card { padding: var(--space-4); }
.lead-card__head { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-3); margin-bottom: var(--space-3); }
.lead-card__title { font-weight: 600; font-size: var(--font-size-md); line-height: var(--leading-md); color: var(--text-primary); }
.lead-card__spec { font-size: var(--font-size-sm); line-height: var(--leading-sm); color: var(--text-tertiary); margin-top: var(--space-1); }
.lead-card__badges { display: flex; gap: var(--space-2); align-items: center; flex-shrink: 0; }
.lead-card__meta { display: flex; gap: var(--space-5); margin-bottom: var(--space-3); font-size: var(--font-size-sm); line-height: var(--leading-sm); flex-wrap: wrap; }
.lead-meta-item { display: flex; gap: var(--space-1); }
.meta-label { color: var(--text-tertiary); }
.lead-card__actions { display: flex; justify-content: flex-end; gap: var(--space-2); padding-top: var(--space-3); border-top: 1px solid var(--border-subtle); }
.quoted-tag { color: var(--success); font-size: var(--font-size-sm); line-height: var(--leading-sm); font-weight: 600; padding: var(--space-1) var(--space-2); }
.mono { font-family: var(--font-mono); font-size: var(--font-size-xs); }
.empty-state { text-align: center; padding: var(--space-8); color: var(--text-tertiary); }
.empty-icon { font-size: var(--font-size-3xl); margin-bottom: var(--space-3); opacity: 0.4; }
.skeleton { background: linear-gradient(90deg, var(--bg-subtle) 25%, var(--border-subtle) 50%, var(--bg-subtle) 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite; border-radius: var(--radius-sm); }
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }

/* Modal */
.modal-overlay { position: fixed; inset: 0; z-index: var(--z-modal); background: color-mix(in srgb, var(--text-primary) 40%, transparent); display: flex; align-items: center; justify-content: center; padding: var(--space-4); }
[data-theme='dark'] .modal-overlay { background: color-mix(in srgb, var(--bg-canvas) 70%, transparent); }
.modal { width: 100%; max-width: 520px; background: var(--bg-elevated); border: 1px solid var(--border-default); border-radius: var(--radius-lg); overflow: hidden; box-shadow: var(--shadow-lg); }
.modal-head { display: flex; justify-content: space-between; align-items: center; padding: var(--space-4); border-bottom: 1px solid var(--border-subtle); }
.modal-head h3 { color: var(--text-primary); font-size: var(--font-size-md); line-height: var(--leading-md); }
.btn-close { color: var(--text-tertiary); font-size: var(--font-size-md); line-height: var(--leading-md); background: none; border: none; cursor: pointer; }
.modal-body { padding: var(--space-4); }
.modal-desc { color: var(--text-secondary); font-size: var(--font-size-sm); line-height: var(--leading-sm); margin-bottom: var(--space-3); }
.modal-info { display: grid; gap: var(--space-1); margin-bottom: var(--space-4); padding: var(--space-3); background: var(--bg-subtle); border-radius: var(--radius-md); font-size: var(--font-size-sm); line-height: var(--leading-sm); color: var(--text-secondary); }
.quote-form { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-3); }
.quote-form label { display: grid; gap: var(--space-1); }
.quote-form label.full { grid-column: 1 / -1; }
.quote-form label.checkbox-label { flex-direction: row; align-items: center; gap: var(--space-2); display: flex; }
.quote-form span { color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: var(--leading-xs); }
.input { padding: var(--space-2) var(--space-3); border: 1px solid var(--border-default); border-radius: var(--radius-md); background: var(--bg-surface); color: var(--text-primary); font-size: var(--font-size-sm); line-height: var(--leading-sm); width: 100%; box-sizing: border-box; outline: none; transition: border-color var(--transition-fast), box-shadow var(--transition-fast); }
.input:focus { border-color: var(--accent-border); box-shadow: 0 0 0 3px var(--accent-soft); }
.form-error { margin-top: var(--space-3); padding: var(--space-2) var(--space-3); border-radius: var(--radius-sm); background: var(--danger-soft); border: 1px solid var(--danger-border); color: var(--danger); font-size: var(--font-size-xs); line-height: var(--leading-xs); }
.modal-footer { display: flex; justify-content: flex-end; gap: var(--space-2); padding: var(--space-4); border-top: 1px solid var(--border-subtle); }
.decline-note { display: grid; gap: var(--space-1); }
.decline-note span { color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: var(--leading-xs); }
.decline-note textarea { width: 100%; box-sizing: border-box; resize: vertical; }

/* toast */
.toast {
  position: fixed;
  bottom: var(--space-5);
  left: 50%;
  transform: translateX(-50%);
  z-index: var(--z-toast);
  padding: var(--space-2) var(--space-4);
  background: var(--bg-elevated);
  border: 1px solid var(--danger-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  color: var(--danger);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
}
.toast-enter-active, .toast-leave-active { transition: opacity var(--transition-base), transform var(--transition-base); }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateX(-50%) translateY(var(--space-2)); }

@media (max-width: 768px) { .stats-row { flex-wrap: wrap; } .stat-chip { min-width: calc(50% - var(--space-3)); } .quote-form { grid-template-columns: 1fr; } }
</style>
