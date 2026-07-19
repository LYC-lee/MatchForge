<script setup lang="ts">
import { reactive, computed, ref } from 'vue'
import type { SpecField } from '@/types/procure'
import AppButton from '@/components/ui/AppButton.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'

const props = withDefaults(defineProps<{
  spec: Record<string, SpecField>
  gating: boolean
  /** 只读展示 (#28): 历史轮次/已冻结的规格卡, 不可编辑、无确认按钮 */
  readonly?: boolean
}>(), { readonly: false })
const emit = defineEmits<{
  (e: 'confirm', spec: Record<string, SpecField>): void
  /** 返回对话补充需求（不丢弃当前轮） */
  (e: 'back'): void
}>()

// 可编辑副本(深拷贝,避免直接改 store)
const edited = reactive<Record<string, SpecField>>(
  JSON.parse(JSON.stringify(props.spec)),
)
// 原始解析值快照：字段级"恢复建议值"用
const original = JSON.parse(JSON.stringify(props.spec)) as Record<string, SpecField>

const fields = computed(() => Object.keys(edited))

const missingCount = computed(
  () => fields.value.filter((k) => edited[k].missing || !edited[k].value).length,
)
// C3: 仅当后端真给了 confidence 才参与低置信判定/展示
const hasConfidence = computed(() => fields.value.some((k) => edited[k].confidence != null))
const lowConfCount = computed(
  () =>
    fields.value.filter(
      (k) => !edited[k].missing && edited[k].confidence != null && edited[k].confidence! < 0.6 && edited[k].value,
    ).length,
)

function onInput(k: string, v: string) {
  edited[k].value = v
  edited[k].missing = !v
  // 仅已有 confidence 时保留语义,不为无 confidence 的字段虚构
  if (v && edited[k].confidence != null) edited[k].confidence = Math.max(edited[k].confidence!, 0.8)
}

/** 字段级恢复：当前值与原始解析值不同且原始有值时，可恢复为建议值 */
function canRestore(k: string): boolean {
  return !props.readonly && !!original[k]?.value && original[k].value !== edited[k].value
}
function restore(k: string) {
  edited[k].value = original[k].value
  edited[k].missing = !original[k].value
  if (original[k].confidence != null) edited[k].confidence = original[k].confidence
}

// 缺失字段时确认需二次确认（避免误放行）
const showMissingConfirm = ref(false)
function tryConfirm() {
  if (missingCount.value > 0) {
    showMissingConfirm.value = true
    return
  }
  emit('confirm', JSON.parse(JSON.stringify(edited)))
}
function confirmMissing() {
  showMissingConfirm.value = false
  emit('confirm', JSON.parse(JSON.stringify(edited)))
}
</script>

<template>
  <form class="spec" @submit.prevent="tryConfirm">
    <div v-if="missingCount || lowConfCount" class="spec__banner">
      <span class="spec__banner-icon" aria-hidden="true">⚠</span>
      <span>
        检测到 <b>{{ missingCount }}</b> 个缺失字段、<b>{{ lowConfCount }}</b> 个低置信字段,
        请核对补充后再继续。缺失与低置信字段会影响替代料匹配准确性。
      </span>
    </div>
    <table class="spec__table">
      <thead>
        <tr><th>规格字段</th><th>解析值</th><th v-if="hasConfidence">置信度</th><th>状态</th></tr>
      </thead>
      <tbody>
        <tr
          v-for="k in fields"
          :key="k"
          :class="{
            'row--missing': edited[k].missing || !edited[k].value,
            'row--low': !edited[k].missing && edited[k].confidence != null && edited[k].confidence! < 0.6 && edited[k].value,
          }"
        >
          <td class="spec__field">{{ k }}</td>
          <td>
            <div class="spec__cell">
              <input
                v-if="!props.readonly && edited[k].editable !== false"
                class="spec__input"
                :value="edited[k].value"
                :placeholder="edited[k].missing ? '待补充' : ''"
                @input="onInput(k, ($event.target as HTMLInputElement).value)"
              >
              <span v-else class="spec__static">{{ edited[k].value || '-' }}</span>
              <button
                v-if="canRestore(k)"
                type="button"
                class="spec__restore"
                title="恢复为解析建议值"
                @click="restore(k)"
              >恢复</button>
            </div>
          </td>
          <td v-if="hasConfidence" class="spec__conf">
            <template v-if="edited[k].confidence != null">
              <span v-if="!edited[k].missing && edited[k].value">
                {{ Math.round(edited[k].confidence! * 100) }}%
                <span
                  v-if="edited[k].confidence! < 0.6"
                  class="spec__qmark"
                  title="置信度较低,建议人工核对"
                >?</span>
              </span>
              <span v-else class="spec__na">-</span>
            </template>
          </td>
          <td>
            <span v-if="edited[k].missing || !edited[k].value" class="state state--warn">缺失</span>
            <span v-else-if="edited[k].confidence != null && edited[k].confidence! < 0.6" class="state state--warn">低置信</span>
            <span v-else class="state state--ok">正常</span>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-if="gating" class="spec__foot">
      <AppButton v-if="!readonly" variant="ghost" type="button" @click="emit('back')">返回修改需求</AppButton>
      <span class="spec__foot-hint">确认规格后将基于修正后的参数匹配替代料与供应商</span>
      <AppButton v-if="!readonly" type="submit">确认规格,继续寻源</AppButton>
    </div>

    <ConfirmDialog
      v-model:open="showMissingConfirm"
      title="存在缺失字段"
      description="仍有字段为空，继续匹配可能影响替代料准确性。确定继续吗？"
      confirm-text="继续寻源"
      @confirm="confirmMissing"
    />
  </form>
</template>

<style scoped>
.spec__banner {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--warning-soft);
  border: 1px solid var(--warning-border);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  color: var(--warning);
  margin-bottom: var(--space-4);
}
.spec__banner b { color: var(--warning); }
.spec__banner-icon { font-size: var(--font-size-md); }

.spec__table { width: 100%; border-collapse: collapse; }
.spec__table th {
  text-align: left;
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
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
  line-height: var(--leading-sm);
}
.row--missing td { background: var(--warning-soft); }
.row--low td { background: var(--bg-subtle); }

.spec__field { color: var(--text-secondary); font-weight: 500; }
.spec__cell {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.spec__input {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  padding: var(--space-1) var(--space-2);
  width: 100%;
  max-width: 240px;
  outline: none;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.spec__input:focus {
  border-color: var(--accent-border);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.spec__input::placeholder { color: var(--warning); }
.spec__static { color: var(--text-primary); }
.spec__restore {
  flex-shrink: 0;
  padding: var(--space-1) var(--space-2);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  color: var(--accent-text);
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  transition: color var(--transition-fast), background-color var(--transition-fast);
}
.spec__restore:hover {
  color: var(--on-accent);
  background: var(--accent);
}

.spec__conf { color: var(--text-secondary); font-family: var(--font-mono); font-size: var(--font-size-xs); }
.spec__qmark {
  display: inline-flex;
  width: var(--space-3);
  height: var(--space-3);
  align-items: center;
  justify-content: center;
  margin-left: var(--space-1);
  background: var(--warning-soft);
  color: var(--warning);
  border-radius: 50%;
  font-weight: 700;
  cursor: help;
}
.spec__na { color: var(--text-tertiary); }

.state {
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
}
.state--warn { color: var(--warning); background: var(--warning-soft); }
.state--ok { color: var(--success); background: var(--success-soft); }

.spec__foot {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-top: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-subtle);
}
.spec__foot-hint {
  flex: 1;
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  color: var(--text-tertiary);
}
</style>
