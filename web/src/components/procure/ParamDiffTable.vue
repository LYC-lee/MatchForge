<script setup lang="ts">
import { computed } from 'vue'
import type { ParamDiff } from '@/types/procure'
import Tag from '@/components/ui/Tag.vue'

const props = defineProps<{ diffs: ParamDiff[] }>()

const rows = computed(() => props.diffs)

const statusText: Record<ParamDiff['status'], string> = {
  match: '一致',
  diff: '差异',
  risk: '风险',
}
</script>

<template>
  <table class="diff">
    <thead>
      <tr><th>参数</th><th class="diff__num-h">原型号</th><th class="diff__num-h">替代型号</th><th>对比</th><th>说明</th></tr>
    </thead>
    <tbody>
      <tr v-for="r in rows" :key="r.field" :class="`row--${r.status}`">
        <td class="diff__field">{{ r.field }}</td>
        <td class="diff__val mono num" :class="`cell--${r.status}`">{{ r.original }}</td>
        <td class="diff__val mono num" :class="`cell--${r.status}`">{{ r.alternative }}</td>
        <td><Tag :type="r.status" :value="statusText[r.status]" /></td>
        <td class="diff__note">{{ r.note || (r.status === 'match' ? '完全一致' : '-') }}</td>
      </tr>
    </tbody>
  </table>
</template>

<style scoped>
.diff { width: 100%; border-collapse: collapse; }
.diff th {
  text-align: left;
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  font-weight: 600;
  color: var(--text-tertiary);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-default);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.diff__num-h { text-align: right; }
.diff td {
  padding: var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  color: var(--text-secondary);
}
.diff__field { color: var(--text-primary); font-weight: 500; }
.diff__val { text-align: right; }
/* 差异/风险：用色字表达（不整行染色） */
.cell--match { color: var(--success); }
.cell--diff { color: var(--warning); }
.cell--risk { color: var(--danger); font-weight: 600; }
.row--risk .diff__field { color: var(--danger); }
.diff__note { color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: var(--leading-xs); }
</style>
