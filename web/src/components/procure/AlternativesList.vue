<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Alternative } from '@/types/procure'
import Card from '@/components/ui/Card.vue'
import Tag from '@/components/ui/Tag.vue'
import ParamDiffTable from './ParamDiffTable.vue'

const props = defineProps<{
  alternatives: Alternative[]
  originalPart?: string
  originalBrand?: string
}>()

// L5 或 低置信+未核验 -> 折叠区
const trusted = computed(() =>
  props.alternatives.filter((a) => a.level !== 'L5' && !(a.confidence < 0.5 && !a.verified)),
)
const risky = computed(() =>
  props.alternatives.filter((a) => a.level === 'L5' || (a.confidence < 0.5 && !a.verified)),
)

const expanded = ref<Set<string>>(new Set())
function toggle(name: string) {
  const s = new Set(expanded.value)
  if (s.has(name)) {
    s.delete(name)
  } else {
    s.add(name)
  }
  expanded.value = s
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
        <span class="alts__count">{{ trusted.length }} 个</span>
      </div>
      <div class="alts__list">
        <Card v-for="a in trusted" :key="a.part_name" elevated>
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
          </div>
          <div class="alt__params">
            <span v-for="(v, k) in a.key_params" :key="k" class="alt__param">
              <em>{{ k }}</em> {{ v }}
            </span>
          </div>
          <div class="alt__stats">
            <div class="alt__stat">
              <span class="alt__stat-label">置信度</span>
              <span class="alt__stat-val" :class="{ low: a.confidence < 0.6 }">
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
            <span>来源:{{ a.source }}</span>
            <span>更新:{{ a.updated_at }}</span>
          </div>
          <p v-if="a.note" class="alt__note">⚠ {{ a.note }}</p>
          <button v-if="a.diffs?.length" class="alt__toggle" @click="toggle(a.part_name)">
            {{ expanded.has(a.part_name) ? '收起参数对比' : '查看参数对比' }}
          </button>
          <div v-if="a.diffs?.length && expanded.has(a.part_name)" class="alt__diff">
            <ParamDiffTable :diffs="a.diffs" />
          </div>
        </Card>
      </div>
    </div>

    <div v-if="risky.length" class="alts__risky">
      <button class="alts__risky-toggle" @click="showRisky = !showRisky">
        <span class="alts__risky-icon">⚠</span>
        仅供参考,需工程师确认({{ risky.length }} 个低置信 / 未核验结果)
        <span class="alts__risky-arrow">{{ showRisky ? '收起' : '展开' }}</span>
      </button>
      <p class="alts__risky-hint">
        以下替代料数据来源单一或置信度低,不代表可安全替代,须由工程师向原厂/供应商确认后方可使用。
      </p>
      <div v-if="showRisky" class="alts__risky-list">
        <Card v-for="a in risky" :key="a.part_name">
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
            <span class="alt__sep">·</span>
            <span class="alt__conf-low">置信度 {{ Math.round(a.confidence * 100) }}%</span>
          </div>
          <div class="alt__source">
            <span>来源:{{ a.source }}</span>
            <span>更新:{{ a.updated_at }}</span>
          </div>
          <p v-if="a.note" class="alt__note">⚠ {{ a.note }}</p>
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
  background: var(--bg-3);
  border: 1px dashed var(--border-default);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-5);
}
.alts__origin-label { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.alts__origin-part { font-size: var(--font-size-lg); font-weight: 600; color: var(--text-primary); }
.alts__origin-brand { font-size: var(--font-size-sm); color: var(--text-secondary); }

.alts__section-head { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3); }
.alts__section-head h4 { font-size: var(--font-size-md); font-weight: 600; }
.alts__count { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.alts__list { display: flex; flex-direction: column; gap: var(--space-3); }

.alt__head { display: flex; align-items: center; gap: var(--space-3); }
.alt__part { font-size: var(--font-size-md); font-weight: 600; color: var(--text-primary); }
.alt__meta { display: flex; align-items: center; gap: var(--space-2); font-size: var(--font-size-sm); color: var(--text-secondary); margin-bottom: var(--space-3); }
.alt__sep { color: var(--text-tertiary); }
.alt__brand { color: var(--text-primary); }
.alt__params { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-bottom: var(--space-3); }
.alt__param { font-size: var(--font-size-xs); padding: 3px 8px; background: var(--bg-3); border-radius: var(--radius-sm); color: var(--text-secondary); }
.alt__param em { font-style: normal; color: var(--text-tertiary); margin-right: 4px; }
.alt__stats { display: flex; gap: var(--space-5); padding: var(--space-3) 0; border-top: 1px solid var(--border-subtle); border-bottom: 1px solid var(--border-subtle); margin-bottom: var(--space-3); }
.alt__stat { display: flex; flex-direction: column; gap: 2px; }
.alt__stat-label { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.alt__stat-val { font-size: var(--font-size-sm); font-weight: 600; color: var(--text-primary); }
.alt__stat-val.low { color: var(--warning); }
.alt__stat-val.ok { color: var(--success); }
.alt__stat-val.warn { color: var(--warning); }
.alt__stat--level .alt__stat-label { color: var(--text-secondary); }
.alt__source { display: flex; gap: var(--space-4); font-size: var(--font-size-xs); color: var(--text-tertiary); margin-bottom: var(--space-3); }
.alt__note { font-size: var(--font-size-xs); color: var(--notice); background: var(--notice-soft); padding: var(--space-2) var(--space-3); border-radius: var(--radius-sm); margin-bottom: var(--space-3); }
.alt__toggle { font-size: var(--font-size-sm); color: var(--accent-hover); padding: 4px 0; }
.alt__toggle:hover { color: var(--accent); }
.alt__diff { margin-top: var(--space-3); }

.alts__risky { margin-top: var(--space-5); }
.alts__risky-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-3) var(--space-4);
  background: var(--warning-soft);
  border: 1px solid rgba(234, 179, 8, 0.3);
  border-radius: var(--radius-md);
  color: var(--warning);
  font-size: var(--font-size-sm);
  font-weight: 500;
}
.alts__risky-toggle:hover { background: rgba(234, 179, 8, 0.18); }
.alts__risky-icon { font-size: 16px; }
.alts__risky-arrow { margin-left: auto; font-size: var(--font-size-xs); opacity: 0.8; }
.alts__risky-hint { font-size: var(--font-size-xs); color: var(--text-tertiary); padding: var(--space-2) var(--space-4); }
.alts__risky-list { display: flex; flex-direction: column; gap: var(--space-3); margin-top: var(--space-3); }
.alt__conf-low { color: var(--warning); }

.alts__empty { text-align: center; padding: var(--space-8) var(--space-4); }
.alts__empty-icon { font-size: 40px; color: var(--text-tertiary); margin-bottom: var(--space-3); }
.alts__empty-title { font-size: var(--font-size-lg); font-weight: 600; color: var(--text-secondary); margin-bottom: var(--space-2); }
.alts__empty-desc { font-size: var(--font-size-sm); color: var(--text-tertiary); max-width: 360px; margin: 0 auto; }
</style>
