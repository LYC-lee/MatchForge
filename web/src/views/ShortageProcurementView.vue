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
  return { urgent: '紧急', critical: '紧急', high: '高', medium: '中', low: '低' }[s] || s
}
function severityTone(s: string) {
  return s === 'urgent' || s === 'critical' || s === 'high' ? 'danger' : s === 'medium' ? 'warning' : 'success'
}
function categoryLabel(c: string) {
  return { sourcing: '采购', production: '生产', sales: '销售', collaboration: '协同' }[c] || c
}

/** 候选供应商：来自当前企业直接关系（上下游/支撑），替代手填数字 ID */
const supplierOptions = computed(() => {
  const d = dashboard.value
  if (!d) return [] as Array<{ id: number; name: string; dir: string }>
  const rels: Array<{ id: number; name: string; dir: string }> = []
  for (const u of d.upstream_summary?.items || []) rels.push({ id: u.company_id, name: u.company_name, dir: '上游' })
  for (const x of d.downstream_summary?.items || []) rels.push({ id: x.company_id, name: x.company_name, dir: '下游' })
  for (const s of d.support_summary?.items || []) rels.push({ id: s.company_id, name: s.company_name, dir: '支撑' })
  return rels
})
function toggleCandidate(id: number) {
  const arr = rfqForm.value.supplier_candidates
  const i = arr.indexOf(id)
  if (i >= 0) arr.splice(i, 1)
  else arr.push(id)
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
  router.push({ path: '/chat', query: selectedShortage.value ? { part: selectedShortage.value.part_number || '' } : undefined })
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
            <div class="form-field">
              <span>候选供应商</span>
              <div class="candidate-list">
                <label v-for="sup in supplierOptions" :key="sup.id" class="candidate-item" :class="{ 'candidate-item--on': rfqForm.supplier_candidates.includes(sup.id) }">
                  <input type="checkbox" :checked="rfqForm.supplier_candidates.includes(sup.id)" @change="toggleCandidate(sup.id)">
                  <span>{{ sup.name }}</span>
                  <small>{{ sup.dir }}</small>
                </label>
                <span v-if="!supplierOptions.length" class="input-hint">暂无直接关系供应商</span>
              </div>
            </div>
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
  max-width: var(--container-lg);
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
  border-radius: var(--radius-lg);
  background: var(--bg-surface);
}
.page-head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  align-items: flex-start;
  padding: var(--space-4);
  margin-bottom: var(--space-4);
}
.eyebrow { color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: var(--leading-xs); font-weight: 700; }
h1 { margin-top: var(--space-1); color: var(--text-primary); font-size: var(--font-size-2xl); line-height: var(--leading-2xl); }
.page-head p,
.hint { margin-top: var(--space-1); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: var(--leading-sm); }
.head-actions { display: flex; gap: var(--space-2); flex-shrink: 0; }
.action-link,
.btn-rfq,
.btn-submit,
.btn-send {
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-3);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  white-space: nowrap;
  color: var(--on-accent);
  background: var(--accent);
  border: none;
  cursor: pointer;
  transition: background-color var(--transition-fast);
}
.action-link:hover, .btn-rfq:hover, .btn-submit:hover:not(:disabled), .btn-send:hover { background: var(--accent-hover); }
.action-link--ghost { background: var(--bg-subtle); color: var(--text-secondary); border: 1px solid var(--border-default); }
.action-link--ghost:hover { border-color: var(--accent-border); background: var(--bg-subtle); }
.loading-bar,
.notice-bar {
  padding: var(--space-3) var(--space-4);
  margin-bottom: var(--space-4);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
}
.loading-bar { border: 1px solid var(--border-subtle); background: var(--bg-subtle); color: var(--text-tertiary); }
.notice-bar { border: 1px solid var(--warning-border); background: var(--warning-soft); color: var(--warning); }
.notice-bar--demo { border: 1px solid var(--accent-border); background: var(--accent-soft); color: var(--accent-text); }
.success-note { color: var(--success); font-size: var(--font-size-sm); line-height: var(--leading-sm); }
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
  line-height: var(--leading-xs);
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
  transition: background-color var(--transition-fast);
}
.shortage-item:hover,
.shortage-item.active { background: var(--bg-subtle); }
.shortage-item__main { display: grid; gap: var(--space-1); }
.shortage-item__title { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
.shortage-item b { color: var(--text-primary); font-size: var(--font-size-sm); line-height: var(--leading-sm); }
.shortage-item span { color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: var(--leading-xs); }
.risk-dot { width: var(--space-2); height: var(--space-2); flex: 0 0 auto; border-radius: var(--radius-full); }
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
.summary-panel h2 { color: var(--text-primary); font-size: var(--font-size-xl); line-height: var(--leading-xl); margin-top: var(--space-1); }
.gap-number { text-align: right; display: grid; gap: var(--space-2); justify-items: end; }
.gap-number span { color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: var(--leading-xs); }
.gap-number b { color: var(--danger); font-size: var(--font-size-2xl); line-height: var(--leading-2xl); font-family: var(--font-mono); }
.detail-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-4); }
.panel { padding: var(--space-4); }
.panel h3 { color: var(--text-primary); font-size: var(--font-size-md); line-height: var(--leading-md); margin-bottom: var(--space-3); }
.line-list { display: grid; gap: var(--space-3); }
.line-list div { display: flex; justify-content: space-between; gap: var(--space-3); border-bottom: 1px solid var(--border-subtle); padding-bottom: var(--space-2); }
.line-list span { color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: var(--leading-xs); }
.line-list b { color: var(--text-primary); font-size: var(--font-size-sm); line-height: var(--leading-sm); text-align: right; }
.danger { color: var(--danger); }
.action-mini-list { display: grid; gap: var(--space-2); }
.action-mini { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: var(--space-2); align-items: flex-start; padding: var(--space-2); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); background: var(--bg-subtle); }
.action-mini b { color: var(--text-primary); font-size: var(--font-size-sm); line-height: var(--leading-sm); display: block; }
.action-mini p { color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: var(--leading-xs); margin-top: var(--space-1); }
.action-tag { padding: var(--space-1) var(--space-2); border-radius: var(--radius-sm); font-size: var(--font-size-xs); line-height: var(--leading-xs); font-weight: 600; }
.action-tag--sourcing { color: var(--accent-text); background: var(--accent-soft); }
.action-tag--production { color: var(--warning); background: var(--warning-soft); }
.action-tag--sales { color: var(--success); background: var(--success-soft); }
.action-tag--collaboration { color: var(--notice); background: var(--notice-soft); }
.btn-mini { padding: var(--space-1) var(--space-2); border-radius: var(--radius-sm); font-size: var(--font-size-xs); line-height: var(--leading-xs); color: var(--accent-text); background: var(--accent-soft); border: 1px solid var(--accent-border); cursor: pointer; white-space: nowrap; }
.btn-mini:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-mini--accent { color: var(--on-accent); background: var(--accent); border-color: var(--accent); }
.btn-mini--success { color: var(--success); background: var(--success-soft); border-color: var(--success-border); }
.empty-line { padding: var(--space-4); color: var(--text-tertiary); font-size: var(--font-size-sm); line-height: var(--leading-sm); text-align: center; }
.rfq-form-panel { padding: var(--space-4); }
.rfq-form-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-3); }
.rfq-form-head h3 { color: var(--text-primary); font-size: var(--font-size-md); line-height: var(--leading-md); }
.btn-close { color: var(--text-tertiary); font-size: var(--font-size-md); line-height: var(--leading-md); cursor: pointer; background: none; border: none; }
.rfq-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-3); }
.rfq-form-grid label,
.form-field { display: grid; gap: var(--space-1); }
.rfq-form-grid span,
.form-field > span { color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: var(--leading-xs); }
.input { padding: var(--space-2) var(--space-3); border: 1px solid var(--border-default); border-radius: var(--radius-md); background: var(--bg-surface); color: var(--text-primary); font-size: var(--font-size-sm); line-height: var(--leading-sm); outline: none; transition: border-color var(--transition-fast), box-shadow var(--transition-fast); }
.input:focus { border-color: var(--accent-border); box-shadow: 0 0 0 3px var(--accent-soft); }
.input-hint { color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: var(--leading-xs); }
.candidate-list { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.candidate-item {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-full);
  background: var(--bg-surface);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  color: var(--text-secondary);
  cursor: pointer;
  transition: border-color var(--transition-fast), background-color var(--transition-fast);
}
.candidate-item input { accent-color: var(--accent); }
.candidate-item small { color: var(--text-tertiary); }
.candidate-item--on { border-color: var(--accent-border); background: var(--accent-soft); color: var(--accent-text); }
.form-error { margin-top: var(--space-3); padding: var(--space-2) var(--space-3); border-radius: var(--radius-sm); background: var(--danger-soft); border: 1px solid var(--danger-border); color: var(--danger); font-size: var(--font-size-xs); line-height: var(--leading-xs); }
.rfq-form-actions { display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-3); }
.btn-cancel { padding: var(--space-2) var(--space-3); border-radius: var(--radius-md); border: 1px solid var(--border-default); background: var(--bg-subtle); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: var(--leading-sm); cursor: pointer; }
.btn-submit:disabled { opacity: 0.5; cursor: not-allowed; }
.success-bar { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); padding: var(--space-3) var(--space-4); border: 1px solid var(--success-border); border-radius: var(--radius-lg); background: var(--success-soft); color: var(--success); font-size: var(--font-size-sm); line-height: var(--leading-sm); }
.rfq-list-panel { padding: var(--space-4); }
.rfq-list-head { margin-bottom: var(--space-3); }
.rfq-list-head h3 { color: var(--text-primary); font-size: var(--font-size-md); line-height: var(--leading-md); }
.rfq-table { overflow-x: auto; }
.rfq-row { display: grid; grid-template-columns: 110px minmax(160px, 1fr) 120px 60px 70px 130px; gap: var(--space-3); align-items: center; min-width: 680px; padding: var(--space-2) 0; border-bottom: 1px solid var(--border-subtle); font-size: var(--font-size-sm); line-height: var(--leading-sm); color: var(--text-secondary); }
.rfq-row--head { color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: var(--leading-xs); }
.mono { font-family: var(--font-mono); font-size: var(--font-size-xs); }
.status-pill { padding: var(--space-1) var(--space-2); border-radius: var(--radius-full); font-size: var(--font-size-xs); line-height: var(--leading-xs); font-weight: 600; display: inline-block; text-align: center; }
.status--draft { color: var(--text-tertiary); background: var(--bg-subtle); }
.status--sent { color: var(--accent-text); background: var(--accent-soft); }
.status--quoted { color: var(--warning); background: var(--warning-soft); }
.status--closed { color: var(--success); background: var(--success-soft); }
.rfq-actions { display: flex; gap: var(--space-1); }
.comparison-panel { margin-top: var(--space-3); padding: var(--space-3); border: 1px solid var(--accent-border); border-radius: var(--radius-md); background: var(--bg-subtle); }
.comparison-panel h4 { color: var(--text-primary); font-size: var(--font-size-sm); line-height: var(--leading-sm); margin-bottom: var(--space-2); }
.quote-table { overflow-x: auto; }
.quote-row { display: grid; grid-template-columns: 50px minmax(120px, 1fr) 80px 60px 70px 60px 60px; gap: var(--space-3); align-items: center; min-width: 520px; padding: var(--space-2) 0; border-bottom: 1px solid var(--border-subtle); font-size: var(--font-size-sm); line-height: var(--leading-sm); color: var(--text-secondary); }
.quote-row--head { color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: var(--leading-xs); }
.quote-row--best { background: var(--success-soft); border-radius: var(--radius-sm); padding-left: var(--space-2); padding-right: var(--space-2); }
.strong { color: var(--text-primary); font-weight: 600; }
.success { color: var(--success); }
.risk-pill { display: inline-flex; justify-content: center; min-width: 34px; padding: var(--space-1) var(--space-2); border-radius: var(--radius-full); font-size: var(--font-size-xs); line-height: var(--leading-xs); border: 1px solid var(--border-subtle); }
.risk-pill--danger { color: var(--danger); background: var(--danger-soft); border-color: var(--danger-border); }
.risk-pill--warning { color: var(--warning); background: var(--warning-soft); border-color: var(--warning-border); }
.risk-pill--success { color: var(--success); background: var(--success-soft); border-color: var(--success-border); }
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
