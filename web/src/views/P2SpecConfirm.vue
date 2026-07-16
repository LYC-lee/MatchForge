<template>
  <div class="page-container">
    <!-- 步骤指示器 -->
    <div class="steps">
      <div class="step done">1. 输入需求</div>
      <div class="step active">2. 规格确认</div>
      <div class="step">3. 替代料</div>
      <div class="step">4. 供应商</div>
      <div class="step">5. 询价单</div>
    </div>

    <h2 class="page-title">规格确认</h2>
    <p class="page-desc">请核对 AI 解析的规格，补全缺失字段后查找替代料</p>

    <!-- 原始需求回显 -->
    <div class="card raw-query-card">
      <div class="card-body">
        <span class="label">原始需求：</span>
        <span>{{ store.rawQuery }}</span>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="!store.parsedSpec && !hasError" class="card loading-card">
      <div class="card-body empty-state">
        <div class="loading-spinner" style="margin: 0 auto 12px" />
        <p>正在识别型号与参数…</p>
      </div>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="hasError" class="card error-card">
      <div class="card-body">
        <div class="alert alert-danger">
          <p><strong>未识别到有效型号</strong></p>
          <p class="error-hint">请手动填写以下规格，或返回修改需求描述</p>
        </div>
        <button class="btn btn-secondary" @click="$router.push('/')">返回修改</button>
      </div>
    </div>

    <!-- 规格表 -->
    <div v-else class="card spec-card">
      <div class="card-header">解析规格</div>
      <div class="card-body">
        <table class="table">
          <thead>
            <tr>
              <th>参数</th>
              <th>值</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="field in specFields" :key="field.key">
              <td class="field-label">{{ field.label }}</td>
              <td>
                <input
                  v-model="localSpec[field.key]"
                  class="field-input"
                  :class="{
                    'field-missing': !localSpec[field.key],
                    'field-low-conf': !missingFields.includes(field.key) && field.confidence === 'low',
                  }"
                  :placeholder="field.placeholder"
                />
              </td>
              <td>
                <span v-if="!localSpec[field.key]" class="tag tag-yellow">缺失</span>
                <span
                  v-else-if="field.confidence === 'low'"
                  class="tag tag-yellow tooltip"
                  title="此参数为推断，请核对"
                >
                  低置信 ?
                </span>
                <span v-else class="tag tag-green">已识别</span>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- 缺失提示 -->
        <div v-if="missingFields.length > 0" class="alert alert-warning" style="margin-top: 12px">
          <strong>提示：</strong>标黄字段为缺失项，请尽量补全以获得更准确的替代料推荐。
        </div>
      </div>

      <div class="card-footer">
        <button class="btn btn-ghost" @click="handleReParse">重新解析</button>
        <button class="btn btn-secondary" @click="$router.push('/')">返回修改</button>
        <button
          class="btn btn-primary"
          :disabled="criticalFieldsMissing"
          @click="handleFindAlternatives"
        >
          查找替代料
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useProcureStore } from '@/stores/procure'

const router = useRouter()
const store = useProcureStore()

const specFields = [
  { key: 'part_number', label: '型号', placeholder: '如 TMK212BJ105KG-T', confidence: 'high' },
  { key: 'brand', label: '品牌', placeholder: '如 Taiyo Yuden', confidence: 'high' },
  { key: 'category', label: '品类', placeholder: '如 MLCC', confidence: 'high' },
  { key: 'package', label: '封装', placeholder: '如 0805', confidence: 'high' },
  { key: 'capacitance', label: '容值', placeholder: '如 10uF', confidence: 'high' },
  { key: 'tolerance', label: '容差', placeholder: '如 ±10%', confidence: 'high' },
  { key: 'temp_coeff', label: '温度系数', placeholder: '如 X7R', confidence: 'high' },
  { key: 'rated_voltage', label: '额定电压', placeholder: '如 50V', confidence: 'high' },
  { key: 'temp_range', label: '温度范围', placeholder: '如 -55~125℃', confidence: 'low' },
  { key: 'lifecycle', label: '生命周期', placeholder: '如 量产', confidence: 'low' },
  { key: 'monthly_qty', label: '月用量', placeholder: '如 50000', confidence: 'low' },
  { key: 'lead_time_weeks', label: '交期(周)', placeholder: '如 2', confidence: 'low' },
]

const localSpec = reactive<Record<string, string>>({})

// 初始化本地规格
watch(
  () => store.parsedSpec,
  (spec) => {
    if (spec) {
      specFields.forEach((f) => {
        localSpec[f.key] = spec[f.key] || ''
      })
    }
  },
  { immediate: true }
)

const hasError = computed(() => store.errors.length > 0 && !store.parsedSpec)

const missingFields = computed(() =>
  specFields.filter((f) => !localSpec[f.key]).map((f) => f.key)
)

// 关键字段缺失阻止下一步
const criticalFields = ['package', 'capacitance', 'rated_voltage']
const criticalFieldsMissing = computed(() =>
  criticalFields.some((k) => !localSpec[k])
)

function handleReParse() {
  store.parsedSpec = null
  store.errors = []
  router.push('/')
}

function handleFindAlternatives() {
  // 将本地编辑的规格写回 store
  store.parsedSpec = { ...localSpec }
  router.push('/alternatives')
}
</script>

<style scoped>
.page-title {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 4px;
}

.page-desc {
  color: var(--color-text-secondary);
  margin-bottom: 20px;
}

.raw-query-card {
  margin-bottom: 16px;
}

.raw-query-card .label {
  color: var(--color-text-secondary);
  font-size: 13px;
}

.spec-card {
  margin-bottom: 20px;
}

.field-label {
  font-weight: 500;
  width: 120px;
  white-space: nowrap;
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
  border-color: var(--color-warning);
  background: var(--color-warning-light);
}

.field-low-conf {
  border-color: var(--color-warning);
}

.card-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid var(--color-border);
}

.error-hint {
  margin-top: 4px;
  font-size: 13px;
}

.loading-card {
  margin-bottom: 20px;
}
</style>