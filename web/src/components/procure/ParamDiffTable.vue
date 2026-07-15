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
      <tr><th>参数</th><th>原型号</th><th>替代型号</th><th>对比</th><th>说明</th></tr>
    </thead>
    <tbody>
      <tr v-for="r in rows" :key="r.field" :class="`row--${r.status}`">
        <td class="diff__field">{{ r.field }}</td>
        <td class="mono">{{ r.original }}</td>
        <td class="mono">{{ r.alternative }}</td>
        <td><Tag :type="r.status" :value="statusText[r.status]" /></td>
        <td class="diff__note">{{ r.note || (r.status === 'match' ? '完全一致' : '—') }}</td>
      </tr>
    </tbody>
  </table>
</template>

<style scoped>
.diff { width: 100%; border-collapse: collapse; }
.diff th {
  text-align: left;
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--text-tertiary);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-default);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.diff td {
  padding: var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.diff__field { color: var(--text-primary); font-weight: 500; }
.diff__note { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.row--match td { background: rgba(34, 197, 94, 0.03); }
.row--diff td { background: rgba(234, 179, 8, 0.04); }
.row--risk td { background: rgba(239, 68, 68, 0.05); }
.row--risk .diff__field,
.row--risk .mono { color: var(--danger); font-weight: 600; }
</style>
