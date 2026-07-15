<script setup lang="ts">
import { computed } from 'vue'
import type { AltLevel } from '@/types/procure'

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
    const map: Record<AltLevel, string> = {
      L1: 'tag--success',
      L2: 'tag--success',
      L3: 'tag--warning',
      L4: 'tag--notice',
      L5: 'tag--danger',
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
  padding: 0 8px;
  font-size: var(--font-size-xs);
  font-weight: 600;
  border-radius: var(--radius-sm);
  white-space: nowrap;
  font-family: var(--font-mono);
}
.tag--success { color: var(--success); background: var(--success-soft); }
.tag--warning { color: var(--warning); background: var(--warning-soft); }
.tag--notice { color: var(--notice); background: var(--notice-soft); }
.tag--danger { color: var(--danger); background: var(--danger-soft); }
.tag--neutral { color: var(--text-secondary); background: var(--bg-3); }
.tag--match { color: var(--success); background: var(--success-soft); }
.tag--diff { color: var(--warning); background: var(--warning-soft); }
.tag--risk { color: var(--danger); background: var(--danger-soft); }
</style>
