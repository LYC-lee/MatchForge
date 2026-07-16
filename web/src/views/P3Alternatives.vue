<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useEnterpriseContext } from '@/composables/useEnterpriseContext'

const route = useRoute()
const { current } = useEnterpriseContext()

const selectedPart = computed(() => String(route.query.part || current.value.shortages[0]?.code || ''))
const shortage = computed(() =>
  current.value.shortages.find((item) => item.code === selectedPart.value) || current.value.shortages[0],
)

const alternatives = computed(() =>
  (shortage.value?.substitutes || []).map((part, index) => ({
    part,
    level: index === 0 ? '优先验证' : '备选验证',
    confidence: index === 0 ? 86 : 74,
    risk: index === 0 ? '规格接近，需确认认证和客户接受度' : '可能涉及参数或结构差异，建议小批验证',
    supplier: shortage.value?.suppliers[index % shortage.value.suppliers.length] || '待匹配供应商',
  })),
)
</script>

<template>
  <div class="alt-page">
    <header class="page-head">
      <div>
        <span class="eyebrow">{{ current.company.name }}</span>
        <h1>替代料推荐</h1>
        <p>围绕当前缺件给出可验证替代料、风险说明和下一步供应商/RFQ入口。</p>
      </div>
      <RouterLink v-if="shortage" :to="{ path: '/shortage-procurement', query: { part: shortage.code } }" class="secondary">
        返回缺件与采购
      </RouterLink>
    </header>

    <section v-if="shortage" class="summary">
      <div>
        <span class="eyebrow">原缺件</span>
        <h2>{{ shortage.part }}</h2>
        <p>{{ shortage.code }} · 缺口 {{ shortage.gap.toLocaleString() }} · 影响 {{ shortage.affectedProducts.join('、') }}</p>
      </div>
      <strong>{{ shortage.risk }}风险</strong>
    </section>

    <section class="alt-list">
      <article v-for="item in alternatives" :key="item.part" class="alt-card">
        <div class="alt-card__head">
          <div>
            <h2>{{ item.part }}</h2>
            <p>{{ item.level }} · 置信度 {{ item.confidence }}%</p>
          </div>
          <span>{{ item.supplier }}</span>
        </div>
        <div class="compare-grid">
          <div>
            <small>替代风险</small>
            <b>{{ item.risk }}</b>
          </div>
          <div>
            <small>推荐依据</small>
            <b>与 {{ shortage?.part }} 在用途、封装/规格或交付路径上接近。</b>
          </div>
          <div>
            <small>建议动作</small>
            <b>先由工程确认规格，再向供应商发起 RFQ。</b>
          </div>
        </div>
      </article>
    </section>

    <section class="action-bar">
      <RouterLink to="/supplier-match" class="secondary">进入供应商匹配</RouterLink>
      <RouterLink to="/rfq-edit" class="primary">生成 RFQ</RouterLink>
    </section>
  </div>
</template>

<style scoped>
.alt-page {
  max-width: 1280px;
  margin: 0 auto;
  padding: var(--space-5);
}
.page-head,
.summary,
.alt-card,
.action-bar {
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
.summary p,
.alt-card p { margin-top: 6px; color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.6; }
.summary {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-4);
  margin-bottom: var(--space-4);
}
.summary h2,
.alt-card h2 { color: var(--text-primary); font-size: var(--font-size-xl); }
.summary strong {
  color: var(--danger);
  align-self: flex-start;
  border: 1px solid rgba(239, 68, 68, 0.35);
  background: var(--danger-soft);
  border-radius: 999px;
  padding: 4px 10px;
  font-size: var(--font-size-xs);
}
.alt-list { display: grid; gap: var(--space-4); }
.alt-card { padding: var(--space-4); }
.alt-card__head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-3);
}
.alt-card__head span {
  align-self: flex-start;
  border: 1px solid var(--border-subtle);
  border-radius: 999px;
  padding: 4px 9px;
  color: var(--text-secondary);
  background: var(--bg-2);
  font-size: var(--font-size-xs);
}
.compare-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
}
.compare-grid div {
  padding: var(--space-3);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  background: var(--bg-2);
}
.compare-grid small {
  display: block;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  margin-bottom: 6px;
}
.compare-grid b {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  line-height: 1.6;
}
.action-bar {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  padding: var(--space-4);
  margin-top: var(--space-4);
}
.primary,
.secondary {
  border-radius: 6px;
  padding: 8px 12px;
  font-size: var(--font-size-sm);
}
.primary { color: #fff; background: var(--gradient-accent); }
.secondary {
  color: var(--text-secondary);
  background: var(--bg-2);
  border: 1px solid var(--border-subtle);
}
@media (max-width: 900px) {
  .compare-grid { grid-template-columns: 1fr; }
  .page-head,
  .summary,
  .alt-card__head { flex-direction: column; }
}
</style>
