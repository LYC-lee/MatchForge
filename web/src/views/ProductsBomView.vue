<script setup lang="ts">
import { ref, watch } from 'vue'
import { useEnterpriseContext } from '@/composables/useEnterpriseContext'
import { onDemoRefresh } from '@/composables/useDemoRefresh'
import {
  getCompanyProducts,
  getProductBom,
  getBomSummary,
  type ProductionProduct,
  type BomItem,
  type BomSummary,
} from '@/api/enterprise'
import { useDashboard } from '@/composables/useDashboard'

const { current, currentEnterpriseId } = useEnterpriseContext()
const { dashboard } = useDashboard()

const products = ref<ProductionProduct[]>([])
const bomMap = ref<Record<number, BomItem[]>>({})
const bomSummary = ref<BomSummary | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const expandedProduct = ref<number | null>(null)

async function fetchData(companyId: number) {
  loading.value = true
  error.value = null
  try {
    const [prodRes, bomSumRes] = await Promise.all([
      getCompanyProducts(companyId),
      getBomSummary(companyId),
    ])
    products.value = (prodRes.data?.production_products || []) as ProductionProduct[]
    bomSummary.value = bomSumRes.data as BomSummary
    // 默认展开第一个产品
    if (products.value.length && !expandedProduct.value) {
      expandedProduct.value = products.value[0].id
      await loadBom(products.value[0].id, companyId)
    }
  } catch (e: any) {
    error.value = e?.message || '后端不可用'
    // 降级: 从 dashboard 取产品摘要
    products.value = (dashboard.value?.products_summary?.items || []).map((p) => ({
      id: p.id,
      company_id: companyId,
      product_name: p.product_name,
      product_model: p.product_model,
      product_type: p.product_type,
      description: p.description,
      monthly_capacity: p.monthly_capacity,
      unit: p.unit,
      status: p.status,
    }))
  } finally {
    loading.value = false
  }
}

async function loadBom(productId: number, companyId: number) {
  if (bomMap.value[productId]) return
  try {
    const res = await getProductBom(productId, companyId)
    bomMap.value[productId] = (res.data?.items || []) as BomItem[]
  } catch {
    bomMap.value[productId] = []
  }
}

async function toggleProduct(productId: number) {
  if (expandedProduct.value === productId) return
  expandedProduct.value = productId
  await loadBom(productId, currentEnterpriseId.value)
}

watch(currentEnterpriseId, (id) => {
  if (id) {
    bomMap.value = {}
    expandedProduct.value = null
    fetchData(id)
  }
}, { immediate: true })

onDemoRefresh(() => {
  bomMap.value = {}
  expandedProduct.value = null
  return fetchData(currentEnterpriseId.value)
})

function riskClass(isCritical: boolean) {
  return isCritical ? 'sev sev--high' : 'sev sev--low'
}
</script>

<template>
  <div class="page">
    <header class="page-head">
      <div>
        <span class="eyebrow">{{ current.company.name }}</span>
        <h1>产品与 BOM</h1>
        <p>按当前企业展示可生产产品、关键物料、BOM 零件和首选供应商。</p>
      </div>
      <RouterLink to="/shortage-procurement" class="action-link">查看缺件与采购</RouterLink>
    </header>

    <div v-if="loading" class="loading-bar">正在拉取产品与 BOM 数据…</div>
    <div v-if="error" class="notice-bar">后端不可用, 已降级到驾驶舱产品摘要: {{ error }}</div>

    <!-- BOM 汇总 -->
    <section v-if="bomSummary" class="bom-summary-bar">
      <div class="summary-stat">
        <b>{{ bomSummary.total_parts }}</b>
        <span>BOM 零件总数</span>
      </div>
      <div class="summary-stat">
        <b>{{ bomSummary.critical_parts }}</b>
        <span>关键件</span>
      </div>
      <div class="summary-stat">
        <b>{{ products.length }}</b>
        <span>在产产品</span>
      </div>
    </section>

    <section class="product-stack">
      <article v-for="product in products" :key="product.id" class="product-section">
        <button class="product-head" @click="toggleProduct(product.id)">
          <div class="product-head__info">
            <h2>{{ product.product_model }} · {{ product.product_name }}</h2>
            <p>
              月产 {{ product.monthly_capacity?.toLocaleString() || '-' }} {{ product.unit || '' }}
              · {{ product.product_type || '' }}
              <span v-if="product.description"> · {{ product.description }}</span>
            </p>
          </div>
          <div class="product-head__right">
            <span class="status-pill" :class="product.status === 'at_risk' ? 'status-pill--risk' : 'status-pill--ok'">
              {{ product.status === 'at_risk' ? '风险' : '在产' }}
            </span>
            <span class="expand-icon">{{ expandedProduct === product.id ? '▾' : '▸' }}</span>
          </div>
        </button>

        <div v-if="expandedProduct === product.id" class="bom-table-wrap">
          <div v-if="bomMap[product.id] === undefined" class="loading-line">加载 BOM 中…</div>
          <div v-else-if="bomMap[product.id].length === 0" class="empty-line">该产品暂无 BOM 数据</div>
          <div v-else class="bom-table">
            <div class="bom-row bom-row--head">
              <span>关键零件</span>
              <span>编码</span>
              <span>品类</span>
              <span>需求量</span>
              <span>安全库存</span>
              <span>首选供应商</span>
              <span>关键</span>
            </div>
            <div v-for="part in bomMap[product.id]" :key="part.id" class="bom-row">
              <span class="strong">{{ part.part_name }}</span>
              <span class="mono">{{ part.part_number }}</span>
              <span>{{ part.category_name || '-' }}</span>
              <span>{{ part.required_qty?.toLocaleString() || '-' }} {{ part.unit || '' }}</span>
              <span>{{ part.safety_stock_qty?.toLocaleString() || '-' }}</span>
              <span>{{ part.preferred_supplier_name || '-' }}</span>
              <span :class="riskClass(part.is_critical)">{{ part.is_critical ? '是' : '否' }}</span>
            </div>
          </div>
        </div>
      </article>
      <div v-if="!loading && !products.length" class="empty-line">当前企业暂无可生产产品</div>
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
.loading-bar,
.notice-bar {
  padding: var(--space-3) var(--space-4);
  margin-bottom: var(--space-4);
  border-radius: 6px;
  font-size: var(--font-size-sm);
}
.loading-bar { border: 1px solid var(--border-subtle); background: var(--bg-2); color: var(--text-tertiary); }
.notice-bar { border: 1px solid rgba(234, 179, 8, 0.25); background: var(--warning-soft); color: var(--warning); }
.bom-summary-bar {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.summary-stat {
  flex: 1;
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-1);
}
.summary-stat b { display: block; color: var(--text-primary); font-size: var(--font-size-xl); }
.summary-stat span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
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
  width: 100%;
  padding: var(--space-4);
  border: none;
  background: none;
  cursor: pointer;
  text-align: left;
  transition: background var(--transition-fast);
}
.product-head:hover { background: var(--bg-2); }
.product-head__info { min-width: 0; }
.product-head h2 { color: var(--text-primary); font-size: var(--font-size-lg); }
.product-head p { margin-top: 4px; color: var(--text-tertiary); font-size: var(--font-size-sm); }
.product-head__right { display: flex; align-items: center; gap: var(--space-3); flex-shrink: 0; }
.status-pill {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: var(--font-size-xs);
  font-weight: 600;
}
.status-pill--ok { color: var(--success); background: var(--success-soft); }
.status-pill--risk { color: var(--danger); background: var(--danger-soft); }
.expand-icon { color: var(--text-tertiary); font-size: var(--font-size-md); }
.bom-table-wrap { border-top: 1px solid var(--border-subtle); }
.bom-table { overflow-x: auto; }
.bom-row {
  display: grid;
  grid-template-columns: minmax(140px, 1.2fr) 130px 100px 90px 90px minmax(120px, 1fr) 56px;
  gap: var(--space-3);
  align-items: center;
  min-width: 780px;
  padding: 11px var(--space-4);
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
.mono { font-family: var(--font-mono); font-size: var(--font-size-xs); }
.loading-line,
.empty-line { padding: var(--space-4); color: var(--text-tertiary); font-size: var(--font-size-sm); text-align: center; }
.sev {
  display: inline-flex;
  justify-content: center;
  min-width: 34px;
  padding: 2px 7px;
  border-radius: 999px;
  font-size: var(--font-size-xs);
  border: 1px solid var(--border-subtle);
}
.sev--high { color: var(--danger); background: var(--danger-soft); border-color: rgba(239, 68, 68, 0.35); }
.sev--low { color: var(--success); background: var(--success-soft); border-color: rgba(34, 197, 94, 0.35); }
@media (max-width: 700px) {
  .page { padding: var(--space-3); }
  .page-head { flex-direction: column; }
  .bom-summary-bar { flex-direction: column; }
}
</style>
