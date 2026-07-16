<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useEnterpriseContext } from '@/composables/useEnterpriseContext'
import { getEnterpriseContext as getMockCtx } from '@/mock/enterpriseContext'
import type { Alternative as ApiAlternative } from '@/api/index'

const route = useRoute()
const { currentEnterpriseId } = useEnterpriseContext()

const mockCtx = computed(() => getMockCtx(currentEnterpriseId.value))
const selectedPart = computed(() => String(route.query.part || mockCtx.value.shortages[0]?.code || ''))
const shortage = computed(() =>
  mockCtx.value.shortages.find((item) => item.code === selectedPart.value) || mockCtx.value.shortages[0],
)

/** 按后端 API 数据结构映射 */
const shortageView = computed(() => {
  const s = shortage.value
  if (!s) return null
  return {
    part_number: s.code,
    part_name: s.part,
    shortage_qty: s.gap,
    severity: s.risk === '高' ? 'high' as const : s.risk === '中' ? 'medium' as const : 'low' as const,
    affected_order_numbers: s.affectedProducts || [],
  }
})

/** 替代料 — 使用后端 Alternative 类型 */
const alternatives = computed<ApiAlternative[]>(() =>
  (shortage.value?.substitutes || []).map((part: string, index: number) => ({
    part,
    brand: shortage.value?.suppliers?.[index % (shortage.value?.suppliers?.length || 1)] || '',
    confidence: index === 0 ? 0.86 : 0.74,
    level: (index === 0 ? 'L2' : 'L3') as 'L2' | 'L3',
    source: 'mock',
    verified: false,
    reason: index === 0 ? '规格接近，需确认认证和客户接受度' : '可能涉及参数或结构差异，建议小批验证',
  })),
)

const LEVEL_DESC: Record<string, string> = {
  L1: '完全等效', L2: 'pin-to-pin 兼容',
  L3: '参数有差异', L4: '需工程评估', L5: '仅作参考',
}
</script>

<template>
  <div class="alt-page">
    <header class="page-head">
      <div>
        <span class="eyebrow">{{ mockCtx.company.name }}</span>
        <h1>替代料推荐</h1>
        <p>围绕当前缺件给出可验证替代料、风险说明和下一步供应商/RFQ入口。</p>
      </div>
      <RouterLink v-if="shortageView" :to="{ path: '/shortage-procurement', query: { part: shortageView.part_number } }" class="secondary">
        返回缺件与采购
      </RouterLink>
    </header>

    <section v-if="shortageView" class="summary">
      <div>
        <span class="eyebrow">原缺件</span>
        <h2>{{ shortageView.part_name }}</h2>
        <p>{{ shortageView.part_number }} · 缺口 {{ shortageView.shortage_qty.toLocaleString() }} · 影响 {{ shortageView.affected_order_numbers.join('、') }}</p>
      </div>
      <span class="risk-dot" :class="'risk-dot--' + shortageView.severity">
        <span class="risk-dot__ring"></span>
        <span class="risk-dot__text">{{ shortageView.severity === 'high' ? '高风险' : shortageView.severity === 'medium' ? '中风险' : '低风险' }}</span>
      </span>
    </section>

    <section class="alt-list">
      <article v-for="item in alternatives" :key="item.part || item.part_name" class="alt-card">
        <div class="alt-card__head">
          <div>
            <h2>{{ item.part || item.part_name }}</h2>
            <p class="alt-card__brand">{{ item.brand }}</p>
          </div>
          <div class="alt-card__tags">
            <span v-if="item.level" class="level-badge" :class="'level--' + item.level">
              <span class="level-badge__key">{{ item.level }}</span>
              <span class="level-badge__label">{{ LEVEL_DESC[item.level] }}</span>
            </span>
          </div>
        </div>
        <div class="alt-card__body">
          <div class="alt-card__stat">
            <span class="alt-card__stat-label">置信度</span>
            <span class="alt-card__stat-value" :class="{ weak: (item.confidence || 0) < 0.6 }">
              {{ item.confidence != null ? Math.round(item.confidence * 100) + '%' : '—' }}
            </span>
          </div>
          <div class="alt-card__stat">
            <span class="alt-card__stat-label">数据来源</span>
            <span class="alt-card__stat-value">{{ item.source || '—' }}</span>
          </div>
          <div class="alt-card__stat">
            <span class="alt-card__stat-label">核验状态</span>
            <span class="alt-card__stat-value" :class="item.verified ? 'ok' : 'pending'">{{ item.verified ? '已核验' : '未核验' }}</span>
          </div>
        </div>
        <p v-if="item.reason" class="alt-card__reason">{{ item.reason }}</p>
        <div v-if="!item.reason && !item.level" class="alt-card__empty">暂无替代料详情</div>
      </article>

      <div v-if="!alternatives.length" class="alt-empty">
        <p>暂无替代料数据</p>
      </div>
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

/* 风险状态指示器 — 圆点 + 文字 */
.risk-dot {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  align-self: flex-start;
  padding: 6px 0;
}
.risk-dot__ring {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  position: relative;
  flex-shrink: 0;
}
.risk-dot__ring::after {
  content: '';
  position: absolute;
  inset: -3px;
  border-radius: 50%;
  opacity: 0.2;
}
.risk-dot__text {
  font-size: var(--font-size-xs);
  font-weight: 600;
  letter-spacing: 0.03em;
}
.risk-dot--high .risk-dot__ring {
  background: #ef4444;
}
.risk-dot--high .risk-dot__ring::after {
  background: #ef4444;
}
.risk-dot--high .risk-dot__text { color: #ef4444; }
.risk-dot--med .risk-dot__ring { background: #f59e0b; }
.risk-dot--med .risk-dot__ring::after { background: #f59e0b; }
.risk-dot--med .risk-dot__text { color: #d97706; }
.risk-dot--low .risk-dot__ring { background: #22c55e; }
.risk-dot--low .risk-dot__text { color: #6b7280; }
.alt-list { display: grid; gap: var(--space-4); }
.alt-card { padding: var(--space-4); }
.alt-card__head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-3);
}
.alt-card__tags {
  display: flex;
  align-items: center;
  gap: 6px;
  align-self: flex-start;
  flex-shrink: 0;
}
.alt-card__brand { margin-top: 2px; color: var(--text-tertiary); font-size: var(--font-size-sm); }

/* L1-L5 层级标签 */
.level-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px 3px 6px;
  border-radius: 999px;
  font-size: var(--font-size-xs);
  font-weight: 600;
  white-space: nowrap;
  border: 1px solid;
}
.level-badge__key { font-size: 10px; font-weight: 800; letter-spacing: 0.02em; }
.level-badge__label { opacity: 0.9; }
.level--L1 { color: #166534; background: #dcfce7; border-color: #86efac; }
.level--L2 { color: #854d0e; background: #fef9c3; border-color: #fde68a; }
.level--L3 { color: #9a3412; background: #ffedd5; border-color: #fed7aa; }
.level--L4 { color: #7c3aed; background: #f3e8ff; border-color: #d8b4fe; }
.level--L5 { color: #6b7280; background: #f3f4f6; border-color: #d1d5db; }

/* 替代料信息行 */
.alt-card__body {
  display: flex;
  gap: var(--space-5);
  padding: var(--space-3) 0;
  border-top: 1px solid var(--border-subtle);
  border-bottom: 1px solid var(--border-subtle);
}
.alt-card__stat { display: flex; flex-direction: column; gap: 2px; }
.alt-card__stat-label { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.alt-card__stat-value { font-size: var(--font-size-sm); font-weight: 600; color: var(--text-primary); }
.alt-card__stat-value.weak { color: var(--warning); }
.alt-card__stat-value.ok { color: var(--success); }
.alt-card__stat-value.pending { color: var(--warning); }
.alt-card__reason {
  margin-top: var(--space-3);
  padding: var(--space-2) var(--space-3);
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  background: var(--bg-2);
  border-radius: 6px;
  line-height: 1.5;
}
.alt-card__empty { margin-top: var(--space-3); color: var(--text-tertiary); font-size: var(--font-size-xs); text-align: center; }
.alt-empty { padding: var(--space-8); text-align: center; color: var(--text-tertiary); }
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
  .page-head,
  .summary,
  .alt-card__head { flex-direction: column; }
  .alt-card__body { flex-wrap: wrap; gap: var(--space-3); }
}
</style>
