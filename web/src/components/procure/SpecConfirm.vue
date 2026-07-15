<script setup lang="ts">
import { reactive, computed } from 'vue'
import type { SpecField } from '@/types/procure'
import AppButton from '@/components/ui/AppButton.vue'

const props = defineProps<{
  spec: Record<string, SpecField>
  gating: boolean
}>()
const emit = defineEmits<{ (e: 'confirm', spec: Record<string, SpecField>): void }>()

// 可编辑副本(深拷贝,避免直接改 store)
const edited = reactive<Record<string, SpecField>>(
  JSON.parse(JSON.stringify(props.spec)),
)

const fields = computed(() => Object.keys(edited))

const missingCount = computed(
  () => fields.value.filter((k) => edited[k].missing || !edited[k].value).length,
)
const lowConfCount = computed(
  () => fields.value.filter((k) => !edited[k].missing && edited[k].confidence < 0.6 && edited[k].value).length,
)

function onInput(k: string, v: string) {
  edited[k].value = v
  edited[k].missing = !v
  if (v) edited[k].confidence = Math.max(edited[k].confidence, 0.8)
}

function confirm() {
  emit('confirm', JSON.parse(JSON.stringify(edited)))
}
</script>

<template>
  <div class="spec">
    <div v-if="missingCount || lowConfCount" class="spec__banner">
      <span class="spec__banner-icon">⚠</span>
      <span>
        检测到 <b>{{ missingCount }}</b> 个缺失字段、<b>{{ lowConfCount }}</b> 个低置信字段,
        请核对补充后再继续。缺失与低置信字段会影响替代料匹配准确性。
      </span>
    </div>
    <table class="spec__table">
      <thead>
        <tr><th>规格字段</th><th>解析值</th><th>置信度</th><th>状态</th></tr>
      </thead>
      <tbody>
        <tr
          v-for="k in fields"
          :key="k"
          :class="{
            'row--missing': edited[k].missing || !edited[k].value,
            'row--low': !edited[k].missing && edited[k].confidence < 0.6 && edited[k].value,
          }"
        >
          <td class="spec__field">{{ k }}</td>
          <td>
            <input
              v-if="edited[k].editable !== false"
              class="spec__input"
              :value="edited[k].value"
              :placeholder="edited[k].missing ? '待补充' : ''"
              @input="onInput(k, ($event.target as HTMLInputElement).value)"
            />
            <span v-else class="spec__static">{{ edited[k].value || '—' }}</span>
          </td>
          <td class="spec__conf">
            <span v-if="!edited[k].missing && edited[k].value">
              {{ Math.round(edited[k].confidence * 100) }}%
              <span
                v-if="edited[k].confidence < 0.6"
                class="spec__qmark"
                title="置信度较低,建议人工核对"
              >?</span>
            </span>
            <span v-else class="spec__na">—</span>
          </td>
          <td>
            <span v-if="edited[k].missing || !edited[k].value" class="state state--warn">缺失</span>
            <span v-else-if="edited[k].confidence < 0.6" class="state state--warn">低置信</span>
            <span v-else class="state state--ok">正常</span>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-if="gating" class="spec__foot">
      <span class="spec__foot-hint">确认规格后将基于修正后的参数匹配替代料与供应商</span>
      <AppButton size="md" @click="confirm">确认规格,继续寻源</AppButton>
    </div>
  </div>
</template>

<style scoped>
.spec__banner {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--warning-soft);
  border: 1px solid rgba(234, 179, 8, 0.3);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  color: var(--warning);
  margin-bottom: var(--space-4);
}
.spec__banner b { color: var(--warning); }
.spec__banner-icon { font-size: 16px; }

.spec__table { width: 100%; border-collapse: collapse; }
.spec__table th {
  text-align: left;
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--text-tertiary);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-default);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.spec__table td {
  padding: var(--space-3);
  border-bottom: 1px solid var(--border-subtle);
  font-size: var(--font-size-sm);
}
.row--missing td { background: rgba(234, 179, 8, 0.05); }
.row--low td { background: rgba(234, 179, 8, 0.03); }

.spec__field { color: var(--text-secondary); font-weight: 500; }
.spec__input {
  background: var(--bg-3);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  padding: 5px 8px;
  width: 100%;
  max-width: 240px;
  outline: none;
  transition: border-color var(--transition-fast);
}
.spec__input:focus { border-color: var(--accent); }
.spec__input::placeholder { color: var(--warning); }
.spec__static { color: var(--text-primary); }

.spec__conf { color: var(--text-secondary); font-family: var(--font-mono); font-size: var(--font-size-xs); }
.spec__qmark {
  display: inline-flex;
  width: 14px; height: 14px;
  align-items: center; justify-content: center;
  margin-left: 4px;
  background: var(--warning-soft);
  color: var(--warning);
  border-radius: 50%;
  font-weight: 700;
  cursor: help;
}
.spec__na { color: var(--text-tertiary); }

.state { font-size: var(--font-size-xs); padding: 2px 8px; border-radius: var(--radius-sm); }
.state--warn { color: var(--warning); background: var(--warning-soft); }
.state--ok { color: var(--success); background: var(--success-soft); }

.spec__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  margin-top: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-subtle);
}
.spec__foot-hint { font-size: var(--font-size-sm); color: var(--text-tertiary); }
</style>
