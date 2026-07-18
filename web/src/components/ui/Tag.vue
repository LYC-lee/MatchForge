<script setup lang="ts">
import { computed } from 'vue'
import type { AltLevel } from '@/types/procure'

/**
 * 通用小标签。状态公式：色字 + 12% alpha 底（*-soft）+ 30% alpha 边（*-border）。
 * 领域状态（L1-L5 风险、线索、审核等）请优先使用 StatusTag.vue（一处定义，全站复用）。
 */
const props = defineProps<{
  type: 'level' | 'match' | 'diff' | 'risk' | 'success' | 'warning' | 'notice' | 'danger' | 'neutral'
  value?: string
  level?: AltLevel
}>()

const text = computed(() => {
  if (props.value) return props.value
  if (props.type === 'level' && props.level) return props.level
  return ''
})

const cls = computed(() => {
  if (props.type === 'level' && props.level) {
    // L5「仅参考」为中性，不再使用 danger
    const map: Record<AltLevel, string> = {
      L1: 'tag--success',
      L2: 'tag--success',
      L3: 'tag--warning',
      L4: 'tag--notice',
      L5: 'tag--neutral',
    }
    return map[props.level]
  }
  return `tag--${props.type}`
})
</script>

<template>
  <span class="tag" :class="cls">{{ text }}</span>
</template>

<style scoped>
.tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 var(--space-2);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  font-weight: 600;
  font-family: var(--font-mono);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  white-space: nowrap;
}
.tag--success { color: var(--success); background: var(--success-soft); border-color: var(--success-border); }
.tag--warning { color: var(--warning); background: var(--warning-soft); border-color: var(--warning-border); }
.tag--notice { color: var(--notice); background: var(--notice-soft); border-color: var(--notice-border); }
.tag--danger { color: var(--danger); background: var(--danger-soft); border-color: var(--danger-border); }
.tag--neutral { color: var(--text-secondary); background: var(--bg-subtle); border-color: var(--border-default); }
.tag--match { color: var(--success); background: var(--success-soft); border-color: var(--success-border); }
.tag--diff { color: var(--warning); background: var(--warning-soft); border-color: var(--warning-border); }
.tag--risk { color: var(--danger); background: var(--danger-soft); border-color: var(--danger-border); }
.tag--level { color: var(--accent-text); background: var(--accent-soft); border-color: var(--accent-border); }
</style>
