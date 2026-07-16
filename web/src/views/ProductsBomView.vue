<script setup lang="ts">
import { useEnterpriseContext } from '@/composables/useEnterpriseContext'
import type { RiskLevel } from '@/types/enterprise'

const { current } = useEnterpriseContext()

function riskClass(risk: RiskLevel) {
  return `risk risk--${risk}`
}
</script>

<template>
  <div class="page">
    <header class="page-head">
      <div>
        <span class="eyebrow">{{ current.company.name }}</span>
        <h1>产品与 BOM</h1>
        <p>按当前企业展示可生产产品、关键物料库存、缺口、替代料和关联供应商。</p>
      </div>
      <RouterLink to="/shortage-procurement" class="action-link">查看缺件与采购</RouterLink>
    </header>

    <section class="product-stack">
      <article v-for="product in current.products" :key="product.id" class="product-section">
        <div class="product-head">
          <div>
            <h2>{{ product.model }} · {{ product.name }}</h2>
            <p>{{ product.capacity }} · 月计划 {{ product.monthlyPlan.toLocaleString() }} · {{ product.status }}</p>
          </div>
          <span :class="riskClass(product.risk)">{{ product.risk }}</span>
        </div>

        <div class="bom-table">
          <div class="bom-row bom-row--head">
            <span>关键零件</span>
            <span>编码</span>
            <span>库存</span>
            <span>需求</span>
            <span>缺口</span>
            <span>替代料</span>
            <span>供应商</span>
            <span>风险</span>
          </div>
          <div v-for="part in product.bom" :key="part.code" class="bom-row">
            <span class="strong">{{ part.name }}</span>
            <span>{{ part.code }}</span>
            <span>{{ part.inventory.toLocaleString() }}</span>
            <span>{{ part.demand.toLocaleString() }}</span>
            <span :class="{ danger: part.gap > 0 }">{{ part.gap.toLocaleString() }}</span>
            <span>{{ part.alternatives }}</span>
            <span>{{ part.suppliers }}</span>
            <span :class="riskClass(part.risk)">{{ part.risk }}</span>
          </div>
        </div>
      </article>
    </section>
  </div>
</template>

<style scoped>
.page {
  max-width: 1280px;
  margin: 0 auto;
  padding: var(--space-5);
}
.page-head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  align-items: flex-start;
  margin-bottom: var(--space-4);
  padding: var(--space-4);
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-1);
}
.eyebrow { color: var(--text-tertiary); font-size: var(--font-size-xs); font-weight: 700; }
h1 { margin-top: 4px; color: var(--text-primary); font-size: var(--font-size-2xl); }
.page-head p { margin-top: 6px; color: var(--text-secondary); font-size: var(--font-size-sm); }
.action-link {
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid var(--accent-border);
  background: var(--accent-soft);
  color: var(--accent-hover);
  font-size: var(--font-size-sm);
  white-space: nowrap;
}
.product-stack { display: grid; gap: var(--space-4); }
.product-section {
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-1);
  overflow: hidden;
}
.product-head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-4);
  border-bottom: 1px solid var(--border-subtle);
}
.product-head h2 { color: var(--text-primary); font-size: var(--font-size-lg); }
.product-head p { margin-top: 4px; color: var(--text-tertiary); font-size: var(--font-size-sm); }
.bom-table { overflow-x: auto; }
.bom-row {
  display: grid;
  grid-template-columns: minmax(160px, 1.2fr) 130px repeat(5, 86px) 64px;
  gap: var(--space-3);
  align-items: center;
  min-width: 880px;
  padding: 12px var(--space-4);
  border-bottom: 1px solid var(--border-subtle);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}
.bom-row:last-child { border-bottom: 0; }
.bom-row--head {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  background: rgba(255, 255, 255, 0.02);
}
.strong { color: var(--text-primary); font-weight: 600; }
.danger { color: var(--danger); font-weight: 700; }
.risk {
  display: inline-flex;
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
@media (max-width: 700px) {
  .page { padding: var(--space-3); }
  .page-head { flex-direction: column; }
}
</style>
