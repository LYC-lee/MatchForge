<script setup lang="ts">
/**
 * 演示场景悬浮控制台（仅 demo 用户可见）。
 * 推进演示沙盘：生成订单 / 消耗库存 / 重算缺件 / 生成 RFQ / 模拟报价 / 执行补货 / 选择替代料 / 重置场景。
 * 拖拽移动；动作后刷新全局 demo 数据（emitDemoRefresh）。
 */
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useEnterpriseContext } from '@/composables/useEnterpriseContext'
import { emitDemoRefresh } from '@/composables/useDemoRefresh'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import {
  consumeDemoInventory,
  executeDemoReplenishment,
  generateDemoOrders,
  generateDemoRfq,
  getDemoEvents,
  recalculateDemoShortages,
  resetDemoScenario,
  selectDemoAlternative,
  simulateDemoQuotes,
  type DemoEvent,
} from '@/api/demo'

const auth = useAuthStore()
const { current, currentEnterpriseId } = useEnterpriseContext()

const expanded = ref(false)
const loadingKey = ref('')
const error = ref('')
const events = ref<DemoEvent[]>([])
const position = ref({ x: 0, y: 0 })
const dragging = ref(false)
const dragOffset = ref({ x: 0, y: 0 })

const isDemo = computed(() => !!auth.user?.is_demo)
const lastResultSummary = ref('')
const lastResultKey = ref('')

const actions = [
  { key: 'orders', label: '生成新订单', run: () => generateDemoOrders(currentEnterpriseId.value) },
  { key: 'consume', label: '消耗库存', run: () => consumeDemoInventory(currentEnterpriseId.value) },
  { key: 'shortages', label: '重新计算缺件', run: () => recalculateDemoShortages(currentEnterpriseId.value) },
  { key: 'rfq', label: '生成 RFQ', run: () => generateDemoRfq(currentEnterpriseId.value) },
  { key: 'quotes', label: '模拟报价', run: () => simulateDemoQuotes(currentEnterpriseId.value) },
  { key: 'replenish', label: '执行补货', run: () => executeDemoReplenishment(currentEnterpriseId.value) },
  { key: 'alternative', label: '选择替代料', run: () => selectDemoAlternative(currentEnterpriseId.value) },
]

/** 从动作结果中提取可读摘要 (展示给用户: RFQ 编号 / no_direct_supplier / 缺件数等)。 */
function resultSummary(payload: any): string {
  if (!payload) return ''
  if (payload.no_direct_supplier) {
    return payload.message || '无可用直接关系供应商, 需要先建立合作关系/人工审核'
  }
  if (payload.rfq) {
    const cands = payload.candidates?.length || 0
    return `已生成 ${payload.rfq.rfq_number} (${cands} 家候选供应商)`
  }
  if (payload.quotes && Array.isArray(payload.quotes)) {
    const lowest = payload.lowest_price
    return lowest != null
      ? `${payload.quote_count} 家报价, 最低 ¥${lowest}`
      : `${payload.quote_count} 家报价`
  }
  if (payload.replenished_qty != null) {
    return `已补货 ${payload.replenished_qty} ${payload.unit || ''}, 可用库存恢复至 ${payload.available_after ?? '-'}`
  }
  if (payload.shortages && Array.isArray(payload.shortages)) {
    return `缺件 ${payload.shortage_count ?? 0} / 预警 ${payload.warning_count ?? 0} / 无直接供应商 ${payload.no_direct_supplier_count ?? 0}`
  }
  if (payload.order) {
    return `订单 ${payload.order.order_number}: ${payload.order.product_name} ${payload.order.quantity}${payload.order.unit || ''}`
  }
  if (payload.consumed) {
    return `消耗 ${payload.consumed.part_name} ${payload.consumed.consumed_qty}${payload.consumed.unit || ''}, 剩余 ${payload.consumed.available_after ?? '-'}`
  }
  if (payload.alternative_supplier_name) {
    return `替代料 ${payload.rfq_number}: ${payload.alternative_supplier_name}, 入库 ${payload.replenished_qty}`
  }
  if (payload.message) return payload.message
  return ''
}

const consoleStyle = computed(() => ({
  left: `${position.value.x}px`,
  top: `${position.value.y}px`,
}))

function clampPosition(x: number, y: number) {
  const width = expanded.value ? 360 : 240
  const height = expanded.value ? 620 : 72
  const pad = 12
  return {
    x: Math.max(pad, Math.min(window.innerWidth - width - pad, x)),
    y: Math.max(pad, Math.min(window.innerHeight - height - pad, y)),
  }
}

function setDefaultPosition() {
  position.value = clampPosition(window.innerWidth - 390, window.innerHeight - 120)
}

function startDrag(event: PointerEvent) {
  const target = event.target as HTMLElement
  if (target.closest('button') && !target.classList.contains('demo-console__drag')) return
  dragging.value = true
  dragOffset.value = {
    x: event.clientX - position.value.x,
    y: event.clientY - position.value.y,
  }
  window.addEventListener('pointermove', onDrag)
  window.addEventListener('pointerup', stopDrag, { once: true })
}

function onDrag(event: PointerEvent) {
  if (!dragging.value) return
  position.value = clampPosition(event.clientX - dragOffset.value.x, event.clientY - dragOffset.value.y)
}

function stopDrag() {
  dragging.value = false
  window.removeEventListener('pointermove', onDrag)
}

function normalizeEvents(payload: unknown): DemoEvent[] {
  if (Array.isArray(payload)) return payload
  const data = payload as { items?: DemoEvent[]; events?: DemoEvent[] } | null
  return data?.items || data?.events || []
}

async function loadEvents() {
  if (!isDemo.value) return
  try {
    const res = await getDemoEvents(currentEnterpriseId.value)
    events.value = normalizeEvents(res.data).slice(0, 12)
  } catch (err: any) {
    error.value = err?.response?.data?.detail || '演示事件接口暂不可用，请确认后端 demo 接口已启动。'
  }
}

async function runAction(key: string, runner: () => Promise<unknown>) {
  error.value = ''
  lastResultSummary.value = ''
  loadingKey.value = key
  try {
    const res = await runner() as any
    await loadEvents()
    emitDemoRefresh()
    const data = res?.data ?? res
    const summary = resultSummary(data)
    if (summary) {
      lastResultSummary.value = summary
      lastResultKey.value = key
    }
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err?.message || '操作失败，后端演示接口暂不可用。'
  } finally {
    loadingKey.value = ''
  }
}

// 重置场景：ConfirmDialog 二次确认（影响全部演示企业）
const showResetConfirm = ref(false)
const resetting = ref(false)
function askReset() {
  showResetConfirm.value = true
}
async function doReset() {
  showResetConfirm.value = false
  await runAction('reset', () => resetDemoScenario(currentEnterpriseId.value))
}

function eventCompany(event: DemoEvent) {
  return event.affected_company_name || event.company_name || `企业 ${event.affected_company_id || event.company_id || '-'}`
}
function eventType(event: DemoEvent) {
  return event.action_type || event.event_type || '演示事件'
}
function eventSummary(event: DemoEvent) {
  return event.result_summary || event.summary || event.message || '已产生联动变化'
}
function eventTime(event: DemoEvent) {
  const raw = event.created_at || event.timestamp
  if (!raw) return ''
  const date = new Date(raw)
  return Number.isNaN(date.getTime()) ? raw : date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

onMounted(() => {
  setDefaultPosition()
  loadEvents()
})
</script>

<template>
  <div
    v-if="isDemo"
    class="demo-console"
    :class="{ 'demo-console--open': expanded, 'is-dragging': dragging }"
    :style="consoleStyle"
  >
    <!-- 收起态：悬浮条 -->
    <div v-if="!expanded" class="demo-console__fab" @pointerdown="startDrag">
      <button type="button" class="demo-console__drag" title="拖动演示控制台" aria-label="拖动">⋮⋮</button>
      <button type="button" class="demo-console__fab-main" @click="expanded = true">
        <span>演示控制台</span>
        <b>{{ current.company.name }}</b>
      </button>
    </div>

    <!-- 展开态：面板 -->
    <section v-else class="demo-console__panel" aria-label="演示控制台">
      <header class="demo-console__head" @pointerdown="startDrag">
        <div>
          <p>演示控制台</p>
          <b>{{ current.company.name }}</b>
        </div>
        <div class="demo-console__head-actions">
          <button type="button" class="demo-console__drag" title="拖动演示控制台" aria-label="拖动">⋮⋮</button>
          <button type="button" @click="expanded = false">收起</button>
        </div>
      </header>

      <div class="demo-console__actions">
        <button
          v-for="action in actions"
          :key="action.key"
          type="button"
          class="demo-console__action"
          :disabled="!!loadingKey"
          @click="runAction(action.key, action.run)"
        >
          {{ loadingKey === action.key ? '执行中…' : action.label }}
        </button>
        <button
          type="button"
          class="demo-console__action demo-console__action--danger"
          :disabled="!!loadingKey"
          @click="askReset"
        >
          {{ loadingKey === 'reset' ? '重置中…' : '重置场景' }}
        </button>
      </div>

      <p v-if="error" class="demo-console__error" role="alert">{{ error }}</p>
      <p v-else-if="lastResultSummary" class="demo-console__result">
        <b>{{ actions.find(a => a.key === lastResultKey)?.label || '操作' }}:</b> {{ lastResultSummary }}
      </p>

      <div class="demo-console__events">
        <div class="demo-console__events-head">
          <b>最近事件</b>
          <button type="button" :disabled="!!loadingKey" @click="loadEvents">刷新</button>
        </div>
        <p v-if="events.length === 0" class="demo-console__empty">暂无事件，点击上方按钮推进演示。</p>
        <article v-for="event in events" :key="String(event.id || event.event_id || event.created_at || event.summary)">
          <div>
            <b>{{ eventCompany(event) }}</b>
            <span>{{ eventTime(event) }}</span>
          </div>
          <p>{{ eventType(event) }}</p>
          <small>{{ eventSummary(event) }}</small>
        </article>
      </div>
    </section>

    <ConfirmDialog
      v-model:open="showResetConfirm"
      title="重置整个演示场景？"
      description="这会清空全部公司的演示状态和事件（不只是当前企业），恢复到初始基线。"
      confirm-text="重置场景"
      danger
      :loading="resetting"
      @confirm="doReset"
    />
  </div>
</template>

<style scoped>
.demo-console {
  position: fixed;
  z-index: var(--z-modal);
  color: var(--text-primary);
  user-select: none;
}
.demo-console.is-dragging {
  cursor: grabbing;
}

/* 收起态 FAB */
.demo-console__fab {
  width: 240px;
  min-height: 68px;
  display: grid;
  grid-template-columns: var(--space-6) minmax(0, 1fr);
  align-items: stretch;
  overflow: hidden;
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-lg);
  background: var(--bg-elevated);
  box-shadow: var(--shadow-lg);
}
.demo-console__fab-main {
  padding: var(--space-2) var(--space-3) var(--space-2) var(--space-1);
  text-align: left;
  color: var(--text-primary);
}
.demo-console__drag {
  min-width: var(--space-6);
  color: var(--accent-text);
  cursor: grab;
  font-weight: 800;
  letter-spacing: -2px;
}
.demo-console__drag:active {
  cursor: grabbing;
}
.demo-console__fab span,
.demo-console__head p {
  display: block;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
}
.demo-console__fab b,
.demo-console__head b {
  display: block;
  margin-top: var(--space-1);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
}

/* 展开态面板 */
.demo-console__panel {
  width: min(360px, calc(100vw - 28px));
  max-height: min(680px, calc(100vh - 36px));
  overflow: auto;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  background: var(--bg-elevated);
  box-shadow: var(--shadow-lg);
}
.demo-console__head,
.demo-console__events-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}
.demo-console__head {
  position: sticky;
  top: 0;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-subtle);
  background: var(--bg-elevated);
  cursor: grab;
}
.demo-console__head-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.demo-console__head-actions button,
.demo-console__events-head button {
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  transition: color var(--transition-fast);
}
.demo-console__head-actions button:hover,
.demo-console__events-head button:hover:not(:disabled) {
  color: var(--text-primary);
}

/* 动作按钮 */
.demo-console__actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
}
.demo-console__action {
  min-height: 36px;
  padding: var(--space-2) var(--space-2);
  color: var(--text-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  font-weight: 600;
  cursor: pointer;
  transition: border-color var(--transition-fast), background-color var(--transition-fast);
}
.demo-console__action:hover:not(:disabled) {
  border-color: var(--accent-border);
  background: var(--bg-subtle);
}
.demo-console__action:disabled {
  cursor: wait;
  opacity: 0.62;
}
.demo-console__action--danger {
  color: var(--danger);
  border-color: var(--danger-border);
  background: var(--danger-soft);
}
.demo-console__action--danger:hover:not(:disabled) {
  color: var(--on-accent);
  background: var(--danger);
  border-color: var(--danger);
}

/* 错误 / 结果 */
.demo-console__error {
  margin: 0 var(--space-4) var(--space-3);
  padding: var(--space-2) var(--space-2);
  color: var(--danger);
  border: 1px solid var(--danger-border);
  border-radius: var(--radius-md);
  background: var(--danger-soft);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
}
.demo-console__result {
  margin: 0 var(--space-4) var(--space-3);
  padding: var(--space-2) var(--space-2);
  color: var(--success);
  border: 1px solid var(--success-border);
  border-radius: var(--radius-md);
  background: var(--success-soft);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
}
.demo-console__result b {
  color: var(--success);
  font-weight: 700;
}

/* 事件列表 */
.demo-console__events {
  padding: 0 var(--space-4) var(--space-4);
}
.demo-console__events-head {
  margin-bottom: var(--space-2);
}
.demo-console__events-head b {
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  color: var(--text-primary);
}
.demo-console__empty {
  padding: var(--space-2);
  color: var(--text-tertiary);
  border: 1px dashed var(--border-default);
  border-radius: var(--radius-md);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
}
.demo-console__events article {
  padding: var(--space-2) 0;
  border-top: 1px solid var(--border-subtle);
}
.demo-console__events article div {
  display: flex;
  justify-content: space-between;
  gap: var(--space-2);
}
.demo-console__events article b {
  color: var(--text-primary);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
}
.demo-console__events article span,
.demo-console__events article p,
.demo-console__events article small {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
}
.demo-console__events article p {
  margin-top: var(--space-1);
  color: var(--accent-text);
}
.demo-console__events article small {
  display: block;
  margin-top: var(--space-1);
  line-height: var(--leading-xs);
}
</style>
