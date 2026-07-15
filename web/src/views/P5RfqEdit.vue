<template>
  <div class="page-container">
    <!-- 步骤指示器 -->
    <div class="steps">
      <div class="step done">1. 输入需求</div>
      <div class="step done">2. 规格确认</div>
      <div class="step done">3. 替代料</div>
      <div class="step done">4. 供应商</div>
      <div class="step active">5. 询价单</div>
    </div>

    <h2 class="page-title">询价单编辑</h2>

    <!-- 生成失败兜底提示 -->
    <div v-if="genError" class="alert alert-danger" style="margin-bottom: 16px">
      {{ genError }}
    </div>

    <!-- 关键字段缺失提示 -->
    <div v-if="missingFields.length > 0" class="alert alert-warning" style="margin-bottom: 16px">
      以下关键字段缺失，请补充：<strong>{{ missingFields.join('、') }}</strong>
    </div>

    <div class="two-col">
      <!-- 询价单预览 -->
      <div class="card rfq-card">
        <div class="card-header">
          询价单预览
          <span class="rfq-id">#{{ store.rfqId || '待生成' }}</span>
        </div>
        <div class="card-body">
          <textarea
            v-model="rfqText"
            class="rfq-editor"
            rows="20"
            spellcheck="false"
          />
        </div>
      </div>

      <!-- 结构化字段 -->
      <div class="card fields-card">
        <div class="card-header">询价单字段</div>
        <div class="card-body">
          <div class="field-group" v-for="field in rfqFields" :key="field.key">
            <label class="field-label" :class="{ required: field.required }">
              {{ field.label }}
              <span v-if="field.required" class="required-star">*</span>
            </label>
            <input
              v-model="rfqFieldValues[field.key]"
              class="field-input"
              :class="{ 'field-missing': field.required && !rfqFieldValues[field.key] }"
              :placeholder="field.placeholder"
              @input="rebuildRfqText"
            />
          </div>

          <div class="field-group">
            <label class="field-label">收件供应商</label>
            <div class="supplier-tags">
              <span v-for="sup in store.selectedSuppliers" :key="sup.id" class="tag tag-blue">
                {{ sup.name }}
              </span>
              <span v-if="store.selectedSuppliers.length === 0" class="no-supplier">未选择</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 操作 -->
    <div class="bottom-actions">
      <button class="btn btn-ghost" @click="$router.push('/supplier-match')">← 返回供应商</button>
      <div class="action-group">
        <button class="btn btn-secondary" @click="handleSaveDraft">保存草稿</button>
        <button class="btn btn-secondary" @click="handleCopy">复制文本</button>
        <button class="btn btn-secondary" @click="handleExport">导出</button>
        <button class="btn btn-primary" @click="handleMarkSent">标记已发送</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useProcureStore } from '@/stores/procure'
import { generateRfq } from '@/api'

const router = useRouter()
const store = useProcureStore()

const rfqText = ref('')
const genError = ref('')

const rfqFields = [
  { key: 'part_name', label: '品名', required: true, placeholder: '如 MLCC 0805 10uF X7R 50V' },
  { key: 'spec', label: '规格', required: true, placeholder: '如 0805 10uF X7R ±10% 50V' },
  { key: 'acceptable_alt', label: '可接受替代', required: false, placeholder: '替代型号及品牌' },
  { key: 'monthly_qty', label: '月用量', required: true, placeholder: '如 50000' },
  { key: 'lead_time', label: '交期', required: true, placeholder: '如 2周' },
  { key: 'target_price', label: '目标价 (可选)', required: false, placeholder: '单位含税价' },
  { key: 'request_fields', label: '请报字段', required: false, placeholder: '含税单价/交期/起订量/库存' },
]

const rfqFieldValues = reactive<Record<string, string>>({
  part_name: '',
  spec: '',
  acceptable_alt: '',
  monthly_qty: '',
  lead_time: '',
  target_price: '',
  request_fields: '含税单价/交期/起订量/库存',
})

const missingFields = computed(() =>
  rfqFields.filter((f) => f.required && !rfqFieldValues[f.key]).map((f) => f.label)
)

function buildRfqText(): string {
  const alt = store.selectedAlternative
  const altLine = alt ? `可接受替代: ${alt.part} (${alt.brand})` : ''

  return [
    `询价单 #${store.rfqId || '待生成'}`,
    `品名: ${rfqFieldValues.part_name}`,
    `规格: ${rfqFieldValues.spec}`,
    altLine,
    `月用量: ${rfqFieldValues.monthly_qty}`,
    `交期: ${rfqFieldValues.lead_time}`,
    rfqFieldValues.target_price ? `目标价: ${rfqFieldValues.target_price}` : '',
    `请报: ${rfqFieldValues.request_fields}`,
    '',
    `收件供应商: ${store.selectedSuppliers.map((s) => s.name).join('、') || '未指定'}`,
  ]
    .filter(Boolean)
    .join('\n')
}

function rebuildRfqText() {
  rfqText.value = buildRfqText()
}

function handleCopy() {
  navigator.clipboard.writeText(rfqText.value).then(() => {
    alert('已复制到剪贴板')
  })
}

function handleExport() {
  const blob = new Blob([rfqText.value], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `询价单_${store.rfqId || 'draft'}.txt`
  a.click()
  URL.revokeObjectURL(url)
}

function handleSaveDraft() {
  alert('草稿已保存')
  router.push('/history')
}

function handleMarkSent() {
  alert('已标记为发送，供应商将收到询价通知')
  router.push('/history')
}

onMounted(async () => {
  // 从 store 自动填充
  const spec = store.parsedSpec || {}
  rfqFieldValues.part_name = [spec.category, spec.package, spec.capacitance, spec.temp_coeff, spec.rated_voltage]
    .filter(Boolean)
    .join(' ')
  rfqFieldValues.spec = [
    spec.package,
    spec.capacitance,
    spec.tolerance || '±10%',
    spec.temp_coeff,
    spec.rated_voltage ? spec.rated_voltage : '',
  ]
    .filter(Boolean)
    .join(' ')
  rfqFieldValues.monthly_qty = spec.monthly_qty || ''
  rfqFieldValues.lead_time = spec.lead_time_weeks ? `${spec.lead_time_weeks}周` : ''

  if (store.selectedAlternative) {
    rfqFieldValues.acceptable_alt = `${store.selectedAlternative.part} (${store.selectedAlternative.brand})`
  }

  // 如果有后端生成的 rfqDoc，优先使用
  if (store.rfqDoc) {
    rfqText.value = store.rfqDoc
  } else {
    // 尝试调用 API 生成
    try {
      const res = await generateRfq(
        store.parsedSpec || {},
        store.alternatives,
        store.selectedSuppliers
      )
      rfqText.value = res.data.rfq_doc || buildRfqText()
    } catch {
      // 模板兜底
      genError.value = '自动生成失败，已用模板填充，请检查'
      rfqText.value = buildRfqText()
    }
  }
})
</script>

<style scoped>
.page-title {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 16px;
}

.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 20px;
}

@media (max-width: 768px) {
  .two-col {
    grid-template-columns: 1fr;
  }
}

.rfq-id {
  font-weight: 400;
  color: var(--color-text-muted);
  font-size: 13px;
}

.rfq-editor {
  width: 100%;
  padding: 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.6;
  resize: vertical;
  color: var(--color-text);
}

.rfq-editor:focus {
  outline: none;
  border-color: var(--color-primary);
}

.field-group {
  margin-bottom: 12px;
}

.field-label {
  display: block;
  margin-bottom: 4px;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-secondary);
}

.field-label.required {
  color: var(--color-text);
}

.required-star {
  color: var(--color-danger);
}

.field-input {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 13px;
  font-family: inherit;
}

.field-input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.field-missing {
  border-color: var(--color-danger);
  background: var(--color-danger-light);
}

.supplier-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.no-supplier {
  color: var(--color-text-muted);
  font-size: 13px;
}

.bottom-actions {
  display: flex;
  justify-content: space-between;
}

.action-group {
  display: flex;
  gap: 8px;
}
</style>