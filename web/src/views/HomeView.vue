<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useEnterpriseContext } from '@/composables/useEnterpriseContext'
import { useDashboard } from '@/composables/useDashboard'
import type { DashboardShortage, DashboardAction } from '@/api/enterprise'

const router = useRouter()
const { current, dataSource } = useEnterpriseContext()
const { dashboard, orders, forecasts, loading, topShortages, sortedActions } = useDashboard()

const company = computed(() => dashboard.value?.company)
const metrics = computed(() => {
  const d = dashboard.value
  if (!d) return null
  const urgent = d.orders_summary?.by_priority?.urgent || 0
  return {
    pendingOrders: d.orders_summary?.active_count || 0,
    forecastDemand: d.forecast_summary?.total_forecast_quantity || 0,
    urgentOrders: urgent,
    shortageParts: (d.shortages?.items || []).filter((s) => s.shortage_type === 'shortage').length,
    availableProducts: d.products_summary?.active_count || 0,
    atRiskProducts: (d.products_summary?.items || []).filter((p) => p.status === 'at_risk').length,
  }
})

const atRiskProducts = computed(() =>
  (dashboard.value?.products_summary?.items || []).filter((p) => p.status === 'at_risk'),
)

function severityLabel(s: string) {
  return { critical: '紧急', high: '高', medium: '中', low: '低' }[s] || s
}

function severityClass(s: string) {
  return `sev sev--${s}`
}

function priorityLabel(p: string) {
  return { urgent: '紧急', high: '高', medium: '中', low: '低' }[p] || p
}

function categoryLabel(c: string) {
  return { sourcing: '采购', production: '生产', sales: '销售', collaboration: '协同' }[c] || c
}

function formatDate(iso: string | null) {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
  } catch {
    return iso
  }
}

function goProcure(shortage?: DashboardShortage) {
  router.push({
    path: '/shortage-procurement',
    query: shortage ? { part: shortage.part_number || shortage.part_name || '' } : undefined,
  })
}

function goRfqFromAction(action: DashboardAction) {
  router.push({
    path: '/shortage-procurement',
    query: {
      part: action.part_number || '',
      action_id: action.action_type,
      supplier: action.suggested_supplier_company_id ? String(action.suggested_supplier_company_id) : '',
    },
  })
}
</script>

<template>
  <div class="dashboard">
    <!-- 企业上下文条 -->
    <section class="context-bar">
      <div class="context-main">
        <span class="eyebrow">当前企业经营驾驶舱</span>
        <div class="context-title">
          <h1>{{ company?.name || '加载中…' }}</h1>
          <span class="role">{{ company?.role || current.role || '' }}</span>
          <span class="source-tag" :class="`source-tag--${dataSource}`">
            {{ dataSource === 'api' ? '实时接口' : dataSource === 'loading' ? '加载中' : '暂无数据' }}
          </span>
        </div>
        <p>{{ company?.description || current.company.description || '' }}</p>
      </div>
      <div class="context-meta">
        <span>{{ company?.region || current.company.region || '-' }}</span>
        <span>{{ current.segment_name || company?.segment_name || '-' }}</span>
        <span v-if="current.chain_position">链路: {{ current.chain_position }}</span>
      </div>
    </section>

    <!-- 指标卡 -->
    <section v-if="metrics" class="metrics-grid" aria-label="经营概览">
      <div class="metric">
        <span>待交付订单</span>
        <b>{{ metrics.pendingOrders }}</b>
        <small>{{ metrics.urgentOrders }} 个紧急订单</small>
      </div>
      <div class="metric">
        <span>预测需求</span>
        <b>{{ metrics.forecastDemand.toLocaleString() }}</b>
        <small>未来滚动预测</small>
      </div>
      <div class="metric">
        <span>可生产产品</span>
        <b>{{ metrics.availableProducts }}</b>
        <small>{{ metrics.atRiskProducts }} 个受缺件影响</small>
      </div>
      <div class="metric metric--risk">
        <span>缺件风险</span>
        <b>{{ metrics.shortageParts }}</b>
        <small>需采购/替代/协同处理</small>
      </div>
    </section>

    <!-- 加载骨架 -->
    <div v-if="loading" class="loading-bar">正在拉取经营驾驶舱数据…</div>

    <!-- 主面板 -->
    <section v-if="dashboard" class="first-screen">
      <!-- 订单与预测 -->
      <div class="panel panel--orders">
        <div class="panel-head">
          <div>
            <span class="eyebrow">订单与预测需求</span>
            <h2>需要关注的交付</h2>
          </div>
        </div>
        <div class="dense-table">
          <div class="table-row table-row--head">
            <span>单号/周期</span>
            <span>客户/来源</span>
            <span>产品</span>
            <span>数量</span>
            <span>交期</span>
            <span>优先级</span>
          </div>
          <div v-for="item in orders.slice(0, 8)" :key="`o${item.id}`" class="table-row">
            <span class="mono">
              {{ item.order_number }}
              <small v-if="item.is_demo" class="demo-badge">演示</small>
            </span>
            <span>{{ item.customer_name || `企业${item.customer_company_id || ''}` }}</span>
            <span>{{ item.product_model || item.product_name || '-' }}</span>
            <span>{{ item.quantity.toLocaleString() }}</span>
            <span>{{ formatDate(item.due_date) }}</span>
            <span :class="severityClass(item.priority)">{{ priorityLabel(item.priority) }}</span>
          </div>
          <div v-for="item in forecasts.slice(0, 4)" :key="`f${item.id}`" class="table-row table-row--forecast">
            <span class="mono">{{ item.forecast_period }}</span>
            <span>预测需求</span>
            <span>{{ item.product_model || item.product_name || '-' }}</span>
            <span>{{ item.forecast_quantity.toLocaleString() }}</span>
            <span>置信度 {{ Math.round((item.confidence || 0) * 100) }}%</span>
            <span class="sev sev--low">预测</span>
          </div>
          <div v-if="!orders.length && !forecasts.length" class="table-row table-row--empty">
            <span>暂无订单与预测数据</span>
          </div>
        </div>
      </div>

      <!-- 可生产产品 -->
      <div class="panel">
        <div class="panel-head">
          <div>
            <span class="eyebrow">可生产产品</span>
            <h2>产品齐套与产能</h2>
          </div>
          <RouterLink to="/products-bom" class="text-link">查看 BOM</RouterLink>
        </div>
        <div class="product-list">
          <div v-for="product in dashboard.products_summary.items" :key="product.id" class="product-line">
            <div>
              <b>{{ product.product_model }}</b>
              <span>{{ product.product_name }} · 月产 {{ product.monthly_capacity?.toLocaleString() || '-' }} {{ product.unit || '' }}</span>
            </div>
            <div class="product-line__right">
              <small>{{ product.status === 'at_risk' ? '受缺件影响' : product.status || '正常' }}</small>
              <span :class="severityClass(product.status === 'at_risk' ? 'high' : 'low')">
                {{ product.status === 'at_risk' ? '风险' : '正常' }}
              </span>
            </div>
          </div>
          <div v-if="!dashboard.products_summary.items.length" class="empty-line">暂无可生产产品</div>
        </div>
        <div v-if="atRiskProducts.length" class="inline-note">
          {{ atRiskProducts.map((p) => p.product_model).join('、') }} 需要结合缺件清单重新排产。
        </div>
      </div>

      <!-- 缺件风险 -->
      <div class="panel">
        <div class="panel-head">
          <div>
            <span class="eyebrow">缺件与风险</span>
            <h2>影响订单的关键缺口</h2>
          </div>
          <button class="text-link" @click="goProcure()">进入采购</button>
        </div>
        <div class="shortage-list">
          <button v-for="item in topShortages" :key="item.id" class="shortage-line" @click="goProcure(item)">
            <div>
              <b>{{ item.part_name || item.part_number }}<small v-if="item.is_demo" class="demo-badge">演示</small></b>
              <span>缺口 {{ item.shortage_qty.toLocaleString() }} {{ item.unit || '' }} · 影响 {{ item.affected_order_numbers.join('、') || '无' }}</span>
            </div>
            <span :class="severityClass(item.severity)">{{ severityLabel(item.severity) }}</span>
          </button>
          <div v-if="!topShortages.length" class="empty-line">暂无缺件风险</div>
        </div>
      </div>

      <!-- 推荐动作 -->
      <div class="panel">
        <div class="panel-head">
          <div>
            <span class="eyebrow">推荐动作</span>
            <h2>采购、生产、销售下一步</h2>
          </div>
        </div>
        <div class="action-list">
          <div v-for="action in sortedActions.slice(0, 6)" :key="action.title" class="action-line">
            <span class="action-type" :class="`action-type--${action.category}`">
              {{ categoryLabel(action.category) }}
              <small v-if="action.is_demo" class="demo-badge demo-badge--inline">演示</small>
            </span>
            <div>
              <b>{{ action.title }}</b>
              <p>{{ action.detail }}</p>
              <small v-if="action.suggested_supplier_name">建议联系：{{ action.suggested_supplier_name }}</small>
            </div>
            <button v-if="action.category === 'sourcing'" class="action-go" @click="goRfqFromAction(action)">发起 RFQ →</button>
            <span v-else :class="severityClass(action.priority)">{{ priorityLabel(action.priority) }}</span>
          </div>
          <div v-if="!sortedActions.length" class="empty-line">暂无推荐动作</div>
        </div>
      </div>
    </section>

    <!-- 上下游概况 -->
    <section v-if="dashboard" class="network-strip">
      <div>
        <span class="eyebrow">直接上下游</span>
        <h2>协同问答只面向当前企业相关对象</h2>
      </div>
      <div class="relation-groups">
        <div v-if="dashboard.upstream_summary.items.length" class="rel-group">
          <span class="rel-label">上游</span>
          <span v-for="u in dashboard.upstream_summary.items" :key="`u${u.company_id}`" class="relation-chip">{{ u.company_name }}</span>
        </div>
        <div v-if="dashboard.downstream_summary.items.length" class="rel-group">
          <span class="rel-label">下游</span>
          <span v-for="d in dashboard.downstream_summary.items" :key="`d${d.company_id}`" class="relation-chip">{{ d.company_name }}</span>
        </div>
        <div v-if="dashboard.support_summary.items.length" class="rel-group">
          <span class="rel-label">支撑</span>
          <span v-for="s in dashboard.support_summary.items" :key="`s${s.company_id}`" class="relation-chip">{{ s.company_name }}</span>
        </div>
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
.context-title h1 { font-size: var(--font-size-xl); font-weight: 700; color: var(--text-primary); }
.role { color: var(--text-secondary); font-size: var(--font-size-sm); }
.source-tag {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: var(--font-size-xs);
  font-weight: 600;
  border: 1px solid var(--border-subtle);
}
.source-tag--api { color: var(--success); background: var(--success-soft); border-color: rgba(34, 197, 94, 0.35); }
.source-tag--mock { color: var(--warning); background: var(--warning-soft); border-color: rgba(234, 179, 8, 0.35); }
.source-tag--loading { color: var(--text-tertiary); }
.context-main p { color: var(--text-tertiary); font-size: var(--font-size-sm); line-height: 1.6; }
.context-meta { display: flex; gap: var(--space-2); align-items: flex-start; flex-wrap: wrap; justify-content: flex-end; }
.context-meta span,
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
.loading-bar {
  padding: var(--space-3) var(--space-4);
  margin-bottom: var(--space-4);
  border-radius: 6px;
  border: 1px solid var(--border-subtle);
  background: var(--bg-2);
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
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
  grid-template-columns: 110px 120px minmax(160px, 1fr) 80px 90px 64px;
  gap: var(--space-3);
  align-items: center;
  min-width: 660px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-subtle);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}
.table-row--head {
  padding-top: 0;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}
.table-row--forecast { opacity: 0.85; }
.table-row--empty { color: var(--text-tertiary); grid-template-columns: 1fr; justify-content: center; }
.mono { font-family: var(--font-mono); font-size: var(--font-size-xs); }
.demo-badge {
  display: inline-block;
  margin-left: 4px;
  padding: 1px 5px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  font-family: var(--font-base, inherit);
  color: var(--accent);
  background: var(--accent-soft);
  border: 1px solid var(--accent-border);
  vertical-align: middle;
}
.demo-badge--inline {
  margin-left: 3px;
  padding: 0 4px;
  font-size: 9px;
  color: #fff;
  background: rgba(99, 102, 241, 0.55);
  border-color: transparent;
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
.shortage-line { cursor: pointer; transition: border-color var(--transition-fast); }
.shortage-line:hover { border-color: var(--accent-border); }
.product-line b,
.shortage-line b,
.action-line b { display: block; color: var(--text-primary); font-size: var(--font-size-sm); }
.product-line span,
.shortage-line span,
.action-line p,
.action-line small { color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: 1.5; }
.product-line__right { text-align: right; flex: 0 0 auto; }
.product-line__right small { display: block; margin-bottom: 6px; }
.empty-line { padding: var(--space-3); color: var(--text-tertiary); font-size: var(--font-size-sm); text-align: center; }
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
.action-type--sourcing { color: var(--accent); background: var(--accent-soft); }
.action-type--production { color: var(--warning); background: var(--warning-soft); }
.action-type--sales { color: var(--success); background: var(--success-soft); }
.action-type--collaboration { color: #a78bfa; background: rgba(167, 139, 250, 0.12); }
.action-go {
  color: var(--accent-hover);
  font-size: var(--font-size-xs);
  font-weight: 600;
  white-space: nowrap;
  padding: 4px 8px;
  border-radius: 4px;
}
.action-go:hover { background: var(--accent-soft); }
.sev {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 34px;
  padding: 2px 7px;
  border-radius: 999px;
  font-size: var(--font-size-xs);
  border: 1px solid var(--border-subtle);
}
.sev--critical { color: var(--danger); background: var(--danger-soft); border-color: rgba(239, 68, 68, 0.35); }
.sev--high { color: var(--danger); background: var(--danger-soft); border-color: rgba(239, 68, 68, 0.3); }
.sev--urgent { color: var(--danger); background: var(--danger-soft); border-color: rgba(239, 68, 68, 0.35); }
.sev--medium { color: var(--warning); background: var(--warning-soft); border-color: rgba(234, 179, 8, 0.35); }
.sev--low { color: var(--success); background: var(--success-soft); border-color: rgba(34, 197, 94, 0.35); }
.network-strip {
  display: grid;
  grid-template-columns: minmax(220px, 0.8fr) minmax(0, 1.4fr) auto;
  gap: var(--space-4);
  align-items: center;
  margin-top: var(--space-4);
  padding: var(--space-4);
}
.network-strip h2 { color: var(--text-primary); font-size: var(--font-size-md); margin-top: 4px; }
.relation-groups { display: grid; gap: var(--space-2); }
.rel-group { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: center; }
.rel-label { color: var(--text-tertiary); font-size: var(--font-size-xs); font-weight: 700; min-width: 36px; }
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
