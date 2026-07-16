<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useEnterpriseContext } from '@/composables/useEnterpriseContext'
import { useDashboard } from '@/composables/useDashboard'
import { severityRank } from '@/composables/useDashboard'
import { useRfq } from '@/composables/useRfq'
import { useDemo } from '@/composables/useDemo'
import { recalculateShortages } from '@/api/enterprise'
import type { DashboardShortage, DashboardAction } from '@/api/enterprise'

const route = useRoute()
const router = useRouter()
const { current, currentEnterpriseId } = useEnterpriseContext()
const { dashboard, loading, dataSource, refresh: refreshDashboard } = useDashboard()
const { rfqs, create: createRfq, send: sendRfq, loadComparison, comparison } = useRfq()
const demo = useDemo()

const isDemo = computed(() => demo.isDemo.value)

const selectedPart = computed(() => String(route.query.part || ''))
const selectedShortage = computed<DashboardShortage | undefined>(() => {
  const items = dashboard.value?.shortages?.items || []
  if (selectedPart.value) {
    const found = items.find(
      (s) => s.part_number === selectedPart.value || s.part_name === selectedPart.value,
    )
    if (found) return found
  }
  return items[0]
})

// RFQ 创建表单
const showRfqForm = ref(false)
const rfqForm = ref({
  title: '',
  part_number: '',
  part_name: '',
  quantity: 1,
  unit: '个',
  target_price: undefined as number | undefined,
  lead_time_days: undefined as number | undefined,
  supplier_candidates: [] as number[],
})
const creating = ref(false)
const createError = ref<string | null>(null)
const lastCreatedRfqId = ref<number | null>(null)

// 报价对比
const compareRfqId = ref<number | null>(null)

const shortages = computed(() => dashboard.value?.shortages?.items || [])
const actions = computed(() => {
  const items = dashboard.value?.recommended_actions?.items || []
  return [...items].sort((a, b) => severityRank(b.priority) - severityRank(a.priority))
})

/** 统一 RFQ 列表: demo 模式取 demo.demoRfqs, 否则取真实 useRfq.rfqs */
const rfqList = computed(() => {
  if (isDemo.value) return demo.demoRfqs.value as unknown as typeof rfqs.value
  return rfqs.value
})

function severityLabel(s: string) {
  return { critical: '紧急', high: '高', medium: '中', low: '低' }[s] || s
}
function severityTone(s: string) {
  return s === 'critical' || s === 'high' ? 'danger' : s === 'medium' ? 'warning' : 'success'
}
function categoryLabel(c: string) {
  return { sourcing: '采购', production: '生产', sales: '销售', collaboration: '协同' }[c] || c
}

function selectShortage(shortage: DashboardShortage) {
  router.push({ path: '/shortage-procurement', query: { part: shortage.part_number || shortage.part_name || '' } })
}

function openRfqForm(shortage?: DashboardShortage) {
  showRfqForm.value = true
  createError.value = null
  demo.clearLastResult()
  if (shortage) {
    rfqForm.value = {
      title: `询价: ${shortage.part_name || shortage.part_number}`,
      part_number: shortage.part_number || '',
      part_name: shortage.part_name || '',
      quantity: shortage.shortage_qty || 1,
      unit: shortage.unit || '个',
      target_price: undefined,
      lead_time_days: undefined,
      supplier_candidates: shortage.preferred_supplier_company_id ? [shortage.preferred_supplier_company_id] : [],
    }
  }
}

function openRfqFromAction(action: DashboardAction) {
  showRfqForm.value = true
  createError.value = null
  demo.clearLastResult()
  rfqForm.value = {
    title: action.title,
    part_number: action.part_number || '',
    part_name: action.part_number || '',
    quantity: 1,
    unit: '个',
    target_price: undefined,
    lead_time_days: undefined,
    supplier_candidates: action.suggested_supplier_company_id ? [action.suggested_supplier_company_id] : [],
  }
}

async function submitRfq() {
  creating.value = true
  createError.value = null
  try {
    if (isDemo.value) {
      // demo 模式: 调 /demo/actions/generate-rfq (基于当前缺件 + 直接关系候选动态生成)
      const res = await demo.generateRfq({
        part_number: rfqForm.value.part_number || undefined,
        quantity: rfqForm.value.quantity,
        target_price: rfqForm.value.target_price,
        lead_time_days: rfqForm.value.lead_time_days,
      })
      if (res?.no_direct_supplier) {
        createError.value = res.message || '无可用直接关系供应商, 需要先建立合作关系/人工审核'
      } else if (res?.rfq) {
        lastCreatedRfqId.value = (res as any).rfq.id
        showRfqForm.value = false
      } else if (demo.actionError.value) {
        createError.value = demo.actionError.value
      }
    } else {
      // 真实模式: 走业务 RFQ 接口
      const res = await createRfq({
        buyer_company_id: currentEnterpriseId.value,
        title: rfqForm.value.title,
        part_number: rfqForm.value.part_number || undefined,
        part_name: rfqForm.value.part_name || undefined,
        quantity: rfqForm.value.quantity,
        unit: rfqForm.value.unit,
        target_price: rfqForm.value.target_price,
        lead_time_days: rfqForm.value.lead_time_days,
        supplier_candidates: rfqForm.value.supplier_candidates.length ? rfqForm.value.supplier_candidates : undefined,
        shortage_id: selectedShortage.value ? String(selectedShortage.value.id) : undefined,
      })
      lastCreatedRfqId.value = res?.rfq?.id || null
      showRfqForm.value = false
    }
  } catch (e: any) {
    createError.value = e?.message || '创建 RFQ 失败'
  } finally {
    creating.value = false
  }
}

async function sendCreatedRfq(rfqId: number) {
  if (isDemo.value) return // demo RFQ 创建即已 sent, 无需再发送
  try {
    await sendRfq(rfqId)
    lastCreatedRfqId.value = null
  } catch {
    // 静默失败, 用户可重试
  }
}

async function viewComparison(rfqId: number) {
  compareRfqId.value = compareRfqId.value === rfqId ? null : rfqId
  if (compareRfqId.value) {
    if (isDemo.value) {
      await demo.loadComparison(rfqId)
    } else {
      await loadComparison(rfqId)
    }
  }
}

/** demo 模式: 对指定 RFQ 模拟报价 (基于候选供应商动态生成) */
async function demoSimulateQuotes(rfqId: number) {
  await demo.simulateQuotes(rfqId)
  if (compareRfqId.value === rfqId) {
    await demo.loadComparison(rfqId)
  }
}

/** demo 模式: 执行补货 (选定报价入库, 缺件下降, RFQ 关闭) */
async function demoExecuteReplenishment(rfq: { id: number }) {
  await demo.executeReplenishment({ rfq_id: rfq.id })
  await refreshDashboard()
}

async function recalculate() {
  if (isDemo.value) {
    await demo.recalculateShortages()
    await refreshDashboard()
  } else {
    try {
      await recalculateShortages(currentEnterpriseId.value)
      await refreshDashboard()
    } catch {
      // 静默失败
    }
  }
}

/** 统一报价对比数据 */
const comparisonData = computed(() => {
  if (isDemo.value) return demo.comparison.value
  return comparison.value as unknown as typeof demo.comparison.value
})

function goFlow() {
  router.push({ path: '/flow', query: selectedShortage.value ? { part: selectedShortage.value.part_number || '' } : undefined })
}
</script>

<template>
  <div class="page">
    <header class="page-head">
      <div>
        <span class="eyebrow">{{ current.company.name }}</span>
        <h1>缺件与采购</h1>
        <p>从订单和预测需求导致的缺件出发, 串起推荐动作、RFQ 创建与报价对比闭环。</p>
      </div>
      <div class="head-actions">
        <button class="action-link action-link--ghost" @click="recalculate">重算缺件</button>
        <button class="action-link" @click="goFlow">进入寻源流程</button>
      </div>
    </header>

    <div v-if="loading" class="loading-bar">正在拉取缺件与采购数据…</div>
    <div v-if="dataSource === 'mock' && !isDemo" class="notice-bar">后端接口暂不可用，当前显示本地兜底经营数据</div>
    <div v-if="isDemo" class="notice-bar notice-bar--demo">演示沙盘数据 · 缺件/RFQ/报价基于当前企业 BOM、库存、订单与直接上下游关系动态计算</div>

    <section class="layout">
      <!-- 缺件清单 -->
      <aside class="shortage-picker">
        <div class="picker-head">缺件清单 ({{ shortages.length }})</div>
        <button
          v-for="item in shortages"
          :key="item.id"
          class="shortage-item"
          :class="{ active: selectedShortage?.id === item.id }"
          @click="selectShortage(item)"
        >
          <div class="shortage-item__main">
            <div class="shortage-item__title">
              <b>{{ item.part_name || item.part_number }}</b>
              <span class="risk-dot" :class="`risk-dot--${severityTone(item.severity)}`" />
            </div>
            <span>{{ item.part_number }} · 缺口 {{ item.shortage_qty.toLocaleString() }} · {{ severityLabel(item.severity) }}</span>
          </div>
        </button>
        <div v-if="!shortages.length" class="empty-line">暂无缺件</div>
      </aside>

      <!-- 详情 + RFQ -->
      <main class="detail">
        <!-- 缺件详情 -->
        <section v-if="selectedShortage" class="summary-panel">
          <div>
            <span class="eyebrow">当前缺件</span>
            <h2>{{ selectedShortage.part_name || selectedShortage.part_number }}</h2>
            <p class="hint">
              {{ selectedShortage.category_name || '物料' }}
              · 缺口 {{ selectedShortage.shortage_qty.toLocaleString() }} {{ selectedShortage.unit || '' }}
              · 需求 {{ selectedShortage.required_qty.toLocaleString() }} · 可用 {{ selectedShortage.available_qty.toLocaleString() }}
            </p>
          </div>
          <div class="gap-number">
            <span>缺口</span>
            <b>{{ selectedShortage.shortage_qty.toLocaleString() }}</b>
            <button class="btn-rfq" @click="openRfqForm(selectedShortage)">从此缺件创建 RFQ</button>
          </div>
        </section>

        <!-- 缺件影响 -->
        <section v-if="selectedShortage" class="detail-grid">
          <div class="panel">
            <h3>影响订单和产品</h3>
            <div class="line-list">
              <div>
                <span>影响订单</span>
                <b>{{ selectedShortage.affected_order_numbers.join('、') || '无' }}</b>
              </div>
              <div>
                <span>影响产品</span>
                <b>{{ selectedShortage.product_name || '-' }}</b>
              </div>
              <div>
                <span>风险等级</span>
                <b class="risk-pill" :class="`risk-pill--${severityTone(selectedShortage.severity)}`">{{ severityLabel(selectedShortage.severity) }}</b>
              </div>
              <div>
                <span>首选供应商</span>
                <b>{{ selectedShortage.preferred_supplier_name || '未配置' }}</b>
              </div>
              <div v-if="selectedShortage.relationship_missing">
                <span>关系状态</span>
                <b class="danger">上游关系缺失</b>
              </div>
            </div>
          </div>

          <div class="panel">
            <h3>推荐动作</h3>
            <div class="action-mini-list">
              <div v-for="action in actions.filter(a => !selectedShortage?.part_number || a.part_number === selectedShortage?.part_number).slice(0, 4)" :key="action.title" class="action-mini">
                <span class="action-tag" :class="`action-tag--${action.category}`">{{ categoryLabel(action.category) }}</span>
                <div>
                  <b>{{ action.title }}</b>
                  <p>{{ action.detail }}</p>
                </div>
                <button v-if="action.category === 'sourcing'" class="btn-mini" @click="openRfqFromAction(action)">发 RFQ</button>
              </div>
              <div v-if="!actions.length" class="empty-line">暂无推荐动作</div>
            </div>
          </div>
        </section>

        <!-- RFQ 创建表单 -->
        <section v-if="showRfqForm" class="rfq-form-panel">
          <div class="rfq-form-head">
            <h3>创建 RFQ</h3>
            <button class="btn-close" @click="showRfqForm = false">✕</button>
          </div>
          <div class="rfq-form-grid">
            <label><span>标题</span><input v-model="rfqForm.title" class="input" placeholder="RFQ 标题" /></label>
            <label><span>零件号</span><input v-model="rfqForm.part_number" class="input" placeholder="part_number" /></label>
            <label><span>零件名</span><input v-model="rfqForm.part_name" class="input" placeholder="零件名称" /></label>
            <label><span>数量</span><input v-model.number="rfqForm.quantity" type="number" class="input" /></label>
            <label><span>单位</span><input v-model="rfqForm.unit" class="input" /></label>
            <label><span>目标单价</span><input v-model.number="rfqForm.target_price" type="number" class="input" placeholder="可选" /></label>
            <label><span>交期(天)</span><input v-model.number="rfqForm.lead_time_days" type="number" class="input" placeholder="可选" /></label>
            <label><span>候选供应商ID</span><input :value="rfqForm.supplier_candidates.join(',')" class="input" placeholder="逗号分隔, 如 9002,9006" @input="rfqForm.supplier_candidates = String(($event.target as HTMLInputElement).value).split(',').map(Number).filter(Boolean)" /></label>
          </div>
          <div v-if="createError" class="form-error">{{ createError }}</div>
          <div class="rfq-form-actions">
            <button class="btn-cancel" @click="showRfqForm = false">取消</button>
            <button class="btn-submit" :disabled="creating || !rfqForm.title" @click="submitRfq">{{ creating ? '创建中…' : '创建 RFQ' }}</button>
          </div>
        </section>

        <!-- 创建成功提示 -->
        <section v-if="lastCreatedRfqId" class="success-bar">
          <span>RFQ #{{ lastCreatedRfqId }} 创建成功!</span>
          <button v-if="!isDemo" class="btn-send" @click="sendCreatedRfq(lastCreatedRfqId!)">发送给供应商</button>
          <span v-else class="success-note">已发送至直接关系候选供应商</span>
        </section>

        <!-- RFQ 列表 -->
        <section class="rfq-list-panel">
          <div class="rfq-list-head">
            <h3>{{ isDemo ? '演示 RFQ 列表' : '本企业 RFQ 列表' }} ({{ rfqList.length }})</h3>
          </div>
          <div v-if="rfqList.length === 0" class="empty-line">暂无 RFQ, 可从缺件创建</div>
          <div v-else class="rfq-table">
            <div class="rfq-row rfq-row--head">
              <span>RFQ 编号</span>
              <span>标题</span>
              <span>零件</span>
              <span>数量</span>
              <span>状态</span>
              <span>操作</span>
            </div>
            <div v-for="rfq in rfqList.slice(0, 10)" :key="rfq.id" class="rfq-row">
              <span class="mono">{{ rfq.rfq_number }}</span>
              <span>{{ rfq.title }}</span>
              <span class="mono">{{ rfq.part_number || rfq.part_name || '-' }}</span>
              <span>{{ rfq.quantity }}</span>
              <span class="status-pill" :class="`status--${rfq.status}`">{{ rfq.status }}</span>
              <div class="rfq-actions">
                <button v-if="!isDemo && rfq.status === 'draft'" class="btn-mini" @click="sendRfq(rfq.id)">发送</button>
                <button v-if="isDemo && rfq.status === 'sent'" class="btn-mini btn-mini--accent" :disabled="!!demo.running.value" @click="demoSimulateQuotes(rfq.id)">模拟报价</button>
                <button v-if="isDemo && (rfq.status === 'sent' || rfq.status === 'quoted')" class="btn-mini btn-mini--success" :disabled="!!demo.running.value" @click="demoExecuteReplenishment(rfq)">执行补货</button>
                <button class="btn-mini" @click="viewComparison(rfq.id)">{{ compareRfqId === rfq.id ? '收起' : '报价对比' }}</button>
              </div>
            </div>
          </div>

          <!-- 报价对比 -->
          <div v-if="compareRfqId && comparisonData" class="comparison-panel">
            <h4>{{ comparisonData.rfq_number }} 报价对比</h4>
            <div v-if="comparisonData.items.length === 0" class="empty-line">暂无报价</div>
            <div v-else class="quote-table">
              <div class="quote-row quote-row--head">
                <span>排名</span>
                <span>供应商</span>
                <span>单价</span>
                <span>MOQ</span>
                <span>交期(天)</span>
                <span>库存</span>
                <span>达标</span>
              </div>
              <div v-for="q in comparisonData.items" :key="q.id" class="quote-row" :class="{ 'quote-row--best': q.is_lowest }">
                <span>{{ q.rank || '-' }}</span>
                <span>{{ q.supplier_name }}</span>
                <span class="strong">¥{{ q.unit_price }}</span>
                <span>{{ q.moq || '-' }}</span>
                <span>{{ q.lead_time_days || '-' }}</span>
                <span>{{ q.is_in_stock ? '有货' : '无货' }}</span>
                <span :class="q.meets_target === false ? 'danger' : 'success'">{{ q.meets_target === null || q.meets_target === undefined ? '-' : q.meets_target ? '达标' : '超目标' }}</span>
              </div>
            </div>
          </div>
        </section>
      </main>
    </section>
  </div>
</template>

<style scoped>
.page {
  max-width: 1320px;
  margin: 0 auto;
  padding: var(--space-5);
}
.page-head,
.shortage-picker,
.summary-panel,
.panel,
.rfq-form-panel,
.rfq-list-panel {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-1);
}
.page-head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  align-items: flex-start;
  padding: var(--space-4);
  margin-bottom: var(--space-4);
}
.eyebrow { color: var(--text-tertiary); font-size: var(--font-size-xs); font-weight: 700; }
h1 { margin-top: 4px; color: var(--text-primary); font-size: var(--font-size-2xl); }
.page-head p,
.hint { margin-top: 6px; color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.6; }
.head-actions { display: flex; gap: var(--space-2); flex-shrink: 0; }
.action-link,
.btn-rfq,
.btn-submit,
.btn-send {
  border-radius: 6px;
  padding: 8px 12px;
  font-size: var(--font-size-sm);
  white-space: nowrap;
  color: #fff;
  background: var(--gradient-accent);
  border: none;
  cursor: pointer;
}
.action-link--ghost { background: var(--bg-2); color: var(--text-secondary); border: 1px solid var(--border-default); }
.action-link--ghost:hover { border-color: var(--accent-border); }
.loading-bar,
.notice-bar {
  padding: var(--space-3) var(--space-4);
  margin-bottom: var(--space-4);
  border-radius: 6px;
  font-size: var(--font-size-sm);
}
.loading-bar { border: 1px solid var(--border-subtle); background: var(--bg-2); color: var(--text-tertiary); }
.notice-bar { border: 1px solid rgba(234, 179, 8, 0.25); background: var(--warning-soft); color: var(--warning); }
.notice-bar--demo { border: 1px solid rgba(99, 102, 241, 0.3); background: var(--accent-soft); color: var(--accent); }
.success-note { color: var(--success); font-size: var(--font-size-sm); }
.layout {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: var(--space-4);
  align-items: start;
}
.shortage-picker { overflow: hidden; }
.picker-head {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-subtle);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  font-weight: 700;
}
.shortage-item {
  display: block;
  width: 100%;
  text-align: left;
  padding: var(--space-3) var(--space-4);
  border: none;
  border-bottom: 1px solid var(--border-subtle);
  background: none;
  cursor: pointer;
}
.shortage-item:hover,
.shortage-item.active { background: var(--bg-2); }
.shortage-item__main { display: grid; gap: 5px; }
.shortage-item__title { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
.shortage-item b { color: var(--text-primary); font-size: var(--font-size-sm); }
.shortage-item span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.risk-dot { width: 8px; height: 8px; flex: 0 0 auto; border-radius: 999px; }
.risk-dot--danger { background: var(--danger); box-shadow: 0 0 0 4px var(--danger-soft); }
.risk-dot--warning { background: var(--warning); box-shadow: 0 0 0 4px var(--warning-soft); }
.risk-dot--success { background: var(--success); box-shadow: 0 0 0 4px var(--success-soft); }
.detail { display: grid; gap: var(--space-4); min-width: 0; }
.summary-panel {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-4);
  align-items: flex-start;
}
.summary-panel h2 { color: var(--text-primary); font-size: var(--font-size-xl); margin-top: 4px; }
.gap-number { text-align: right; display: grid; gap: var(--space-2); justify-items: end; }
.gap-number span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.gap-number b { color: var(--danger); font-size: var(--font-size-2xl); }
.detail-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-4); }
.panel { padding: var(--space-4); }
.panel h3 { color: var(--text-primary); font-size: var(--font-size-md); margin-bottom: var(--space-3); }
.line-list { display: grid; gap: var(--space-3); }
.line-list div { display: flex; justify-content: space-between; gap: var(--space-3); border-bottom: 1px solid var(--border-subtle); padding-bottom: var(--space-2); }
.line-list span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.line-list b { color: var(--text-primary); font-size: var(--font-size-sm); text-align: right; }
.danger { color: var(--danger); }
.action-mini-list { display: grid; gap: var(--space-2); }
.action-mini { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: var(--space-2); align-items: flex-start; padding: var(--space-2); border: 1px solid var(--border-subtle); border-radius: 6px; background: var(--bg-2); }
.action-mini b { color: var(--text-primary); font-size: var(--font-size-sm); display: block; }
.action-mini p { color: var(--text-tertiary); font-size: var(--font-size-xs); margin-top: 2px; }
.action-tag { padding: 2px 6px; border-radius: 4px; font-size: var(--font-size-xs); font-weight: 600; }
.action-tag--sourcing { color: var(--accent); background: var(--accent-soft); }
.action-tag--production { color: var(--warning); background: var(--warning-soft); }
.action-tag--sales { color: var(--success); background: var(--success-soft); }
.action-tag--collaboration { color: #a78bfa; background: rgba(167, 139, 250, 0.12); }
.btn-mini { padding: 4px 8px; border-radius: 4px; font-size: var(--font-size-xs); color: var(--accent-hover); background: var(--accent-soft); border: 1px solid var(--accent-border); cursor: pointer; white-space: nowrap; }
.btn-mini:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-mini--accent { color: #fff; background: var(--gradient-accent); border: none; }
.btn-mini--success { color: var(--success); background: var(--success-soft); border-color: rgba(34, 197, 94, 0.35); }
.empty-line { padding: var(--space-4); color: var(--text-tertiary); font-size: var(--font-size-sm); text-align: center; }
.rfq-form-panel { padding: var(--space-4); }
.rfq-form-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-3); }
.rfq-form-head h3 { color: var(--text-primary); font-size: var(--font-size-md); }
.btn-close { color: var(--text-tertiary); font-size: var(--font-size-md); cursor: pointer; background: none; border: none; }
.rfq-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-3); }
.rfq-form-grid label { display: grid; gap: 4px; }
.rfq-form-grid span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.input { padding: 8px 10px; border: 1px solid var(--border-default); border-radius: 6px; background: var(--bg-2); color: var(--text-primary); font-size: var(--font-size-sm); }
.form-error { margin-top: var(--space-3); padding: var(--space-2) var(--space-3); border-radius: 4px; background: var(--danger-soft); color: var(--danger); font-size: var(--font-size-xs); }
.rfq-form-actions { display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-3); }
.btn-cancel { padding: 8px 12px; border-radius: 6px; border: 1px solid var(--border-default); background: var(--bg-2); color: var(--text-secondary); font-size: var(--font-size-sm); cursor: pointer; }
.btn-submit:disabled { opacity: 0.5; cursor: not-allowed; }
.success-bar { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); padding: var(--space-3) var(--space-4); border: 1px solid rgba(34, 197, 94, 0.35); border-radius: 8px; background: var(--success-soft); color: var(--success); font-size: var(--font-size-sm); }
.rfq-list-panel { padding: var(--space-4); }
.rfq-list-head { margin-bottom: var(--space-3); }
.rfq-list-head h3 { color: var(--text-primary); font-size: var(--font-size-md); }
.rfq-table { overflow-x: auto; }
.rfq-row { display: grid; grid-template-columns: 110px minmax(160px, 1fr) 120px 60px 70px 130px; gap: var(--space-3); align-items: center; min-width: 680px; padding: 10px 0; border-bottom: 1px solid var(--border-subtle); font-size: var(--font-size-sm); color: var(--text-secondary); }
.rfq-row--head { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.mono { font-family: var(--font-mono); font-size: var(--font-size-xs); }
.status-pill { padding: 2px 8px; border-radius: 999px; font-size: var(--font-size-xs); font-weight: 600; display: inline-block; text-align: center; }
.status--draft { color: var(--text-tertiary); background: var(--bg-3); }
.status--sent { color: var(--accent); background: var(--accent-soft); }
.status--quoted { color: var(--warning); background: var(--warning-soft); }
.status--closed { color: var(--success); background: var(--success-soft); }
.rfq-actions { display: flex; gap: var(--space-1); }
.comparison-panel { margin-top: var(--space-3); padding: var(--space-3); border: 1px solid var(--accent-border); border-radius: 6px; background: var(--bg-2); }
.comparison-panel h4 { color: var(--text-primary); font-size: var(--font-size-sm); margin-bottom: var(--space-2); }
.quote-table { overflow-x: auto; }
.quote-row { display: grid; grid-template-columns: 50px minmax(120px, 1fr) 80px 60px 70px 60px 60px; gap: var(--space-3); align-items: center; min-width: 520px; padding: 8px 0; border-bottom: 1px solid var(--border-subtle); font-size: var(--font-size-sm); color: var(--text-secondary); }
.quote-row--head { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.quote-row--best { background: var(--success-soft); border-radius: 4px; padding-left: var(--space-2); padding-right: var(--space-2); }
.strong { color: var(--text-primary); font-weight: 600; }
.success { color: var(--success); }
.risk-pill { display: inline-flex; justify-content: center; min-width: 34px; padding: 2px 7px; border-radius: 999px; font-size: var(--font-size-xs); border: 1px solid var(--border-subtle); }
.risk-pill--danger { color: var(--danger); background: var(--danger-soft); border-color: rgba(239, 68, 68, 0.35); }
.risk-pill--warning { color: var(--warning); background: var(--warning-soft); border-color: rgba(234, 179, 8, 0.35); }
.risk-pill--success { color: var(--success); background: var(--success-soft); border-color: rgba(34, 197, 94, 0.35); }
@media (max-width: 980px) {
  .layout,
  .detail-grid,
  .rfq-form-grid { grid-template-columns: 1fr; }
}
@media (max-width: 700px) {
  .page { padding: var(--space-3); }
  .page-head,
  .summary-panel { flex-direction: column; }
}
</style>
