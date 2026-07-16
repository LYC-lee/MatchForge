<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useEnterpriseContext } from '@/composables/useEnterpriseContext'
import { useDashboard, severityRank } from '@/composables/useDashboard'
import { useProcureStore } from '@/stores/procure'

const route = useRoute()
const router = useRouter()
const store = useProcureStore()
const { current, currentEnterpriseId } = useEnterpriseContext()
const { dashboard } = useDashboard()

const shortages = computed(() =>
  (dashboard.value?.shortages?.items || []).slice().sort((a, b) => severityRank(b.severity) - severityRank(a.severity))
)
const selectedCode = ref(String(route.query.part || shortages.value[0]?.part_number || ''))
const selectedShortage = computed(() =>
  shortages.value.find((item) => item.part_number === selectedCode.value) || shortages.value[0]
)
const query = ref('')

const suggestedQuery = computed(() => {
  const item = selectedShortage.value
  if (!item) return ''
  return `${current.value.company.name} 当前 ${item.part_name || item.part_number} 缺口 ${item.shortage_qty.toLocaleString()}，影响 ${(item.affected_order_numbers || []).join('、')}，请推荐替代料、供应商和 RFQ 要点。`
})

watch(() => currentEnterpriseId.value, () => {
  selectedCode.value = shortages.value[0]?.part_number || ''
  query.value = ''
})

function severityLabel(s: string) {
  return { critical: '高风险', high: '高风险', medium: '中风险', low: '低风险' }[s] || s
}

function applySuggestion() {
  query.value = suggestedQuery.value
}

function goAlternatives() {
  if (selectedShortage.value) {
    router.push({ path: '/alternatives', query: { part: selectedShortage.value.part_number } })
  }
}

function saveDraft() {
  store.rawQuery = query.value || suggestedQuery.value
  if (selectedShortage.value) {
    router.push({ path: '/shortage-procurement', query: { part: selectedShortage.value.part_number } })
  }
}
</script>

<template>
  <div class="sourcing-page">
    <header class="sourcing-head">
      <div>
        <span class="eyebrow">{{ current.company.name }}</span>
        <h1>采购寻源流程</h1>
        <p>从当前企业缺件出发，先确认影响订单，再进入替代料、供应商和 RFQ。</p>
      </div>
      <button class="primary-action" @click="saveDraft">带入缺件与采购</button>
    </header>

    <section class="sourcing-layout">
      <aside class="shortage-panel">
        <div class="panel-title">
          <span class="eyebrow">第一步</span>
          <h2>选择要寻源的缺件</h2>
        </div>

        <div class="shortage-list">
          <button
            v-for="item in shortages"
            :key="item.part_number || item.id"
            type="button"
            class="shortage-card"
            :class="{ active: selectedShortage?.part_number === item.part_number }"
            @click="selectedCode = item.part_number"
          >
            <span class="shortage-card__top">
              <b>{{ item.part_name || item.part_number }}</b>
              <i>{{ severityLabel(item.severity) }}</i>
            </span>
            <span class="shortage-card__meta">{{ item.part_number }} · 缺口 {{ item.shortage_qty.toLocaleString() }}</span>
          </button>
        </div>
      </aside>

      <main class="work-panel">
        <section v-if="selectedShortage" class="selected-card">
          <div>
            <span class="eyebrow">当前寻源对象</span>
            <h2>{{ selectedShortage.part_name || selectedShortage.part_number }}</h2>
            <p>{{ selectedShortage.is_critical ? '关键物料，建议优先处理' : '常规缺件，按正常流程处理' }}</p>
          </div>
          <div class="gap-box">
            <span>缺口</span>
            <b>{{ selectedShortage.shortage_qty.toLocaleString() }}</b>
          </div>
        </section>

        <div class="work-content">
          <section class="query-card">
            <div class="section-title">
              <span class="eyebrow">第二步</span>
              <h2>补充采购寻源说明</h2>
            </div>
            <textarea
              id="sourcing-query"
              v-model="query"
              rows="6"
              :placeholder="suggestedQuery"
              aria-label="采购寻源说明"
            />
            <div class="query-actions">
              <button type="button" class="secondary-action" @click="applySuggestion">使用推荐说明</button>
              <button type="button" class="secondary-action" @click="goAlternatives">查看替代料推荐</button>
              <button type="button" class="primary-action" @click="saveDraft">进入采购处理</button>
            </div>
          </section>

          <section v-if="selectedShortage" class="process-card">
            <div class="section-title">
              <span class="eyebrow">处理路径</span>
              <h2>从缺件到 RFQ</h2>
            </div>
            <div class="process-grid">
              <div class="process-step">
                <span>1</span>
                <b>确认缺口</b>
                <small>{{ selectedShortage.affected_order_numbers?.join('、') || '无关联订单' }}</small>
              </div>
              <div class="process-step">
                <span>2</span>
                <b>替代料评估</b>
                <small>待匹配</small>
              </div>
              <div class="process-step">
                <span>3</span>
                <b>供应商匹配</b>
                <small>{{ selectedShortage.preferred_supplier_name || '待匹配' }}</small>
              </div>
              <div class="process-step">
                <span>4</span>
                <b>生成 RFQ</b>
                <small>带入目标交期和缺口</small>
              </div>
            </div>
          </section>
        </div>
      </main>
    </section>
  </div>
</template>

<style scoped>
.sourcing-page {
  max-width: 1360px;
  margin: 0 auto;
  padding: var(--space-5) var(--space-6);
}
.sourcing-head,
.shortage-panel,
.work-panel {
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  background: #10131b;
}
.sourcing-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
  padding: 18px 20px;
}
.eyebrow {
  color: #aeb7c8;
  font-size: var(--font-size-xs);
  font-weight: 700;
}
h1 {
  margin-top: 4px;
  color: var(--text-primary);
  font-size: var(--font-size-2xl);
}
h2 {
  color: var(--text-primary);
  font-size: var(--font-size-lg);
}
.sourcing-head p,
.selected-card p {
  margin-top: 6px;
  color: #c9d0dc;
  font-size: var(--font-size-sm);
  line-height: 1.6;
}
.sourcing-layout {
  display: grid;
  grid-template-columns: 288px minmax(0, 1fr);
  gap: var(--space-4);
  align-items: start;
}
.shortage-panel,
.work-panel {
  padding: var(--space-4);
}
.panel-title {
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-default);
}
.shortage-list {
  display: grid;
  gap: var(--space-2);
  margin-top: var(--space-3);
}
.shortage-card {
  display: grid;
  gap: 6px;
  width: 100%;
  padding: var(--space-3);
  text-align: left;
  border: 1px solid var(--border-default);
  border-radius: 6px;
  background: #171b26;
  transition: border-color var(--transition-fast), background var(--transition-fast), box-shadow var(--transition-fast);
}
.shortage-card:hover,
.shortage-card.active {
  border-color: var(--accent-border);
  background: var(--bg-3);
}
.shortage-card.active {
  box-shadow: inset 3px 0 0 var(--accent);
}
.shortage-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}
.shortage-card b {
  color: var(--text-primary);
  font-size: var(--font-size-sm);
}
.shortage-card i {
  color: var(--warning);
  font-size: var(--font-size-xs);
  font-style: normal;
}
.shortage-card__meta {
  color: #aeb7c8;
  font-size: var(--font-size-xs);
}
.work-panel {
  min-width: 0;
}
.selected-card {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--border-default);
}
.gap-box {
  min-width: 100px;
  text-align: right;
}
.gap-box span {
  display: block;
  color: #aeb7c8;
  font-size: var(--font-size-xs);
}
.gap-box b {
  color: var(--danger);
  font-size: var(--font-size-2xl);
}
.work-content {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(300px, 0.8fr);
  gap: var(--space-4);
  margin-top: var(--space-4);
}
.query-card,
.process-card {
  min-width: 0;
}
.section-title {
  margin-bottom: var(--space-3);
}
.section-title h2 {
  margin-top: 4px;
}
textarea {
  width: 100%;
  resize: vertical;
  border: 1px solid var(--border-strong);
  border-radius: 6px;
  background: #171b26;
  color: var(--text-primary);
  padding: var(--space-3);
  line-height: 1.7;
  min-height: 148px;
}
textarea::placeholder {
  color: #aeb7c8;
}
.query-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-3);
}
.primary-action,
.secondary-action {
  border-radius: 6px;
  padding: 8px 12px;
  font-size: var(--font-size-sm);
}
.primary-action {
  color: #fff;
  background: var(--gradient-accent);
}
.secondary-action {
  color: #d8deea;
  background: #171b26;
  border: 1px solid var(--border-default);
}
.process-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-2);
}
.process-step {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  column-gap: var(--space-3);
  align-items: start;
  padding: 10px 12px;
  border: 1px solid var(--border-default);
  border-radius: 6px;
  background: #171b26;
}
.process-step span {
  display: inline-flex;
  width: 20px;
  height: 20px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent-hover);
  font-size: var(--font-size-xs);
  font-weight: 700;
  grid-row: span 2;
}
.process-step b {
  display: block;
  color: var(--text-primary);
  font-size: var(--font-size-sm);
}
.process-step small {
  display: block;
  margin-top: 3px;
  color: #aeb7c8;
  font-size: var(--font-size-xs);
  line-height: 1.5;
}
@media (max-width: 1120px) {
  .work-content {
    grid-template-columns: 1fr;
  }
  .process-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 760px) {
  .sourcing-layout,
  .process-grid {
    grid-template-columns: 1fr;
  }
  .sourcing-page {
    padding: var(--space-4);
  }
}
@media (max-width: 640px) {
  .sourcing-page {
    padding: var(--space-3);
  }
  .sourcing-head,
  .selected-card {
    flex-direction: column;
  }
  .gap-box {
    text-align: left;
  }
}
</style>
