<script setup lang="ts">
import { computed } from 'vue'

/**
 * 替代料来源徽章 (issue #27, A线 #16 source 枚举)
 * 三态:
 *  - Neo4j:*                  → 绿 图谱核验 (direct/transitive/cross_ref/all 细分)
 *  - llm_inferred*            → 黄 LLM 推测
 *  - rule_fallback:query_failed → 红 查询失败·须人工核验 (+ 小字提示)
 * source 缺失(旧数据)时不渲染,由父组件回退到纯文本显示。
 */
const props = defineProps<{
  source?: string
  verified?: boolean
}>()

type BadgeKind = 'neo4j' | 'llm' | 'fallback' | 'unknown'

const NEO4J_SUBTYPE: Record<string, string> = {
  direct: '图谱核验·直接',
  transitive: '图谱核验·传递',
  cross_ref: '图谱核验·交叉',
  all: '图谱核验·综合',
}

const kind = computed<BadgeKind | null>(() => {
  const s = props.source
  if (!s) return null
  if (s.startsWith('Neo4j:')) return 'neo4j'
  if (s.startsWith('llm_inferred')) return 'llm'
  if (s === 'rule_fallback:query_failed') return 'fallback'
  return 'unknown'
})

const hasRag = computed(() => !!props.source && props.source.includes('+RAG'))

const label = computed(() => {
  const s = props.source || ''
  switch (kind.value) {
    case 'neo4j': {
      const subtype = s.slice('Neo4j:'.length).replace('+RAG', '')
      const base = NEO4J_SUBTYPE[subtype] || '图谱核验'
      return hasRag.value ? `${base}·知识库` : base
    }
    case 'llm':
      return hasRag.value ? 'LLM 推测·知识库' : 'LLM 推测'
    case 'fallback':
      return '查询失败·须人工核验'
    default:
      return s
  }
})

const showUnverified = computed(() => props.verified === false)
</script>

<template>
  <span v-if="kind" class="src-badge-wrap">
    <span class="src-badge" :class="`src-badge--${kind}`">{{ label }}</span>
    <span v-if="showUnverified" class="src-badge__unverified" title="该结果未经人工核验">未核验</span>
    <span v-if="kind === 'fallback'" class="src-badge__note">未经数据库核验,须人工确认</span>
  </span>
</template>

<style scoped>
.src-badge-wrap {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.src-badge {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 var(--space-2);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  font-weight: 600;
  border-radius: var(--radius-sm);
  border: 1px solid;
  white-space: nowrap;
}
.src-badge--neo4j {
  color: var(--success);
  background: var(--success-soft);
  border-color: var(--success-border);
}
.src-badge--llm {
  color: var(--warning);
  background: var(--warning-soft);
  border-color: var(--warning-border);
}
.src-badge--fallback {
  color: var(--danger);
  background: var(--danger-soft);
  border-color: var(--danger-border);
}
.src-badge--unknown {
  color: var(--text-secondary);
  background: var(--bg-subtle);
  border-color: var(--border-default);
}

.src-badge__unverified {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 var(--space-1);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  color: var(--warning);
  background: var(--warning-soft);
  border: 1px dashed var(--warning-border);
  border-radius: var(--radius-sm);
  white-space: nowrap;
}

.src-badge__note {
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  color: var(--danger);
  opacity: 0.85;
}
</style>
