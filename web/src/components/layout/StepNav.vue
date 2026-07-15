<script setup lang="ts">
import { computed } from 'vue'
import type { AgentName } from '@/types/procure'

const props = defineProps<{
  agents: { name: AgentName; status: string }[]
}>()

const LABELS: Record<AgentName, string> = {
  parse: '需求解析',
  normalize: '规格标准化',
  alternatives: '替代料推荐',
  match: '供应商匹配',
  gen_rfq: '询价单生成',
  grade: '线索分级',
}

const items = computed(() =>
  props.agents.map((a) => ({ ...a, label: LABELS[a.name] })),
)
</script>

<template>
  <div class="stepnav">
    <div
      v-for="a in items"
      :key="a.name"
      class="step"
      :class="`step--${a.status}`"
    >
      <span class="step__dot">
        <span v-if="a.status === 'done'" class="check">✓</span>
        <span v-else-if="a.status === 'running'" class="pulse" />
        <span v-else-if="a.status === 'error'" class="x">!</span>
      </span>
      <span class="step__label">{{ a.label }}</span>
    </div>
  </div>
</template>

<style scoped>
.stepnav {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex-wrap: wrap;
}
.step {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 6px 10px;
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
}
.step__dot {
  width: 16px;
  height: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  border: 1.5px solid var(--border-strong);
  font-size: 10px;
}
.step--running { color: var(--accent-hover); }
.step--running .step__dot { border-color: var(--accent); background: var(--accent-soft); }
.step--done { color: var(--text-secondary); }
.step--done .step__dot { border-color: var(--success); background: var(--success); color: #fff; }
.step--error { color: var(--danger); }
.step--error .step__dot { border-color: var(--danger); background: var(--danger-soft); color: var(--danger); }

.check { color: #fff; font-weight: 700; line-height: 1; }
.x { color: var(--danger); font-weight: 700; }
.pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
  animation: pulse 1s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.7); }
}
</style>
