<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Alternative, SpecField, Supplier } from '@/types/procure'
import AppButton from '@/components/ui/AppButton.vue'
import Tag from '@/components/ui/Tag.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'

const props = defineProps<{
  rfqDoc: string
  rfqId: string | null
  spec: Record<string, SpecField> | null
  alternatives: Alternative[]
  suppliers: Supplier[]
  selectedSupplierIds: Set<string>
  sent: boolean
  streaming: boolean
  /** 纳入询价单的替代料（由 AlternativesList 勾选）；缺省时回退前 3 个非 L5 */
  selectedAlternativeParts?: Set<string>
}>()
const emit = defineEmits<{
  (e: 'update', text: string): void
  (e: 'sent'): void
  (e: 'regenerate'): void
}>()

// ── 结构化字段定义 ──
interface EditableField {
  key: string
  label: string
  required: boolean
  specKey: string
  numeric?: boolean
}

const fields: EditableField[] = [
  { key: 'part_name', label: '品名', required: true, specKey: '型号' },
  { key: 'package', label: '封装', required: true, specKey: '封装' },
  { key: 'capacitance', label: '容值', required: true, specKey: '容值' },
  { key: 'tolerance', label: '容差', required: false, specKey: '容差' },
  { key: 'temp_coeff', label: '温度系数', required: false, specKey: '温度系数' },
  { key: 'rated_voltage', label: '额定电压', required: true, specKey: '额定电压' },
  { key: 'monthly_qty', label: '月用量', required: true, specKey: '月用量', numeric: true },
  { key: 'lead_time', label: '期望交期', required: true, specKey: '交期要求' },
  { key: 'target_price', label: '目标价', required: false, specKey: '目标价', numeric: true },
]

// ── 本地字段值（结构化单一数据源）──
const fieldValues = ref<Record<string, string>>(initFieldValues())

function initFieldValues(): Record<string, string> {
  const vals: Record<string, string> = {}
  for (const f of fields) vals[f.key] = ''
  return vals
}

// 从 spec 初始化字段
watch(
  () => props.spec,
  (spec) => {
    if (!spec) return
    for (const f of fields) {
      const sv = spec[f.specKey] || spec[f.key]
      if (sv && typeof sv === 'object' && 'value' in sv) {
        fieldValues.value[f.key] = String(sv.value || '')
      } else if (sv && typeof sv === 'string') {
        fieldValues.value[f.key] = sv
      }
    }
  },
  { immediate: true },
)

// ── 从 RFQ 文本解析回填字段 ──
function parseFromText(text: string) {
  if (!text) return
  const patterns: Record<string, RegExp> = {
    part_name: /品名[：:]\s*(.+)/,
    package: /封装[：:]\s*(.+)/,
    capacitance: /(?:标称容值|容值)[：:]\s*(.+)/,
    tolerance: /容差[：:]\s*(.+)/,
    temp_coeff: /温度系数[：:]\s*(.+)/,
    rated_voltage: /额定电压[：:]\s*(.+)/,
    monthly_qty: /月用量[：:]\s*(.+)/,
    lead_time: /(?:期望交期|交期)[：:]\s*(.+)/,
    target_price: /目标价[：:]\s*(.+)/,
  }
  for (const [key, regex] of Object.entries(patterns)) {
    const match = text.match(regex)
    if (match) fieldValues.value[key] = match[1].trim()
  }
}

// ── 纳入询价单的替代料 ──
const selectedAlts = computed<Alternative[]>(() => {
  if (props.selectedAlternativeParts && props.selectedAlternativeParts.size > 0) {
    return props.alternatives.filter((a) => props.selectedAlternativeParts!.has(a.part_name || a.part || ''))
  }
  // 回退：前 3 个非 L5
  return props.alternatives.filter((a) => a.level !== 'L5').slice(0, 3)
})

// ── 从字段构建 RFQ 文本（正文派生）──
function buildRfqFromFields(): string {
  const f = (k: string) => fieldValues.value[k] || '__(待补充)__'

  const altLines = selectedAlts.value
    .map((a, i) => `${i + 1}. ${a.part_name || a.part || ''} (${a.brand || ''}) - ${a.level || ''}`)
    .join('\n') || '__(待补充)__'

  const supLines =
    props.suppliers
      .filter((s) => props.selectedSupplierIds.has(s.id))
      .slice(0, 5)
      .map((s) => s.name)
      .join(' / ') || '__(待补充)__'

  return [
    `【询价单 RFQ】`,
    `RFQ-ID: ${props.rfqId || '待生成'}`,
    `日期: ${new Date().toISOString().slice(0, 10)}`,
    ``,
    `一、品名`,
    f('part_name'),
    ``,
    `二、规格要求`,
    `- 封装: ${f('package')}`,
    `- 标称容值: ${f('capacitance')}`,
    `- 容差: ${f('tolerance')}`,
    `- 温度系数: ${f('temp_coeff')}`,
    `- 额定电压: ${f('rated_voltage')}`,
    `- 月用量: ${f('monthly_qty')}`,
    `- 期望交期: ${f('lead_time')}`,
    `${fieldValues.value.target_price ? `- 目标价: ${fieldValues.value.target_price}` : ''}`,
    ``,
    `三、可接受替代料 (仅供参考，需工程师确认)`,
    altLines,
    ``,
    `四、目标供应商`,
    supLines,
    ``,
    `五、说明`,
    `本询价单由 MatchForge AI 辅助生成，替代料仅供参考，最终可替代性须由工程师确认。`,
    `供应商回复的库存 / 交期 / 价格均以正式确认为准，本平台不承诺实时库存与报价。`,
  ]
    .filter((line) => line !== '')
    .join('\n')
}

// ── 正文来源：external(AI/恢复文本) / derived(字段派生) / manual(手改) ──
type BodySource = 'external' | 'derived' | 'manual'
const bodySource = ref<BodySource>('external')
const manualBody = ref('')

const displayBody = computed(() => {
  if (bodySource.value === 'manual') return manualBody.value
  if (bodySource.value === 'derived') return buildRfqFromFields()
  return props.rfqDoc
})

// 正文变化 -> 推回 store（带回声守卫，避免与 props.rfqDoc 循环）
let lastEmitted = ''
watch(
  displayBody,
  (text) => {
    if (text === lastEmitted) return
    lastEmitted = text
    emit('update', text)
  },
)

// ── 字段编辑：手改正文在场时二次确认 ──
const showOverwriteConfirm = ref(false)

function onFieldInput(key: string, val: string) {
  fieldValues.value[key] = val
  if (bodySource.value === 'manual') {
    // 正文已被手改：让用户选 保留手改 / 重新生成
    showOverwriteConfirm.value = true
  } else {
    bodySource.value = 'derived'
  }
}
function confirmRegenerate() {
  bodySource.value = 'derived'
  showOverwriteConfirm.value = false
}
function keepManual() {
  // 字段值已更新并保留；正文维持手改
  showOverwriteConfirm.value = false
}

// ── 手动编辑正文 ──
function onTextInput(e: Event) {
  manualBody.value = (e.target as HTMLTextAreaElement).value
  bodySource.value = 'manual'
}

// ── 外部 rfqDoc：AI 流式完成 / 会话恢复时回填字段、正文回到 external ──
watch(
  () => props.rfqDoc,
  (newDoc) => {
    if (bodySource.value === 'manual') return  // 不覆盖手改
    if (props.streaming) return  // 流式期间由 streaming watcher 收尾
    if (newDoc === lastEmitted) return  // 自己回声
    if (newDoc) parseFromText(newDoc)
    bodySource.value = 'external'
  },
)

watch(
  () => props.streaming,
  (s) => {
    if (s) {
      // 流式开始：展示 AI 文本，清掉派生/手改状态
      bodySource.value = 'external'
      manualBody.value = ''
    } else if (props.rfqDoc && bodySource.value !== 'manual') {
      // 流式结束：回填字段，正文回到 external（展示 AI 最终文本）
      parseFromText(props.rfqDoc)
      bodySource.value = 'external'
    }
  },
)

// ── 计算属性 ──
const selectedSuppliers = computed(() =>
  props.suppliers.filter((s) => props.selectedSupplierIds.has(s.id)),
)

const missingFields = computed(() => {
  const miss: string[] = []
  if (!fieldValues.value['monthly_qty']) miss.push('月用量')
  if (!fieldValues.value['lead_time']) miss.push('期望交期')
  if (!selectedSuppliers.value.length) miss.push('目标供应商')
  return miss
})

const isFallback = computed(
  () => props.rfqDoc.includes('__(待补充)__') || props.rfqDoc.includes('待补充'),
)

const bodyDirty = computed(() => bodySource.value === 'manual')

// ── 操作 ──
const copied = ref(false)
async function copy() {
  try {
    await navigator.clipboard.writeText(displayBody.value)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {
    /* 静默 */
  }
}

function exportFile() {
  const blob = new Blob([displayBody.value], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `询价单_${props.rfqId || 'draft'}.txt`
  a.click()
  URL.revokeObjectURL(url)
}

function parseFromTextManual() {
  parseFromText(displayBody.value)
  bodySource.value = 'derived'
}
</script>

<template>
  <div class="rfq">
    <!-- 缺失字段警告 -->
    <div v-if="missingFields.length && !streaming" class="rfq__warn" role="alert">
      <span class="rfq__warn-icon" aria-hidden="true">⚠</span>
      <span>
        关键字段缺失:
        <b v-for="f in missingFields" :key="f" class="rfq__warn-field">{{ f }}</b>
        将影响询价有效性，请补充。
      </span>
    </div>

    <!-- 流式生成中 -->
    <div v-if="streaming" class="rfq__streaming-bar">
      <span class="rfq__streaming-spinner" />
      <span>AI 正在生成询价单…</span>
    </div>

    <div class="rfq__cols">
      <!-- 左侧：结构化字段面板 -->
      <aside class="rfq__side">
        <h4 class="rfq__side-title">结构化字段</h4>

        <div class="rfq__field-list">
          <div v-for="f in fields" :key="f.key" class="rfq__field-row">
            <label class="rfq__field-label" :class="{ required: f.required }">
              {{ f.label }}
              <span v-if="f.required" class="rfq__required">*</span>
            </label>
            <input
              :value="fieldValues[f.key]"
              class="rfq__field-input"
              :class="{ 'is-missing': f.required && !fieldValues[f.key], 'num': f.numeric }"
              :placeholder="f.required ? '必填' : '可选'"
              :disabled="streaming"
              @input="onFieldInput(f.key, ($event.target as HTMLInputElement).value)"
            >
          </div>
        </div>

        <!-- 替代料摘要 -->
        <div class="rfq__side-block">
          <h5>纳入询价单的替代料 ({{ selectedAlts.length }})</h5>
          <ul class="rfq__alt-list">
            <li v-for="a in selectedAlts" :key="a.part_name || a.part">
              <span class="mono">{{ a.part_name || a.part }}</span>
              <span class="rfq__alt-brand">{{ a.brand }}</span>
              <Tag type="neutral" :value="a.level || ''" />
            </li>
            <li v-if="!selectedAlts.length" class="rfq__empty-inline">
              暂无（在替代料卡勾选「纳入询价单」）
            </li>
          </ul>
        </div>

        <!-- 目标供应商 -->
        <div class="rfq__side-block">
          <h5>目标供应商 ({{ selectedSuppliers.length }})</h5>
          <ul class="rfq__sup-list">
            <li v-for="s in selectedSuppliers" :key="s.id">
              <span>{{ s.name }}</span>
              <span class="rfq__sup-score num" :class="s.match_score >= 0.8 ? 'high' : s.match_score >= 0.65 ? 'mid' : 'low'">
                {{ Math.round(s.match_score * 100) }}%
              </span>
            </li>
            <li v-if="!selectedSuppliers.length" class="rfq__empty-inline">未选择</li>
          </ul>
        </div>

        <div class="rfq__side-actions">
          <AppButton variant="ghost" size="sm" :disabled="streaming" @click="parseFromTextManual">
            从正文回填字段
          </AppButton>
          <AppButton variant="ghost" size="sm" :disabled="streaming" @click="emit('regenerate')">
            AI 重新生成
          </AppButton>
        </div>
      </aside>

      <!-- 右侧：询价单预览/编辑 -->
      <div class="rfq__main">
        <div class="rfq__toolbar">
          <div class="rfq__id">
            <span v-if="rfqId" class="mono">{{ rfqId }}</span>
            <span v-if="streaming" class="rfq__streaming-tag">生成中…</span>
            <span v-else-if="bodyDirty" class="rfq__dirty-tag">已手动修改</span>
            <span v-else-if="isFallback" class="rfq__fallback-tag">模板兜底</span>
            <span v-else-if="rfqDoc" class="rfq__ready-tag">AI 已生成</span>
          </div>
          <div class="rfq__tools">
            <AppButton variant="ghost" size="sm" :disabled="streaming || !displayBody" @click="copy">
              {{ copied ? '已复制 ✓' : '复制' }}
            </AppButton>
            <AppButton variant="ghost" size="sm" :disabled="streaming || !displayBody" @click="exportFile">
              导出
            </AppButton>
            <AppButton
              variant="secondary"
              size="sm"
              :disabled="streaming || !displayBody"
              @click="emit('sent')"
            >
              {{ sent ? '已发送 ✓' : '标记已发送' }}
            </AppButton>
          </div>
        </div>

        <textarea
          class="rfq__editor"
          :value="displayBody"
          :placeholder="streaming ? 'AI 正在生成询价单…' : '询价单内容（AI 自动生成，可编辑）'"
          :readonly="streaming"
          @input="onTextInput"
        />

        <p class="rfq__note">
          本询价单由 AI 辅助生成，替代料仅供参考，最终可替代性须由工程师确认。
          供应商回复的库存 / 交期 / 价格以正式确认为准。
        </p>
      </div>
    </div>

    <ConfirmDialog
      v-model:open="showOverwriteConfirm"
      title="正文已被手动修改"
      description="你修改了询价单正文，现在又编辑了结构化字段。要保留手改的正文，还是用字段重新生成？"
      confirm-text="重新生成"
      cancel-text="保留手改"
      @confirm="confirmRegenerate"
      @cancel="keepManual"
    />
  </div>
</template>

<style scoped>
/* 警告 */
.rfq__warn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--danger-soft);
  border: 1px solid var(--danger-border);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  color: var(--danger);
  margin-bottom: var(--space-4);
}
.rfq__warn-icon { font-size: var(--font-size-md); flex-shrink: 0; }
.rfq__warn-field {
  margin: 0 var(--space-1);
  padding: var(--space-1) var(--space-2);
  background: var(--danger-soft);
  border: 1px solid var(--danger-border);
  border-radius: var(--radius-sm);
}

/* 流式进度条 */
.rfq__streaming-bar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--bg-subtle);
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-md);
  color: var(--accent-text);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  margin-bottom: var(--space-4);
}
.rfq__streaming-spinner {
  width: var(--space-4);
  height: var(--space-4);
  border: 2px solid var(--accent-soft);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* 双栏布局 */
.rfq__cols { display: grid; grid-template-columns: 300px 1fr; gap: var(--space-5); }

/* 左侧面板 */
.rfq__side {
  background: var(--bg-subtle);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  align-self: start;
  max-height: calc(100vh - 200px);
  overflow-y: auto;
}
.rfq__side-title {
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: var(--space-3);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.rfq__field-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.rfq__field-row {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.rfq__field-label {
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  color: var(--text-tertiary);
  font-weight: 500;
}
.rfq__field-label.required { color: var(--text-secondary); }
.rfq__required { color: var(--danger); margin-left: var(--space-1); }
.rfq__field-input {
  width: 100%;
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  font-family: var(--font-mono);
  outline: none;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.rfq__field-input:focus {
  border-color: var(--accent-border);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.rfq__field-input.is-missing {
  border-color: var(--danger-border);
  background: var(--danger-soft);
}
.rfq__field-input::placeholder { color: var(--text-tertiary); }

/* 替代料/供应商摘要 */
.rfq__side-block {
  margin-top: var(--space-4);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}
.rfq__side-block h5 {
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  color: var(--text-tertiary);
  margin-bottom: var(--space-2);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.rfq__alt-list,
.rfq__sup-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.rfq__alt-list li,
.rfq__sup-list li {
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  color: var(--text-secondary);
  padding: var(--space-1) 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-2);
}
.rfq__alt-brand { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.rfq__sup-score {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  font-weight: 600;
}
.rfq__sup-score.high { color: var(--success); }
.rfq__sup-score.mid { color: var(--warning); }
.rfq__sup-score.low { color: var(--text-tertiary); }
.rfq__empty-inline { color: var(--text-tertiary); font-style: italic; }

/* 左侧操作按钮 */
.rfq__side-actions {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-top: var(--space-4);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}

/* 右侧主区域 */
.rfq__main { display: flex; flex-direction: column; min-height: 480px; }
.rfq__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-2);
}
.rfq__id {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  color: var(--text-tertiary);
}
.rfq__streaming-tag { color: var(--accent-text); font-weight: 600; }
.rfq__dirty-tag {
  color: var(--notice);
  background: var(--notice-soft);
  border: 1px solid var(--notice-border);
  border-radius: var(--radius-sm);
  padding: var(--space-1) var(--space-2);
}
.rfq__fallback-tag {
  color: var(--warning);
  background: var(--warning-soft);
  border: 1px solid var(--warning-border);
  border-radius: var(--radius-sm);
  padding: var(--space-1) var(--space-2);
}
.rfq__ready-tag {
  color: var(--success);
  background: var(--success-soft);
  border: 1px solid var(--success-border);
  border-radius: var(--radius-sm);
  padding: var(--space-1) var(--space-2);
}
.rfq__tools { display: flex; gap: var(--space-2); }

/* 编辑器 */
.rfq__editor {
  flex: 1;
  width: 100%;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  color: var(--text-primary);
  resize: vertical;
  outline: none;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  min-height: 420px;
  tab-size: 2;
}
.rfq__editor:focus {
  border-color: var(--accent-border);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.rfq__editor::placeholder { color: var(--text-tertiary); }
.rfq__note {
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  color: var(--text-tertiary);
  margin-top: var(--space-3);
}
.mono { font-family: var(--font-mono); }

@media (max-width: 768px) {
  .rfq__cols { grid-template-columns: 1fr; }
  .rfq__side { max-height: none; }
}
</style>
