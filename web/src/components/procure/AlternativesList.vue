<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Alternative } from '@/types/procure'
import Card from '@/components/ui/Card.vue'
import Tag from '@/components/ui/Tag.vue'
import ParamDiffTable from './ParamDiffTable.vue'
import SourceBadge from './SourceBadge.vue'

const props = defineProps<{
  alternatives: Alternative[]
  originalPart?: string
  originalBrand?: string
  /** 可勾选「纳入询价单」（ProcureView 活跃轮启用；历史回看只读） */
  selectable?: boolean
  /** 已纳入询价单的替代料 key 集合（part_name||part） */
  selectedParts?: Set<string>
}>()
const emit = defineEmits<{
  (e: 'toggle-part', part: string): void
}>()

const LEVEL_ORDER: Record<string, number> = { L1: 1, L2: 2, L3: 3, L4: 4, L5: 5 }

function byLevel(a: Alternative, b: Alternative) {
  return (LEVEL_ORDER[a.level] ?? 99) - (LEVEL_ORDER[b.level] ?? 99)
}
function altKey(a: Alternative) {
  return a.part_name || a.part || ''
}

// 低置信判定仅在该项真有 confidence 字段时生效(C3)
function isLowConfidence(a: Alternative) {
  return a.confidence != null && a.confidence < 0.5 && !a.verified
}

// L5 或 低置信+未核验 -> 折叠区；内部按 level 排序（L1->L5）
const trusted = computed(() =>
  props.alternatives.filter((a) => a.level !== 'L5' && !isLowConfidence(a)).sort(byLevel),
)
const risky = computed(() =>
  props.alternatives.filter((a) => a.level === 'L5' || isLowConfidence(a)).sort(byLevel),
)

const expanded = ref<Set<string>>(new Set())
function toggle(name: string) {
  const s = new Set(expanded.value)
  if (s.has(name)) s.delete(name)
  else s.add(name)
  expanded.value = s
}

function isSelected(a: Alternative) {
  return !!props.selectedParts?.has(altKey(a))
}
function onToggle(a: Alternative) {
  emit('toggle-part', altKey(a))
}

const showRisky = ref(false)

const LEVEL_DESC: Record<string, string> = {
  L1: '完全等效',
  L2: '跨品牌 pin-to-pin 兼容',
  L3: '参数有差异,需工程评估',
  L4: '需工程评估',
  L5: '仅作参考',
}
</script>

<template>
  <div class="alts">
    <div v-if="originalPart" class="alts__origin">
      <div class="alts__origin-label">原型号(缺货)</div>
      <div class="alts__origin-part mono">{{ originalPart }}</div>
      <div v-if="originalBrand" class="alts__origin-brand">{{ originalBrand }}</div>
    </div>

    <div v-if="trusted.length" class="alts__section">
      <div class="alts__section-head">
        <h4>推荐替代料</h4>
        <span class="alts__count num">{{ trusted.length }} 个</span>
      </div>
      <div class="alts__list">
        <Card v-for="a in trusted" :key="altKey(a)" elevated>
          <template #header>
            <div class="alt__head">
              <label v-if="selectable" class="alt__include" :title="'纳入询价单'">
                <input
                  type="checkbox"
                  class="alt__check"
                  :checked="isSelected(a)"
                  @change="onToggle(a)"
                >
              </label>
              <span class="alt__part mono">{{ a.part_name }}</span>
              <Tag type="level" :level="a.level" />
            </div>
          </template>
          <div class="alt__meta">
            <span class="alt__brand">{{ a.brand }}</span>
            <span class="alt__sep">·</span>
            <span>{{ a.package }}</span>
          </div>
          <div class="alt__params">
            <span v-for="(v, k) in a.key_params" :key="k" class="alt__param">
              <em>{{ k }}</em> <span class="num">{{ v }}</span>
            </span>
          </div>
          <div class="alt__stats">
            <div v-if="a.confidence != null" class="alt__stat">
              <span class="alt__stat-label">置信度</span>
              <span class="alt__stat-val num" :class="{ low: a.confidence < 0.6 }">
                {{ Math.round(a.confidence * 100) }}%
              </span>
            </div>
            <div class="alt__stat">
              <span class="alt__stat-label">人工核验</span>
              <span class="alt__stat-val" :class="a.verified ? 'ok' : 'warn'">
                {{ a.verified ? '已核验' : '未核验' }}
              </span>
            </div>
            <div class="alt__stat alt__stat--level">
              <span class="alt__stat-label">{{ LEVEL_DESC[a.level] }}</span>
            </div>
          </div>
          <div class="alt__source">
            <SourceBadge v-if="a.source" :source="a.source" :verified="a.verified" />
            <span v-else>来源:{{ a.source }}</span>
            <span>更新:{{ a.updated_at }}</span>
          </div>
          <p v-if="a.note" class="alt__note"><span aria-hidden="true">⚠</span> {{ a.note }}</p>
          <button v-if="a.diffs?.length" class="alt__toggle" @click="toggle(altKey(a))">
            {{ expanded.has(altKey(a)) ? '收起参数对比' : '查看参数对比' }}
          </button>
          <div v-if="a.diffs?.length && expanded.has(altKey(a))" class="alt__diff">
            <ParamDiffTable :diffs="a.diffs" />
          </div>
        </Card>
      </div>
    </div>

    <div v-if="risky.length" class="alts__risky">
      <button class="alts__risky-toggle" @click="showRisky = !showRisky">
        <span class="alts__risky-icon" aria-hidden="true">⚠</span>
        仅供参考,需工程师确认({{ risky.length }} 个低置信 / 未核验结果)
        <span class="alts__risky-arrow">{{ showRisky ? '收起' : '展开' }}</span>
      </button>
      <p class="alts__risky-hint">
        以下替代料数据来源单一或置信度低,不代表可安全替代,须由工程师向原厂/供应商确认后方可使用。
      </p>
      <div v-if="showRisky" class="alts__risky-list">
        <Card v-for="a in risky" :key="altKey(a)">
          <template #header>
            <div class="alt__head">
              <span class="alt__part mono">{{ a.part_name }}</span>
              <Tag type="level" :level="a.level" />
            </div>
          </template>
          <div class="alt__meta">
            <span class="alt__brand">{{ a.brand }}</span>
            <span class="alt__sep">·</span>
            <span>{{ a.package }}</span>
            <template v-if="a.confidence != null">
              <span class="alt__sep">·</span>
              <span class="alt__conf-low">置信度 <span class="num">{{ Math.round(a.confidence * 100) }}%</span></span>
            </template>
          </div>
          <div class="alt__source">
            <SourceBadge v-if="a.source" :source="a.source" :verified="a.verified" />
            <span v-else>来源:{{ a.source }}</span>
            <span>更新:{{ a.updated_at }}</span>
          </div>
          <p v-if="a.note" class="alt__note"><span aria-hidden="true">⚠</span> {{ a.note }}</p>
          <!-- 高风险(L5)卡片补参数对比入口 -->
          <button v-if="a.diffs?.length" class="alt__toggle" @click="toggle(altKey(a))">
            {{ expanded.has(altKey(a)) ? '收起参数对比' : '查看参数对比' }}
          </button>
          <div v-if="a.diffs?.length && expanded.has(altKey(a))" class="alt__diff">
            <ParamDiffTable :diffs="a.diffs" />
          </div>
        </Card>
      </div>
    </div>

    <div v-if="!alternatives.length" class="alts__empty">
      <div class="alts__empty-icon">⊘</div>
      <p class="alts__empty-title">暂无安全替代建议</p>
      <p class="alts__empty-desc">当前需求信息不足以安全推荐替代料,请返回补充型号或规格参数。</p>
    </div>
  </div>
</template>

<style scoped>
.alts__origin {
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--bg-subtle);
  border: 1px dashed var(--border-default);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-5);
}
.alts__origin-label { font-size: var(--font-size-xs); line-height: var(--leading-xs); color: var(--text-tertiary); }
.alts__origin-part { font-size: var(--font-size-lg); line-height: var(--leading-lg); font-weight: 600; color: var(--text-primary); }
.alts__origin-brand { font-size: var(--font-size-sm); line-height: var(--leading-sm); color: var(--text-secondary); }

.alts__section-head { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3); }
.alts__section-head h4 { font-size: var(--font-size-md); line-height: var(--leading-md); font-weight: 600; }
.alts__count { font-size: var(--font-size-xs); line-height: var(--leading-xs); color: var(--text-tertiary); }
.alts__list { display: flex; flex-direction: column; gap: var(--space-3); }

.alt__head { display: flex; align-items: center; gap: var(--space-3); }
.alt__include { display: inline-flex; align-items: center; }
.alt__check { width: 16px; height: 16px; accent-color: var(--accent); cursor: pointer; }
.alt__part { font-size: var(--font-size-md); line-height: var(--leading-md); font-weight: 600; color: var(--text-primary); }
.alt__meta { display: flex; align-items: center; gap: var(--space-2); font-size: var(--font-size-sm); line-height: var(--leading-sm); color: var(--text-secondary); margin-bottom: var(--space-3); }
.alt__sep { color: var(--text-tertiary); }
.alt__brand { color: var(--text-primary); }
.alt__params { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-bottom: var(--space-3); }
.alt__param {
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  padding: var(--space-1) var(--space-2);
  background: var(--bg-subtle);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
}
.alt__param em { font-style: normal; color: var(--text-tertiary); margin-right: var(--space-1); }
.alt__stats { display: flex; gap: var(--space-5); padding: var(--space-3) 0; border-top: 1px solid var(--border-subtle); border-bottom: 1px solid var(--border-subtle); margin-bottom: var(--space-3); }
.alt__stat { display: flex; flex-direction: column; gap: var(--space-1); }
.alt__stat-label { font-size: var(--font-size-xs); line-height: var(--leading-xs); color: var(--text-tertiary); }
.alt__stat-val { font-size: var(--font-size-sm); line-height: var(--leading-sm); font-weight: 600; color: var(--text-primary); }
.alt__stat-val.low { color: var(--warning); }
.alt__stat-val.ok { color: var(--success); }
.alt__stat-val.warn { color: var(--warning); }
.alt__stat--level .alt__stat-label { color: var(--text-secondary); }
.alt__source { display: flex; gap: var(--space-4); font-size: var(--font-size-xs); line-height: var(--leading-xs); color: var(--text-tertiary); margin-bottom: var(--space-3); }
.alt__note {
  display: flex;
  gap: var(--space-1);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  color: var(--notice);
  background: var(--notice-soft);
  border: 1px solid var(--notice-border);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  margin-bottom: var(--space-3);
}
.alt__toggle {
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  color: var(--accent-text);
  padding: var(--space-1) 0;
}
.alt__toggle:hover { color: var(--accent-hover); }
.alt__diff { margin-top: var(--space-3); }
.alts__risky { margin-top: var(--space-5); }
.alts__risky-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-3) var(--space-4);
  background: var(--warning-soft);
  border: 1px solid var(--warning-border);
  border-radius: var(--radius-md);
  color: var(--warning);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  font-weight: 500;
  transition: background-color var(--transition-fast);
}
.alts__risky-toggle:hover { background: var(--warning-soft); }
.alts__risky-icon { font-size: var(--font-size-md); }
.alts__risky-arrow { margin-left: auto; font-size: var(--font-size-xs); opacity: 0.8; }
.alts__risky-hint { font-size: var(--font-size-xs); line-height: var(--leading-xs); color: var(--text-tertiary); padding: var(--space-2) var(--space-4); }
.alts__risky-list { display: flex; flex-direction: column; gap: var(--space-3); margin-top: var(--space-3); }
.alt__conf-low { color: var(--warning); }

.alts__empty { text-align: center; padding: var(--space-8) var(--space-4); }
.alts__empty-icon { font-size: var(--font-size-3xl); color: var(--text-tertiary); margin-bottom: var(--space-3); }
.alts__empty-title { font-size: var(--font-size-lg); line-height: var(--leading-lg); font-weight: 600; color: var(--text-secondary); margin-bottom: var(--space-2); }
.alts__empty-desc { font-size: var(--font-size-sm); line-height: var(--leading-sm); color: var(--text-tertiary); max-width: 360px; margin: 0 auto; }
</style>
