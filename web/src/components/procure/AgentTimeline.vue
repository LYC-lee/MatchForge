<script setup lang="ts">
import { computed, ref, onUnmounted } from 'vue'
import type { AgentName, AgentState } from '@/types/procure'

const props = withDefaults(defineProps<{
  agents: AgentState[]
  alternativesCount?: number
  suppliersCount?: number
  /** false 时冻结展示(历史沉淀), 不启动实时计时器 */
  live?: boolean
}>(), { live: true, alternativesCount: 0, suppliersCount: 0 })

const LABELS: Record<AgentName, string> = {
  parse: '需求解析',
  normalize: '规格标准化',
  alternatives: '替代料推荐',
  match: '供应商匹配',
  gen_rfq: '询价单生成',
  grade: '线索分级',
  chat: '智能问答',
}

const DESC: Record<AgentName, string> = {
  parse: '解析自然语言需求，提取型号与规格参数',
  normalize: '标准化规格字段，标注缺失与低置信项',
  alternatives: '基于知识图谱推荐兼容替代料',
  match: '向量检索匹配供应能力的供应商',
  gen_rfq: 'LLM 生成可编辑询价单',
  grade: '对询价线索进行分级评估',
  chat: '基于知识库的对话式问答',
}

const ICONS: Record<AgentName, string> = {
  parse: '🔍',
  normalize: '📋',
  alternatives: '🔄',
  match: '🏭',
  gen_rfq: '📝',
  grade: '⭐',
  chat: '💬',
}

// 实时计时器 (live=false 的沉淀时间线不启动, 避免每个历史卡片常驻 interval)
const now = ref(Date.now())
let timer: ReturnType<typeof setInterval> | undefined
if (props.live) {
  timer = setInterval(() => {
    now.value = Date.now()
  }, 200)
}
onUnmounted(() => { if (timer !== undefined) clearInterval(timer) })

function elapsed(a: AgentState): number {
  if (!a.startedAt) return 0
  const end = a.endedAt || now.value
  return end - a.startedAt
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function statusLabel(status: AgentState['status']): string {
  switch (status) {
    case 'running':
      return '进行中'
    case 'done':
      return '已完成'
    case 'error':
      return '失败'
    default:
      return '待处理'
  }
}

function statusIcon(status: AgentState['status']): string {
  switch (status) {
    case 'running':
      return '●'
    case 'done':
      return '✓'
    case 'error':
      return '✗'
    default:
      return '○'
  }
}

const items = computed(() =>
  props.agents.map((a, i) => ({
    ...a,
    label: LABELS[a.name],
    desc: DESC[a.name],
    icon: ICONS[a.name],
    elapsed: elapsed(a),
    statusText: statusLabel(a.status),
    statusIcon: statusIcon(a.status),
    isLast: i === props.agents.length - 1,
  })),
)

// 进度统计
const completedCount = computed(() => props.agents.filter((a) => a.status === 'done').length)
const totalCount = computed(() => props.agents.length)
const isComplete = computed(() => completedCount.value === totalCount.value)
const hasError = computed(() => props.agents.some((a) => a.status === 'error'))
</script>

<template>
  <div class="tl">
    <!-- 进度摘要 -->
    <div class="tl__summary">
      <div class="tl__summary-bar">
        <div
          class="tl__summary-fill"
          :class="{ complete: isComplete, error: hasError }"
          :style="{ width: `${(completedCount / totalCount) * 100}%` }"
        />
      </div>
      <span class="tl__summary-text">
        {{ completedCount }}/{{ totalCount }} 阶段完成
        <span v-if="hasError" class="tl__summary-error">（有错误）</span>
      </span>
    </div>

    <!-- 时间线 -->
    <div class="tl__list">
      <div
        v-for="a in items"
        :key="a.name"
        class="tl__item"
        :class="`tl__item--${a.status}`"
      >
        <!-- 轨道 -->
        <div class="tl__rail">
          <span class="tl__dot" :class="`tl__dot--${a.status}`">
            <span v-if="a.status === 'running'" class="tl__spinner" />
            <span v-else class="tl__dot-icon">{{ a.statusIcon }}</span>
          </span>
          <span v-if="!a.isLast" class="tl__line" :class="`tl__line--${a.status}`" />
        </div>

        <!-- 内容 -->
        <div class="tl__body">
          <div class="tl__head">
            <span class="tl__icon">{{ a.icon }}</span>
            <span class="tl__label">{{ a.label }}</span>
            <span v-if="a.elapsed" class="tl__elapsed" :class="{ running: a.status === 'running' }">
              {{ formatDuration(a.elapsed) }}
            </span>
            <span class="tl__badge" :class="`tl__badge--${a.status}`">
              {{ a.statusText }}
            </span>
          </div>
          <p class="tl__desc">{{ a.desc }}</p>

          <!-- 运行中效果 -->
          <div v-if="a.status === 'running'" class="tl__running-hint">
            <span class="tl__running-dot" />
            <span>正在执行中…</span>
          </div>

          <!-- 错误信息 -->
          <p v-if="a.message && a.status === 'error'" class="tl__msg">{{ a.message }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tl { display: flex; flex-direction: column; }

/* 进度摘要 */
.tl__summary {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
  padding: var(--space-3);
  background: var(--bg-2);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-subtle);
}
.tl__summary-bar {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: var(--bg-3);
  overflow: hidden;
}
.tl__summary-fill {
  height: 100%;
  border-radius: 3px;
  background: var(--accent);
  transition: width 0.5s ease;
}
.tl__summary-fill.complete { background: var(--success); }
.tl__summary-fill.error { background: var(--warning); }
.tl__summary-text {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  white-space: nowrap;
}
.tl__summary-error { color: var(--danger); }

/* 时间线列表 */
.tl__list { display: flex; flex-direction: column; }

/* 单条 */
.tl__item { display: flex; gap: var(--space-3); min-height: 64px; }

/* 轨道 */
.tl__rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 20px;
  flex-shrink: 0;
  padding-top: 2px;
}
.tl__dot {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  position: relative;
}
.tl__dot--pending {
  border: 2px solid var(--border-strong);
  background: var(--bg-1);
}
.tl__dot--running {
  border: 2px solid var(--accent);
  background: var(--accent-soft);
}
.tl__dot--done {
  border: 2px solid var(--success);
  background: var(--success);
}
.tl__dot--error {
  border: 2px solid var(--danger);
  background: var(--danger);
}
.tl__dot-icon {
  font-size: 10px;
  font-weight: 700;
  color: #fff;
}
.tl__dot--pending .tl__dot-icon {
  color: var(--text-tertiary);
  font-size: 8px;
}
.tl__spinner {
  width: 10px;
  height: 10px;
  border: 2px solid var(--accent-soft);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.tl__line {
  width: 2px;
  flex: 1;
  background: var(--border-subtle);
  margin-top: 4px;
  min-height: 20px;
  transition: background var(--transition-fast);
}
.tl__line--done { background: var(--success-soft); }
.tl__line--running { background: var(--accent-soft); }

/* 内容 */
.tl__body { flex: 1; padding-bottom: var(--space-4); }
.tl__head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.tl__icon { font-size: 14px; }
.tl__label {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--text-primary);
}
.tl__elapsed {
  font-size: var(--font-size-xs);
  font-family: var(--font-mono);
  color: var(--text-tertiary);
}
.tl__elapsed.running { color: var(--accent-hover); }
.tl__badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 999px;
  font-weight: 600;
  margin-left: auto;
}
.tl__badge--pending { color: var(--text-tertiary); background: var(--bg-3); }
.tl__badge--running { color: var(--accent-hover); background: var(--accent-soft); }
.tl__badge--done { color: var(--success); background: var(--success-soft); }
.tl__badge--error { color: var(--danger); background: var(--danger-soft); }

.tl__desc {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin-top: 2px;
}

/* 运行中提示 */
.tl__running-hint {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: 4px;
  font-size: var(--font-size-xs);
  color: var(--accent-hover);
}
.tl__running-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  animation: pulse 1s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.tl__msg {
  font-size: var(--font-size-xs);
  color: var(--danger);
  margin-top: 4px;
  padding: var(--space-2);
  background: var(--danger-soft);
  border-radius: var(--radius-sm);
}
</style>