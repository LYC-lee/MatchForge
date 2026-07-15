<script setup lang="ts">
import { computed } from 'vue'
import type { AgentName, AgentState } from '@/types/procure'

const props = defineProps<{ agents: AgentState[] }>()

const LABELS: Record<AgentName, string> = {
  parse: '需求解析',
  normalize: '规格标准化',
  alternatives: '替代料推荐',
  match: '供应商匹配',
  gen_rfq: '询价单生成',
  grade: '线索分级',
}

const DESC: Record<AgentName, string> = {
  parse: '解析自然语言需求,提取型号与规格参数',
  normalize: '标准化规格字段,标注缺失与低置信项',
  alternatives: '基于知识图谱推荐兼容替代料',
  match: '向量检索匹配供应能力的供应商',
  gen_rfq: 'LLM 生成可编辑询价单',
  grade: '对询价线索进行分级评估',
}

function duration(a: AgentState): string {
  if (!a.startedAt) return ''
  const end = a.endedAt || Date.now()
  return `${((end - a.startedAt) / 1000).toFixed(1)}s`
}

const items = computed(() =>
  props.agents.map((a) => ({
    ...a,
    label: LABELS[a.name],
    desc: DESC[a.name],
    dur: duration(a),
  })),
)
</script>

<template>
  <div class="timeline">
    <div
      v-for="(a, i) in items"
      :key="a.name"
      class="tl-item"
      :class="`tl-item--${a.status}`"
    >
      <div class="tl-item__rail">
        <span class="tl-item__dot" />
        <span v-if="i < items.length - 1" class="tl-item__line" />
      </div>
      <div class="tl-item__body">
        <div class="tl-item__head">
          <span class="tl-item__label">{{ a.label }}</span>
          <span v-if="a.dur" class="tl-item__dur">{{ a.dur }}</span>
          <span class="tl-item__status" :class="`is-${a.status}`">
            {{ a.status === 'running' ? '进行中' : a.status === 'done' ? '已完成' : a.status === 'error' ? '失败' : '待处理' }}
          </span>
        </div>
        <p class="tl-item__desc">{{ a.desc }}</p>
        <p v-if="a.message" class="tl-item__msg">{{ a.message }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.timeline { display: flex; flex-direction: column; }
.tl-item { display: flex; gap: var(--space-3); min-height: 56px; }
.tl-item__rail { display: flex; flex-direction: column; align-items: center; width: 14px; flex-shrink: 0; padding-top: 3px; }
.tl-item__dot {
  width: 10px; height: 10px;
  border-radius: 50%;
  border: 2px solid var(--border-strong);
  background: var(--bg-1);
  flex-shrink: 0;
}
.tl-item__line { width: 2px; flex: 1; background: var(--border-subtle); margin-top: 2px; min-height: 16px; }

.tl-item--running .tl-item__dot { border-color: var(--accent); background: var(--accent-soft); animation: pulse 1s ease-in-out infinite; }
.tl-item--done .tl-item__dot { border-color: var(--success); background: var(--success); }
.tl-item--error .tl-item__dot { border-color: var(--danger); background: var(--danger); }

.tl-item__body { flex: 1; padding-bottom: var(--space-4); }
.tl-item__head { display: flex; align-items: center; gap: var(--space-3); }
.tl-item__label { font-size: var(--font-size-sm); font-weight: 600; color: var(--text-primary); }
.tl-item__dur { font-size: var(--font-size-xs); color: var(--text-tertiary); font-family: var(--font-mono); }
.tl-item__status { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-left: auto; }
.tl-item__status.is-running { color: var(--accent-hover); }
.tl-item__status.is-done { color: var(--success); }
.tl-item__status.is-error { color: var(--danger); }
.tl-item__desc { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.tl-item__msg { font-size: var(--font-size-xs); color: var(--danger); margin-top: 4px; }

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.8); }
}
</style>
