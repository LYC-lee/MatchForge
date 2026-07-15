<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Alternative, SpecField, Supplier } from '@/types/procure'
import AppButton from '@/components/ui/AppButton.vue'

const props = defineProps<{
  rfqDoc: string
  rfqId: string | null
  spec: Record<string, SpecField> | null
  alternatives: Alternative[]
  suppliers: Supplier[]
  selectedSupplierIds: Set<string>
  sent: boolean
  streaming: boolean
}>()
const emit = defineEmits<{
  (e: 'update', text: string): void
  (e: 'sent'): void
}>()

const copied = ref(false)

const selectedSuppliers = computed(() =>
  props.suppliers.filter((s) => props.selectedSupplierIds.has(s.id)),
)

const trustedAlts = computed(() => props.alternatives.filter((a) => a.level !== 'L5'))

// spec 可能为 null,统一转成 entries 规避 v-for 类型问题
const specEntries = computed<Array<[string, SpecField]>>(() =>
  Object.entries(props.spec || {}),
)

// 关键字段缺失检测
const missingFields = computed(() => {
  const miss: string[] = []
  const s = props.spec || {}
  if (!s['月用量']?.value) miss.push('月用量')
  if (!s['交期要求']?.value) miss.push('交期要求')
  if (!selectedSuppliers.value.length) miss.push('目标供应商')
  return miss
})

const isFallback = computed(
  () => props.rfqDoc.includes('__(待补充)__') || props.rfqDoc.includes('待补充'),
)

async function copy() {
  try {
    await navigator.clipboard.writeText(props.rfqDoc)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {
    // 剪贴板不可用时静默
  }
}

function onInput(e: Event) {
  emit('update', (e.target as HTMLTextAreaElement).value)
}
</script>

<template>
  <div class="rfq">
    <div v-if="missingFields.length && !streaming" class="rfq__warn">
      <span class="rfq__warn-icon">⚠</span>
      <span>
        关键字段缺失:
        <b v-for="f in missingFields" :key="f" class="rfq__warn-field">{{ f }}</b>
        将影响询价有效性,请补充。
      </span>
    </div>

    <div class="rfq__cols">
      <aside class="rfq__side">
        <h4 class="rfq__side-title">结构化字段</h4>
        <dl class="rfq__fields">
          <template v-for="[k, v] in specEntries" :key="k">
            <dt>{{ k }}</dt>
            <dd :class="{ 'rfq__field--miss': !v.value }">{{ v.value || '缺失' }}</dd>
          </template>
        </dl>
        <div class="rfq__side-block">
          <h5>可接受替代料</h5>
          <ul class="rfq__alt-list">
            <li v-for="a in trustedAlts" :key="a.part_name">
              <span class="mono">{{ a.part_name }}</span>
              <span class="rfq__alt-brand">{{ a.brand }}</span>
            </li>
            <li v-if="!trustedAlts.length" class="rfq__empty-inline">暂无</li>
          </ul>
        </div>
        <div class="rfq__side-block">
          <h5>目标供应商({{ selectedSuppliers.length }})</h5>
          <ul class="rfq__sup-list">
            <li v-for="s in selectedSuppliers" :key="s.id">{{ s.name }}</li>
            <li v-if="!selectedSuppliers.length" class="rfq__empty-inline">未选择</li>
          </ul>
        </div>
      </aside>

      <div class="rfq__main">
        <div class="rfq__toolbar">
          <div class="rfq__id">
            <span v-if="rfqId" class="mono">{{ rfqId }}</span>
            <span v-if="streaming" class="rfq__streaming">生成中…</span>
            <span v-else-if="isFallback" class="rfq__fallback">模板兜底</span>
          </div>
          <div class="rfq__tools">
            <AppButton variant="ghost" size="sm" :disabled="streaming" @click="copy">
              {{ copied ? '已复制' : '复制' }}
            </AppButton>
            <AppButton variant="secondary" size="sm" :disabled="streaming" @click="emit('sent')">
              {{ sent ? '已发送 ✓' : '标记已发送' }}
            </AppButton>
          </div>
        </div>
        <textarea
          class="rfq__editor"
          :value="rfqDoc"
          :placeholder="streaming ? 'AI 正在生成询价单…' : '询价单内容'"
          :readonly="streaming"
          @input="onInput"
        />
        <p class="rfq__note">
          本询价单由 AI 辅助生成,替代料仅供参考,最终可替代性须由工程师确认。
          供应商回复的库存 / 交期 / 价格以正式确认为准。
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.rfq__warn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--danger-soft);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  color: var(--danger);
  margin-bottom: var(--space-4);
}
.rfq__warn-icon { font-size: 16px; }
.rfq__warn-field { margin: 0 4px; padding: 1px 6px; background: rgba(239, 68, 68, 0.2); border-radius: var(--radius-sm); }

.rfq__cols { display: grid; grid-template-columns: 280px 1fr; gap: var(--space-5); }
.rfq__side {
  background: var(--bg-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  align-self: start;
}
.rfq__side-title { font-size: var(--font-size-sm); font-weight: 600; color: var(--text-secondary); margin-bottom: var(--space-3); text-transform: uppercase; letter-spacing: 0.04em; }
.rfq__fields { display: grid; grid-template-columns: auto 1fr; gap: var(--space-2) var(--space-3); font-size: var(--font-size-sm); margin: 0; }
.rfq__fields dt { color: var(--text-tertiary); }
.rfq__fields dd { color: var(--text-primary); margin: 0; }
.rfq__field--miss { color: var(--danger) !important; }
.rfq__side-block { margin-top: var(--space-4); padding-top: var(--space-3); border-top: 1px solid var(--border-subtle); }
.rfq__side-block h5 { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-bottom: var(--space-2); text-transform: uppercase; letter-spacing: 0.04em; }
.rfq__alt-list li,
.rfq__sup-list li { font-size: var(--font-size-sm); color: var(--text-secondary); padding: 3px 0; display: flex; justify-content: space-between; gap: var(--space-2); }
.rfq__alt-brand { color: var(--text-tertiary); }
.rfq__empty-inline { color: var(--text-tertiary); font-style: italic; }

.rfq__main { display: flex; flex-direction: column; min-height: 420px; }
.rfq__toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-2); }
.rfq__id { display: flex; align-items: center; gap: var(--space-3); font-size: var(--font-size-xs); color: var(--text-tertiary); }
.rfq__streaming { color: var(--accent-hover); }
.rfq__fallback { color: var(--warning); }
.rfq__tools { display: flex; gap: var(--space-2); }

.rfq__editor {
  flex: 1;
  width: 100%;
  background: var(--bg-2);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  line-height: 1.7;
  color: var(--text-primary);
  resize: vertical;
  outline: none;
  transition: border-color var(--transition-fast);
  min-height: 360px;
}
.rfq__editor:focus { border-color: var(--accent); }
.rfq__editor::placeholder { color: var(--text-tertiary); }
.rfq__note { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: var(--space-3); }

@media (max-width: 768px) {
  .rfq__cols { grid-template-columns: 1fr; }
}
</style>
