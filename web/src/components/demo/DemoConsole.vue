<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useEnterpriseContext } from '@/composables/useEnterpriseContext'
import { emitDemoRefresh } from '@/composables/useDemoRefresh'
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

const actions = [
  { key: 'orders', label: '生成新订单', run: () => generateDemoOrders(currentEnterpriseId.value) },
  { key: 'consume', label: '消耗库存', run: () => consumeDemoInventory(currentEnterpriseId.value) },
  { key: 'shortages', label: '重新计算缺件', run: () => recalculateDemoShortages(currentEnterpriseId.value) },
  { key: 'rfq', label: '生成 RFQ', run: () => generateDemoRfq(currentEnterpriseId.value) },
  { key: 'quotes', label: '模拟报价', run: () => simulateDemoQuotes(currentEnterpriseId.value) },
  { key: 'replenish', label: '执行补货', run: () => executeDemoReplenishment(currentEnterpriseId.value) },
  { key: 'alternative', label: '选择替代料', run: () => selectDemoAlternative(currentEnterpriseId.value) },
]

const consoleStyle = computed(() => ({
  left: `${position.value.x}px`,
  top: `${position.value.y}px`,
}))

function clampPosition(x: number, y: number) {
  const width = expanded.value ? 360 : 220
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
  loadingKey.value = key
  try {
    await runner()
    await loadEvents()
    emitDemoRefresh()
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err?.message || '操作失败，后端演示接口暂不可用。'
  } finally {
    loadingKey.value = ''
  }
}

async function resetScenario() {
  const ok = window.confirm('这会重置整个演示场景下全部公司的演示状态和事件，不只是当前企业。确认继续？')
  if (!ok) return
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
    <div v-if="!expanded" class="demo-console__fab" @pointerdown="startDrag">
      <button type="button" class="demo-console__drag" title="拖动演示控制台">⋮⋮</button>
      <button type="button" class="demo-console__fab-main" @click="expanded = true">
        <span>演示控制台</span>
        <b>{{ current.company.name }}</b>
      </button>
    </div>

    <section v-else class="demo-console__panel" aria-label="演示控制台">
      <header class="demo-console__head" @pointerdown="startDrag">
        <div>
          <p>演示控制台</p>
          <b>{{ current.company.name }}</b>
        </div>
        <div class="demo-console__head-actions">
          <button type="button" class="demo-console__drag" title="拖动演示控制台">⋮⋮</button>
          <button type="button" @click="expanded = false">收起</button>
        </div>
      </header>

      <div class="demo-console__actions">
        <button
          v-for="action in actions"
          :key="action.key"
          type="button"
          :disabled="!!loadingKey"
          @click="runAction(action.key, action.run)"
        >
          {{ loadingKey === action.key ? '执行中...' : action.label }}
        </button>
        <button type="button" class="demo-console__reset" :disabled="!!loadingKey" @click="resetScenario">
          {{ loadingKey === 'reset' ? '重置中...' : '重置场景' }}
        </button>
      </div>

      <p v-if="error" class="demo-console__error">{{ error }}</p>

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
  </div>
</template>

<style scoped>
.demo-console {
  position: fixed;
  z-index: 90;
  color: #eef2ff;
  user-select: none;
}

.demo-console.is-dragging {
  cursor: grabbing;
}

.demo-console__fab {
  width: 220px;
  min-height: 68px;
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  align-items: stretch;
  overflow: hidden;
  border: 1px solid rgba(129, 140, 248, 0.75);
  border-radius: 14px;
  background: linear-gradient(135deg, #242a42, #141927 60%);
  box-shadow: 0 18px 52px rgba(0, 0, 0, 0.42), 0 0 0 4px rgba(99, 102, 241, 0.14);
}

.demo-console__fab-main {
  padding: 10px 14px 10px 4px;
  text-align: left;
}

.demo-console__drag {
  min-width: 32px;
  color: #c7d2fe;
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
  color: #aeb7d2;
  font-size: 12px;
}

.demo-console__fab b,
.demo-console__head b {
  display: block;
  margin-top: 3px;
  color: #f7f8ff;
  font-size: 13px;
}

.demo-console__panel {
  width: min(360px, calc(100vw - 28px));
  max-height: min(680px, calc(100vh - 36px));
  overflow: auto;
  border: 1px solid #3a4258;
  border-radius: 14px;
  background: #111520;
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.48), 0 0 0 4px rgba(99, 102, 241, 0.12);
}

.demo-console__head,
.demo-console__events-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.demo-console__head {
  position: sticky;
  top: 0;
  padding: 14px 16px;
  border-bottom: 1px solid #2e3548;
  background: #111520;
  cursor: grab;
}

.demo-console__head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.demo-console__head-actions button,
.demo-console__events-head button {
  color: #c8d1ea;
  font-size: 12px;
}

.demo-console__actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  padding: 14px 16px;
}

.demo-console__actions button {
  min-height: 36px;
  padding: 8px 10px;
  color: #eef2ff;
  border: 1px solid #394258;
  border-radius: 8px;
  background: #171c2a;
  font-size: 12px;
  font-weight: 700;
}

.demo-console__actions button:hover:not(:disabled) {
  border-color: #7c83ff;
  background: #20263a;
}

.demo-console__actions button:disabled {
  cursor: wait;
  opacity: 0.62;
}

.demo-console__reset {
  color: #ffd1d1 !important;
  border-color: rgba(248, 113, 113, 0.5) !important;
}

.demo-console__error {
  margin: 0 16px 12px;
  padding: 9px 10px;
  color: #fecaca;
  border: 1px solid rgba(248, 113, 113, 0.35);
  border-radius: 8px;
  background: rgba(127, 29, 29, 0.22);
  font-size: 12px;
  line-height: 1.5;
}

.demo-console__events {
  padding: 0 16px 16px;
}

.demo-console__events-head {
  margin-bottom: 8px;
}

.demo-console__events-head b {
  font-size: 13px;
}

.demo-console__empty {
  padding: 10px;
  color: #9aa6c2;
  border: 1px dashed #3a4258;
  border-radius: 8px;
  font-size: 12px;
}

.demo-console__events article {
  padding: 9px 0;
  border-top: 1px solid #2a3144;
}

.demo-console__events article div {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.demo-console__events article b {
  color: #f7f8ff;
  font-size: 12px;
}

.demo-console__events article span,
.demo-console__events article p,
.demo-console__events article small {
  color: #9aa6c2;
  font-size: 12px;
}

.demo-console__events article p {
  margin-top: 4px;
  color: #c7d2fe;
}

.demo-console__events article small {
  display: block;
  margin-top: 3px;
  line-height: 1.45;
}

@media (max-width: 920px) {
  .demo-console {
    right: 12px;
    bottom: 12px;
  }
}
</style>
