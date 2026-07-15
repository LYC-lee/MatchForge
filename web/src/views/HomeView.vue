<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useEnterpriseContext } from '@/composables/useEnterpriseContext'
import { riskRank, type RiskLevel } from '@/mock/enterpriseContext'

const router = useRouter()
const { companies, current, currentEnterpriseId, setCurrentEnterprise } = useEnterpriseContext()

const topShortages = computed(() =>
  [...current.value.shortages].sort((a, b) => riskRank(b.risk) - riskRank(a.risk)).slice(0, 4),
)
const atRiskProducts = computed(() => current.value.products.filter((item) => item.risk !== '低'))

function riskClass(risk: RiskLevel) {
  return `risk risk--${risk}`
}

function goProcure(shortageCode?: string) {
  router.push({ path: '/shortage-procurement', query: shortageCode ? { part: shortageCode } : undefined })
}
</script>

<template>
  <div class="dashboard">
    <section class="context-bar">
      <div class="context-main">
        <span class="eyebrow">当前企业经营驾驶舱</span>
        <div class="context-title">
          <select
            :value="currentEnterpriseId"
            class="enterprise-select"
            aria-label="切换当前企业"
            @change="setCurrentEnterprise(Number(($event.target as HTMLSelectElement).value))"
          >
            <option v-for="company in companies" :key="company.id" :value="company.id">
              {{ company.name }} / {{ company.segment }}
            </option>
          </select>
          <span class="role">{{ current.company.role }}</span>
        </div>
        <p>{{ current.company.note }}</p>
      </div>
      <div class="context-meta">
        <span>{{ current.company.location }}</span>
        <span>{{ current.company.segment }}</span>
      </div>
    </section>

    <section class="metrics-grid" aria-label="经营概览">
      <div class="metric">
        <span>待交付订单</span>
        <b>{{ current.metrics.pendingOrders }}</b>
        <small>{{ current.metrics.urgentOrders }} 个紧急订单</small>
      </div>
      <div class="metric">
        <span>预测需求</span>
        <b>{{ current.metrics.forecastDemand.toLocaleString() }}</b>
        <small>未来 30 天滚动</small>
      </div>
      <div class="metric">
        <span>可生产产品</span>
        <b>{{ current.metrics.availableProducts }}</b>
        <small>{{ current.metrics.atRiskProducts }} 个受缺件影响</small>
      </div>
      <div class="metric metric--risk">
        <span>缺件风险</span>
        <b>{{ current.metrics.shortageParts }}</b>
        <small>需采购/替代/协同处理</small>
      </div>
    </section>

    <section class="first-screen">
      <div class="panel panel--orders">
        <div class="panel-head">
          <div>
            <span class="eyebrow">订单与预测需求</span>
            <h2>今天需要老板关注的交付</h2>
          </div>
        </div>
        <div class="dense-table">
          <div class="table-row table-row--head">
            <span>类型</span>
            <span>客户/对象</span>
            <span>产品</span>
            <span>数量</span>
            <span>交期</span>
            <span>风险</span>
          </div>
          <div v-for="item in current.demands" :key="item.id" class="table-row">
            <span class="pill">{{ item.type }}</span>
            <span>{{ item.customer }}</span>
            <span>{{ item.product }}</span>
            <span>{{ item.quantity.toLocaleString() }}</span>
            <span>{{ item.due }}</span>
            <span :class="riskClass(item.risk)">{{ item.risk }}</span>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-head">
          <div>
            <span class="eyebrow">可生产产品</span>
            <h2>产品齐套与产能</h2>
          </div>
          <RouterLink to="/products-bom" class="text-link">查看 BOM</RouterLink>
        </div>
        <div class="product-list">
          <div v-for="product in current.products" :key="product.id" class="product-line">
            <div>
              <b>{{ product.model }}</b>
              <span>{{ product.name }} · {{ product.capacity }}</span>
            </div>
            <div class="product-line__right">
              <small>{{ product.status }}</small>
              <span :class="riskClass(product.risk)">{{ product.risk }}</span>
            </div>
          </div>
        </div>
        <div v-if="atRiskProducts.length" class="inline-note">
          {{ atRiskProducts.map((item) => item.model).join('、') }} 需要结合缺件清单重新排产。
        </div>
      </div>

      <div class="panel">
        <div class="panel-head">
          <div>
            <span class="eyebrow">缺件与风险</span>
            <h2>影响订单的关键缺口</h2>
          </div>
          <button class="text-link" @click="goProcure()">进入采购</button>
        </div>
        <div class="shortage-list">
          <button v-for="item in topShortages" :key="item.code" class="shortage-line" @click="goProcure(item.code)">
            <div>
              <b>{{ item.part }}</b>
              <span>缺口 {{ item.gap.toLocaleString() }} · 影响 {{ item.affectedProducts.join('、') }}</span>
            </div>
            <span :class="riskClass(item.risk)">{{ item.risk }}</span>
          </button>
        </div>
      </div>

      <div class="panel">
        <div class="panel-head">
          <div>
            <span class="eyebrow">推荐动作</span>
            <h2>采购、生产、销售下一步</h2>
          </div>
        </div>
        <div class="action-list">
          <div v-for="action in current.actions" :key="action.id" class="action-line">
            <span class="action-type">{{ action.category }}</span>
            <div>
              <b>{{ action.title }}</b>
              <p>{{ action.detail }}</p>
              <small v-if="action.target">建议联系：{{ action.target }}</small>
            </div>
            <span :class="riskClass(action.priority)">{{ action.priority }}</span>
          </div>
        </div>
      </div>
    </section>

    <section class="network-strip">
      <div>
        <span class="eyebrow">直接上下游</span>
        <h2>协同问答只面向当前企业相关对象</h2>
      </div>
      <div class="relation-chips">
        <span v-for="relation in current.relations" :key="relation.id" class="relation-chip">
          {{ relation.direction }} · {{ relation.name }}
        </span>
      </div>
      <RouterLink to="/company-chat" class="primary-link">进入上下游协同问答</RouterLink>
    </section>
  </div>
</template>

<style scoped>
.dashboard {
  max-width: 1360px;
  margin: 0 auto;
  padding: var(--space-5);
}
.context-bar,
.panel,
.metric,
.network-strip {
  border: 1px solid var(--border-default);
  background: var(--bg-1);
  border-radius: 8px;
}
.context-bar {
  display: flex;
  justify-content: space-between;
  gap: var(--space-5);
  padding: var(--space-4) var(--space-5);
  margin-bottom: var(--space-4);
}
.context-main { min-width: 0; }
.context-title {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin: 4px 0 6px;
}
.enterprise-select {
  min-width: 260px;
  max-width: 100%;
  border: 1px solid var(--border-strong);
  border-radius: 6px;
  padding: 8px 10px;
  color: var(--text-primary);
  background: var(--bg-2);
  font-size: var(--font-size-lg);
  font-weight: 700;
}
.role { color: var(--text-secondary); font-size: var(--font-size-sm); }
.context-main p { color: var(--text-tertiary); font-size: var(--font-size-sm); }
.context-meta { display: flex; gap: var(--space-2); align-items: flex-start; flex-wrap: wrap; justify-content: flex-end; }
.context-meta span,
.pill,
.relation-chip,
.action-type {
  border: 1px solid var(--border-subtle);
  background: var(--bg-2);
  border-radius: 999px;
  padding: 3px 8px;
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  white-space: nowrap;
}
.eyebrow {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  font-weight: 700;
}
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.metric { padding: var(--space-4); }
.metric span,
.metric small { display: block; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.metric b { display: block; margin: 6px 0 2px; color: var(--text-primary); font-size: var(--font-size-2xl); }
.metric--risk b { color: var(--danger); }
.first-screen {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(360px, 0.9fr);
  gap: var(--space-4);
  align-items: start;
}
.panel { padding: var(--space-4); min-width: 0; }
.panel--orders { grid-row: span 2; }
.panel-head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  align-items: flex-start;
  margin-bottom: var(--space-3);
}
.panel-head h2 { margin-top: 3px; color: var(--text-primary); font-size: var(--font-size-lg); }
.text-link,
.primary-link {
  color: var(--accent-hover);
  font-size: var(--font-size-sm);
  white-space: nowrap;
}
.dense-table { overflow-x: auto; }
.table-row {
  display: grid;
  grid-template-columns: 70px 120px minmax(180px, 1fr) 82px 82px 58px;
  gap: var(--space-3);
  align-items: center;
  min-width: 720px;
  padding: 11px 0;
  border-bottom: 1px solid var(--border-subtle);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}
.table-row--head {
  padding-top: 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}
.product-list,
.shortage-list,
.action-list { display: grid; gap: var(--space-2); }
.product-line,
.shortage-line,
.action-line {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  background: var(--bg-2);
  text-align: left;
}
.product-line b,
.shortage-line b,
.action-line b { display: block; color: var(--text-primary); font-size: var(--font-size-sm); }
.product-line span,
.shortage-line span,
.action-line p,
.action-line small { color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: 1.5; }
.product-line__right { text-align: right; flex: 0 0 auto; }
.product-line__right small { display: block; margin-bottom: 6px; }
.inline-note {
  margin-top: var(--space-3);
  padding: var(--space-3);
  border: 1px solid rgba(234, 179, 8, 0.25);
  border-radius: 6px;
  color: var(--warning);
  background: var(--warning-soft);
  font-size: var(--font-size-xs);
}
.action-line {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
}
.risk {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 34px;
  padding: 2px 7px;
  border-radius: 999px;
  font-size: var(--font-size-xs);
  border: 1px solid var(--border-subtle);
}
.risk--高 { color: var(--danger); background: var(--danger-soft); border-color: rgba(239, 68, 68, 0.35); }
.risk--中 { color: var(--warning); background: var(--warning-soft); border-color: rgba(234, 179, 8, 0.35); }
.risk--低 { color: var(--success); background: var(--success-soft); border-color: rgba(34, 197, 94, 0.35); }
.network-strip {
  display: grid;
  grid-template-columns: minmax(220px, 0.8fr) minmax(0, 1.4fr) auto;
  gap: var(--space-4);
  align-items: center;
  margin-top: var(--space-4);
  padding: var(--space-4);
}
.network-strip h2 { color: var(--text-primary); font-size: var(--font-size-md); margin-top: 4px; }
.relation-chips { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.primary-link {
  padding: 8px 12px;
  border: 1px solid var(--accent-border);
  border-radius: 6px;
  background: var(--accent-soft);
}
@media (max-width: 1100px) {
  .metrics-grid,
  .first-screen,
  .network-strip { grid-template-columns: 1fr; }
  .panel--orders { grid-row: auto; }
}
@media (max-width: 640px) {
  .dashboard { padding: var(--space-3); }
  .context-bar { flex-direction: column; }
  .metrics-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
