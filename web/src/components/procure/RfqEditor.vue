<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Alternative, SpecField, Supplier } from '@/types/procure'
import AppButton from '@/components/ui/AppButton.vue'
import Tag from '@/components/ui/Tag.vue'

const props = defineProps<{
  rfqDoc: string
  rfqId: string | null
  spec: Record<string, SpecField> | null
  alternatives: Alternative[]
  suppliers: Supplier[]
  selectedSupplierIds: Set<string>
  sent: boolean
  streaming: boolean
  /** 落库后的真实 RFQ 编号 (RFQ-YYYY-NNNN); 优先于内存 rfqId 展示 */
  persistedRfqNumber?: string | null
  /** 发送到后端的进行中状态 */
  sending?: boolean
  /** 发送到后端的错误信息 (显式出口) */
  sendError?: string | null
  /** demo 沙盘模式: 仅本地标记, 不调后端 */
  isDemo?: boolean
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
}

const fields: EditableField[] = [
  { key: 'part_name', label: '品名', required: true, specKey: '型号' },
  { key: 'package', label: '封装', required: true, specKey: '封装' },
  { key: 'capacitance', label: '容值', required: true, specKey: '容值' },
  { key: 'tolerance', label: '容差', required: false, specKey: '容差' },
  { key: 'temp_coeff', label: '温度系数', required: false, specKey: '温度系数' },
  { key: 'rated_voltage', label: '额定电压', required: true, specKey: '额定电压' },
  { key: 'monthly_qty', label: '月用量', required: true, specKey: '月用量' },
  { key: 'lead_time', label: '期望交期', required: true, specKey: '交期要求' },
  { key: 'target_price', label: '目标价', required: false, specKey: '目标价' },
]

// ── 本地字段值 ──
const fieldValues = ref<Record<string, string>>(initFieldValues())

function initFieldValues(): Record<string, string> {
  const vals: Record<string, string> = {}
  for (const f of fields) {
    vals[f.key] = ''
  }
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

// ── 从 RFQ 文本解析回填字段 (单向: 文本 → 字段) ──
function parseFromText() {
  const text = props.rfqDoc
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
    if (match) {
      fieldValues.value[key] = match[1].trim()
    }
  }
}

// ── 从字段构建 RFQ 文本 ──
function buildRfqFromFields(): string {
  const f = (k: string) => fieldValues.value[k] || '__(待补充)__'

  const altLines = props.alternatives
    .filter((a) => a.level !== 'L5')
    .slice(0, 3)
    .map(
      (a, i) =>
        `${i + 1}. ${a.part_name || a.part || ''} (${a.brand || ''}) — ${a.level || ''}`,
    )
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
    `多层陶瓷贴片电容 (MLCC)`,
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

// 字段 → 文本 (字段变化时自动重建)
let syncFromFields = true
watch(
  fieldValues,
  () => {
    if (!syncFromFields) return
    emit('update', buildRfqFromFields())
  },
  { deep: true },
)

// 当外部 rfqDoc 更新时 (如 SSE 流式推送), 暂停字段→文本同步
watch(
  () => props.rfqDoc,
  (newDoc) => {
    if (newDoc && newDoc !== buildRfqFromFields()) {
      syncFromFields = false
      setTimeout(() => {
        syncFromFields = true
      }, 100)
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

const localRfqText = ref('')
watch(
  () => props.rfqDoc,
  (doc) => {
    localRfqText.value = doc
  },
  { immediate: true },
)

function onTextInput(e: Event) {
  const text = (e.target as HTMLTextAreaElement).value
  localRfqText.value = text
  emit('update', text)
}

// ── 操作 ──
const copied = ref(false)
async function copy() {
  try {
    await navigator.clipboard.writeText(props.rfqDoc)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch {
    // 静默
  }
}

function exportFile() {
  const blob = new Blob([props.rfqDoc], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `询价单_${props.rfqId || 'draft'}.txt`
  a.click()
  URL.revokeObjectURL(url)
}

// ── 展示用 RFQ 标识: 落库后优先真实编号, 否则用内存临时 ID ──
const displayRfqId = computed(() => props.persistedRfqNumber || props.rfqId)
const sendBtnText = computed(() => {
  if (props.isDemo) return props.sent ? '已标记已发送 ✓' : '标记已发送'
  if (props.sending) return '发送中…'
  return props.sent ? '已发送 ✓' : '发送 RFQ'
})
</script>

<template>
  <div class="rfq">
    <!-- 缺失字段警告 -->
    <div v-if="missingFields.length && !streaming" class="rfq__warn">
      <span class="rfq__warn-icon">⚠</span>
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
              v-model="fieldValues[f.key]"
              class="rfq__field-input"
              :class="{ 'is-missing': f.required && !fieldValues[f.key] }"
              :placeholder="f.required ? '必填' : '可选'"
              :disabled="streaming"
            />
          </div>
        </div>

        <!-- 替代料摘要 -->
        <div class="rfq__side-block">
          <h5>可接受替代料 ({{ alternatives.filter((a) => a.level !== 'L5').length }})</h5>
          <ul class="rfq__alt-list">
            <li v-for="a in alternatives.filter((a) => a.level !== 'L5')" :key="a.part_name || a.part">
              <span class="mono">{{ a.part_name || a.part }}</span>
              <span class="rfq__alt-brand">{{ a.brand }}</span>
              <Tag type="neutral" :value="a.level || ''" />
            </li>
            <li v-if="!alternatives.filter((a) => a.level !== 'L5').length" class="rfq__empty-inline">
              暂无
            </li>
          </ul>
        </div>

        <!-- 目标供应商 -->
        <div class="rfq__side-block">
          <h5>目标供应商 ({{ selectedSuppliers.length }})</h5>
          <ul class="rfq__sup-list">
            <li v-for="s in selectedSuppliers" :key="s.id">
              <span>{{ s.name }}</span>
              <span class="rfq__sup-score" :class="s.match_score >= 0.8 ? 'high' : s.match_score >= 0.65 ? 'mid' : 'low'">
                {{ Math.round(s.match_score * 100) }}%
              </span>
            </li>
            <li v-if="!selectedSuppliers.length" class="rfq__empty-inline">未选择</li>
          </ul>
        </div>

        <div class="rfq__side-actions">
          <AppButton variant="ghost" size="sm" :disabled="streaming" @click="parseFromText">
            从文本回填字段
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
            <span v-if="displayRfqId" class="mono">{{ displayRfqId }}</span>
            <span v-if="streaming" class="rfq__streaming-tag">生成中…</span>
            <span v-else-if="isFallback" class="rfq__fallback-tag">模板兜底</span>
            <span v-else-if="rfqDoc" class="rfq__ready-tag">AI 已生成</span>
          </div>
          <div class="rfq__tools">
            <AppButton variant="ghost" size="sm" :disabled="streaming || !rfqDoc" @click="copy">
              {{ copied ? '已复制 ✓' : '复制' }}
            </AppButton>
            <AppButton variant="ghost" size="sm" :disabled="streaming || !rfqDoc" @click="exportFile">
              导出
            </AppButton>
            <AppButton
              variant="secondary"
              size="sm"
              :disabled="streaming || !rfqDoc || sending || sent"
              @click="emit('sent')"
            >
              {{ sendBtnText }}
            </AppButton>
          </div>
        </div>

        <!-- 发送错误出口 (不静默) -->
        <div v-if="sendError" class="rfq__send-error">
          <span class="rfq__send-error-icon">⚠</span>
          <span>{{ sendError }}</span>
        </div>

        <textarea
          class="rfq__editor"
          :value="localRfqText"
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
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  color: var(--danger);
  margin-bottom: var(--space-4);
}
.rfq__warn-icon { font-size: 16px; flex-shrink: 0; }
.rfq__warn-field { margin: 0 4px; padding: 1px 6px; background: rgba(239, 68, 68, 0.2); border-radius: var(--radius-sm); }

/* 流式进度条 */
.rfq__streaming-bar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--bg-2);
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-md);
  color: var(--accent-hover);
  font-size: var(--font-size-sm);
  margin-bottom: var(--space-4);
}
.rfq__streaming-spinner {
  width: 18px;
  height: 18px;
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
  background: var(--bg-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  align-self: start;
  max-height: calc(100vh - 200px);
  overflow-y: auto;
}
.rfq__side-title {
  font-size: var(--font-size-sm);
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
  gap: 4px;
}
.rfq__field-label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  font-weight: 500;
}
.rfq__field-label.required { color: var(--text-secondary); }
.rfq__required { color: var(--danger); margin-left: 2px; }
.rfq__field-input {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  background: var(--bg-2);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  font-family: var(--font-mono);
  outline: none;
  transition: border-color var(--transition-fast);
}
.rfq__field-input:focus { border-color: var(--accent); }
.rfq__field-input.is-missing {
  border-color: var(--danger);
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
  color: var(--text-secondary);
  padding: 4px 0;
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
  color: var(--text-tertiary);
}
.rfq__streaming-tag { color: var(--accent-hover); font-weight: 600; }
.rfq__fallback-tag { color: var(--warning); }
.rfq__ready-tag { color: var(--success); }
.rfq__tools { display: flex; gap: var(--space-2); }

/* 发送错误出口 */
.rfq__send-error {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  margin-bottom: var(--space-2);
  background: var(--danger-soft, #fef2f2);
  border: 1px solid var(--danger, #dc2626);
  border-radius: var(--radius-sm, 4px);
  color: var(--danger, #dc2626);
  font-size: var(--font-size-sm);
}
.rfq__send-error-icon { font-weight: 700; }

/* 编辑器 */
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
  min-height: 420px;
  tab-size: 2;
}
.rfq__editor:focus { border-color: var(--accent); }
.rfq__editor::placeholder { color: var(--text-tertiary); }
.rfq__note {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin-top: var(--space-3);
}
.mono { font-family: var(--font-mono); }

@media (max-width: 768px) {
  .rfq__cols { grid-template-columns: 1fr; }
  .rfq__side { max-height: none; }
}
</style>