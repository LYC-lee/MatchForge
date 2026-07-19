<script setup lang="ts">
/**
 * 共享对话输入区（ChatView / CompanyChat / CompanyAssistant 统一接入）。
 *
 * 能力：
 * - IME 安全：compositionstart/end 期间 Enter 不发送（中文输入法选词回车不误发）
 * - textarea 自动增高，上限约 6 行；Shift+Enter 换行；Enter 发送
 * - 发送/停止双态按钮：busy 时显示停止（中断流式/渐进展示）
 * - Kimi 式「+」总入口：#menu 插槽聚合各页现有能力（示例/模板/模式切换），
 *   插槽为空时不渲染「+」按钮
 *
 * #menu 插槽约定：条目用 <button class="chat-menu-item">，分组标题用 <p class="chat-menu-title">，
 * 菜单内任意点击后自动关闭。
 */
import { computed, nextTick, onMounted, onUnmounted, ref, useSlots, watch } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'

const props = withDefaults(
  defineProps<{
    modelValue: string
    /** 生成中：显示停止按钮 */
    busy?: boolean
    /** 额外禁用（如未选择协同对象）：输入与发送都不可用 */
    disabled?: boolean
    placeholder?: string
    /** 「+」按钮的无障碍标签 */
    menuLabel?: string
  }>(),
  {
    busy: false,
    disabled: false,
    placeholder: '输入消息…',
    menuLabel: '更多操作',
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'send'): void
  (e: 'stop'): void
}>()

const slots = useSlots()
const hasMenu = computed(() => !!slots.menu)

const root = ref<HTMLElement | null>(null)
const textarea = ref<HTMLTextAreaElement | null>(null)
const isComposing = ref(false)
const menuOpen = ref(false)

const canSend = computed(() => !props.busy && !props.disabled && !!props.modelValue.trim())

// ── 自动增高（CSS max-height 封顶约 6 行，超出后内部滚动）──
function autoGrow() {
  const el = textarea.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${el.scrollHeight}px`
}
watch(
  () => props.modelValue,
  () => nextTick(autoGrow),
)
onMounted(autoGrow)

function onInput(e: Event) {
  emit('update:modelValue', (e.target as HTMLTextAreaElement).value)
}

// ── 发送：Enter（IME 组合中除外）──
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && !isComposing.value && !e.isComposing) {
    e.preventDefault()
    trySend()
  }
}
function trySend() {
  if (!canSend.value) return
  emit('send')
}
function onStop() {
  emit('stop')
}

// ── 「+」菜单：点击外部 / Esc 关闭；菜单内任意点击后关闭 ──
function onDocClick(e: MouseEvent) {
  if (root.value && !root.value.contains(e.target as Node)) menuOpen.value = false
}
function onDocKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') menuOpen.value = false
}
onMounted(() => {
  document.addEventListener('click', onDocClick)
  document.addEventListener('keydown', onDocKeydown)
})
onUnmounted(() => {
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onDocKeydown)
})

defineExpose({
  focus: () => textarea.value?.focus(),
})
</script>

<template>
  <div ref="root" class="chat-input">
    <div class="chat-input__wrap">
      <div v-if="hasMenu" class="chat-input__plus">
        <button
          type="button"
          class="chat-input__plus-btn"
          :class="{ 'chat-input__plus-btn--open': menuOpen }"
          :aria-expanded="menuOpen"
          aria-haspopup="menu"
          :aria-label="menuLabel"
          @click.stop="menuOpen = !menuOpen"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
            <path d="M12 5v14M5 12h14" />
          </svg>
        </button>
        <div v-if="menuOpen" class="chat-input__menu" role="menu" @click="menuOpen = false">
          <slot name="menu" />
        </div>
      </div>

      <textarea
        ref="textarea"
        class="chat-input__field"
        :value="modelValue"
        rows="1"
        :placeholder="placeholder"
        :disabled="disabled"
        @input="onInput"
        @keydown="onKeydown"
        @compositionstart="isComposing = true"
        @compositionend="isComposing = false"
      />

      <AppButton v-if="busy" variant="secondary" class="chat-input__action" @click="onStop">
        <span class="chat-input__stop-icon" aria-hidden="true" />停止
      </AppButton>
      <AppButton v-else class="chat-input__action" :disabled="!canSend" @click="trySend">发送</AppButton>
    </div>
  </div>
</template>

<style scoped>
.chat-input__wrap {
  position: relative;
  display: flex;
  align-items: flex-end;
  gap: var(--space-2);
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: var(--space-2);
  transition: border-color var(--transition-base), box-shadow var(--transition-base);
}
.chat-input__wrap:focus-within {
  border-color: var(--accent-border);
  box-shadow: 0 0 0 3px var(--accent-soft);
}

/* 「+」总入口 */
.chat-input__plus {
  position: relative;
  flex-shrink: 0;
}
.chat-input__plus-btn {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  color: var(--text-tertiary);
  transition: color var(--transition-fast), background-color var(--transition-fast);
}
.chat-input__plus-btn:hover,
.chat-input__plus-btn--open {
  color: var(--text-primary);
  background: var(--bg-subtle);
}
.chat-input__menu {
  position: absolute;
  bottom: calc(100% + var(--space-2));
  left: 0;
  z-index: var(--z-dropdown);
  min-width: 220px;
  max-width: min(320px, 80vw);
  max-height: 50vh;
  overflow-y: auto;
  padding: var(--space-2);
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
}
.chat-input__menu :deep(.chat-menu-title) {
  padding: var(--space-1) var(--space-2);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: var(--leading-xs);
  font-weight: 600;
}
.chat-input__menu :deep(.chat-menu-item) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-2);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  text-align: left;
  transition: color var(--transition-fast), background-color var(--transition-fast);
}
.chat-input__menu :deep(.chat-menu-item:hover) {
  color: var(--text-primary);
  background: var(--bg-subtle);
}
.chat-input__menu :deep(.chat-menu-item--active) {
  color: var(--accent-text);
}
.chat-input__menu :deep(.chat-menu-item__check) {
  flex-shrink: 0;
  color: var(--accent-text);
  font-size: var(--font-size-xs);
}

/* 输入域：约 6 行封顶 */
.chat-input__field {
  flex: 1;
  min-width: 0;
  background: transparent;
  border: none;
  outline: none;
  padding: var(--space-1) var(--space-2);
  font-size: var(--font-size-md);
  line-height: var(--leading-md);
  color: var(--text-primary);
  resize: none;
  max-height: calc(var(--leading-md) * 6 + var(--space-2));
  overflow-y: auto;
}
.chat-input__field::placeholder {
  color: var(--text-tertiary);
}
.chat-input__field:disabled {
  opacity: 0.5;
}

.chat-input__action {
  flex-shrink: 0;
}
.chat-input__stop-icon {
  display: block;
  width: var(--space-2);
  height: var(--space-2);
  background: currentColor;
  border-radius: 2px;
}
</style>
