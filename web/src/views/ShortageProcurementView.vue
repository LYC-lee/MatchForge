<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useEnterpriseContext } from '@/composables/useEnterpriseContext'
import type { RiskLevel } from '@/types/enterprise'

const route = useRoute()
const router = useRouter()
const { current } = useEnterpriseContext()

const selectedPart = computed(() => String(route.query.part || current.value.shortages[0]?.code || ''))
const selectedShortage = computed(() =>
  current.value.shortages.find((item) => item.code === selectedPart.value) || current.value.shortages[0],
)

function riskTone(risk: RiskLevel) {
  return risk === '高' ? 'danger' : risk === '中' ? 'warning' : 'success'
}

function goFlow() {
  const item = selectedShortage.value
  router.push({ path: '/flow', query: item ? { part: item.code } : undefined })
}
</script>

<template>
  <div class="page">
    <header class="page-head">
      <div>
        <span class="eyebrow">{{ current.company.name }}</span>
        <h1>缺件与采购</h1>
        <p>从订单和预测需求导致的缺件出发，串起替代料、供应商匹配和 RFQ。</p>
      </div>
      <button class="action-link" @click="goFlow">进入采购寻源流程</button>
    </header>

    <section class="layout">
      <aside class="shortage-picker">
        <div class="picker-head">缺件清单</div>
        <RouterLink
          v-for="item in current.shortages"
          :key="item.code"
          :to="{ path: '/shortage-procurement', query: { part: item.code } }"
          class="shortage-item"
          :class="{ active: selectedShortage?.code === item.code }"
        >
          <div class="shortage-item__main">
            <div class="shortage-item__title">
              <b>{{ item.part }}</b>
              <span class="risk-dot" :class="`risk-dot--${riskTone(item.risk)}`" />
            </div>
            <span>{{ item.code }} · 缺口 {{ item.gap.toLocaleString() }} · {{ item.risk }}风险</span>
          </div>
        </RouterLink>
      </aside>

      <main v-if="selectedShortage" class="detail">
        <section class="summary-panel">
          <div>
            <span class="eyebrow">当前缺件</span>
            <h2>{{ selectedShortage.part }}</h2>
            <p>{{ selectedShortage.action }}</p>
          </div>
          <div class="gap-number">
            <span>缺口</span>
            <b>{{ selectedShortage.gap.toLocaleString() }}</b>
          </div>
        </section>

        <section class="detail-grid">
          <div class="panel">
            <h3>影响订单和产品</h3>
            <div class="line-list">
              <div>
                <span>订单</span>
                <b>{{ selectedShortage.affectedOrders.join('、') }}</b>
              </div>
              <div>
                <span>产品</span>
                <b>{{ selectedShortage.affectedProducts.join('、') }}</b>
              </div>
              <div>
                <span>风险等级</span>
                <b class="risk-pill" :class="`risk-pill--${riskTone(selectedShortage.risk)}`">{{ selectedShortage.risk }}</b>
              </div>
            </div>
          </div>

          <div class="panel">
            <h3>推荐替代料</h3>
            <div class="chips">
              <RouterLink
                v-for="item in selectedShortage.substitutes"
                :key="item"
                :to="{ path: '/alternatives', query: { part: selectedShortage.code } }"
                class="chip"
              >
                {{ item }}
              </RouterLink>
            </div>
            <p class="hint">替代前需由工程确认规格、认证和客户接受度。</p>
          </div>

          <div class="panel">
            <h3>推荐供应商</h3>
            <div class="supplier-list">
              <div v-for="supplier in selectedShortage.suppliers" :key="supplier" class="supplier-row">
                <b>{{ supplier }}</b>
                <span>能力匹配 · 建议询价</span>
              </div>
            </div>
          </div>

          <div class="panel">
            <h3>生成 RFQ</h3>
            <p class="hint">把缺口、目标交期、替代料和候选供应商带入现有 RFQ 流程。</p>
            <div class="rfq-actions">
              <RouterLink :to="{ path: '/alternatives', query: { part: selectedShortage.code } }" class="secondary">查看替代料结果</RouterLink>
              <RouterLink to="/supplier-match" class="secondary">供应商匹配</RouterLink>
              <RouterLink to="/rfq-edit" class="primary">生成 RFQ</RouterLink>
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
.panel {
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
.action-link,
.primary,
.secondary {
  border-radius: 6px;
  padding: 8px 12px;
  font-size: var(--font-size-sm);
  white-space: nowrap;
}
.action-link,
.primary { color: #fff; background: var(--gradient-accent); }
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
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-subtle);
}
.shortage-item:hover,
.shortage-item.active { background: var(--bg-2); }
.shortage-item__main { display: grid; gap: 5px; }
.shortage-item__title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}
.shortage-item b { color: var(--text-primary); font-size: var(--font-size-sm); }
.shortage-item span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.risk-dot {
  width: 8px;
  height: 8px;
  flex: 0 0 auto;
  border-radius: 999px;
}
.risk-dot--danger { background: var(--danger); box-shadow: 0 0 0 4px var(--danger-soft); }
.risk-dot--warning { background: var(--warning); box-shadow: 0 0 0 4px var(--warning-soft); }
.risk-dot--success { background: var(--success); box-shadow: 0 0 0 4px var(--success-soft); }
.detail { display: grid; gap: var(--space-4); min-width: 0; }
.summary-panel {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-4);
}
.summary-panel h2 { color: var(--text-primary); font-size: var(--font-size-xl); margin-top: 4px; }
.gap-number { text-align: right; }
.gap-number span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.gap-number b { display: block; color: var(--danger); font-size: var(--font-size-2xl); }
.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
}
.panel { padding: var(--space-4); }
.panel h3 { color: var(--text-primary); font-size: var(--font-size-md); margin-bottom: var(--space-3); }
.line-list { display: grid; gap: var(--space-3); }
.line-list div {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
  padding-bottom: var(--space-2);
}
.line-list span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.line-list b { color: var(--text-primary); font-size: var(--font-size-sm); text-align: right; }
.chips,
.rfq-actions { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.chip,
.secondary {
  border: 1px solid var(--border-subtle);
  background: var(--bg-2);
  color: var(--text-secondary);
}
.chip {
  border-radius: 999px;
  padding: 5px 9px;
  font-size: var(--font-size-xs);
}
.supplier-list { display: grid; gap: var(--space-2); }
.supplier-row {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  background: var(--bg-2);
}
.supplier-row b { color: var(--text-primary); font-size: var(--font-size-sm); }
.supplier-row span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.risk-pill {
  display: inline-flex;
  justify-content: center;
  min-width: 34px;
  padding: 2px 7px;
  border-radius: 999px;
  font-size: var(--font-size-xs);
  border: 1px solid var(--border-subtle);
}
.risk-pill--danger { color: var(--danger); background: var(--danger-soft); border-color: rgba(239, 68, 68, 0.35); }
.risk-pill--warning { color: var(--warning); background: var(--warning-soft); border-color: rgba(234, 179, 8, 0.35); }
.risk-pill--success { color: var(--success); background: var(--success-soft); border-color: rgba(34, 197, 94, 0.35); }
@media (max-width: 980px) {
  .layout,
  .detail-grid { grid-template-columns: 1fr; }
}
@media (max-width: 700px) {
  .page { padding: var(--space-3); }
  .page-head,
  .summary-panel { flex-direction: column; }
}
</style>
