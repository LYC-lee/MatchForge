<script setup lang="ts">
import { computed } from 'vue'

/**
 * 领域状态标签 —— 一处定义，全站复用。
 * 状态公式：色字 + 12% alpha 底（*-soft）+ 30% alpha 边（*-border）。
 *
 * 用法：
 *   <StatusTag domain="level" value="L3" />
 *   <StatusTag domain="lead" value="quoted" />
 *   <StatusTag domain="audit" value="pending" />
 * 未收录的 value 自动降级为 neutral 并原样展示。
 */

export type StatusTone = 'success' | 'warning' | 'notice' | 'danger' | 'neutral' | 'accent'
export type StatusDomain = 'level' | 'lead' | 'rfq' | 'audit' | 'agent' | 'param'

interface StatusMeta {
  label: string
  tone: StatusTone
}

/** 领域状态字典：新增/调整状态只改这里 */
const STATUS_DICT: Record<StatusDomain, Record<string, StatusMeta>> = {
  /* 替代料风险等级（L5「仅参考」为 neutral，不再 danger） */
  level: {
    L1: { label: 'L1 完全等效', tone: 'success' },
    L2: { label: 'L2 跨品牌等效', tone: 'success' },
    L3: { label: 'L3 参数有差异', tone: 'warning' },
    L4: { label: 'L4 需工程评估', tone: 'notice' },
    L5: { label: 'L5 仅参考', tone: 'neutral' },
  },
  /* 线索状态（enterprise.ts: pending | sent | viewed | quoted | declined） */
  lead: {
    pending: { label: '待处理', tone: 'notice' },
    sent: { label: '已发送', tone: 'accent' },
    viewed: { label: '已查看', tone: 'neutral' },
    quoted: { label: '已报价', tone: 'success' },
    declined: { label: '已谢绝', tone: 'danger' },
  },
  /* RFQ 状态（enterprise.ts: draft | sent | quoted | closed） */
  rfq: {
    draft: { label: '草稿', tone: 'neutral' },
    sent: { label: '已发送', tone: 'accent' },
    quoted: { label: '已报价', tone: 'success' },
    closed: { label: '已关闭', tone: 'neutral' },
  },
  /* 审核状态（enterprise.ts: pending | approved | rejected） */
  audit: {
    pending: { label: '待审核', tone: 'notice' },
    approved: { label: '已通过', tone: 'success' },
    rejected: { label: '已驳回', tone: 'danger' },
  },
  /* 智能体运行状态（procure.ts AgentStatus） */
  agent: {
    pending: { label: '等待中', tone: 'neutral' },
    running: { label: '运行中', tone: 'accent' },
    done: { label: '已完成', tone: 'success' },
    error: { label: '出错', tone: 'danger' },
  },
  /* 参数对比状态（ParamDiff.status） */
  param: {
    match: { label: '一致', tone: 'success' },
    diff: { label: '差异', tone: 'warning' },
    risk: { label: '风险', tone: 'danger' },
  },
}

const props = defineProps<{
  domain: StatusDomain
  value: string
  /** 覆盖默认文案（如数字徽标） */
  label?: string
  /** 紧凑模式：仅显示等级码（如 L3），不显示全称 */
  compact?: boolean
}>()

const meta = computed<StatusMeta>(() => {
  const hit = STATUS_DICT[props.domain]?.[props.value]
  if (hit) return hit
  return { label: props.value, tone: 'neutral' }
})

const text = computed(() => {
  if (props.label) return props.label
  if (props.compact && props.domain === 'level') return props.value
  return meta.value.label
})
</script>

<template>
  <span class="status-tag" :class="`status-tag--${meta.tone}`">{{ text }}</span>
</template>

<style scoped>
.status-tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 var(--space-2);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  font-weight: 600;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  white-space: nowrap;
}
.status-tag--success { color: var(--success); background: var(--success-soft); border-color: var(--success-border); }
.status-tag--warning { color: var(--warning); background: var(--warning-soft); border-color: var(--warning-border); }
.status-tag--notice { color: var(--notice); background: var(--notice-soft); border-color: var(--notice-border); }
.status-tag--danger { color: var(--danger); background: var(--danger-soft); border-color: var(--danger-border); }
.status-tag--neutral { color: var(--text-secondary); background: var(--bg-subtle); border-color: var(--border-default); }
.status-tag--accent { color: var(--accent-text); background: var(--accent-soft); border-color: var(--accent-border); }
</style>
