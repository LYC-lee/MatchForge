<script setup lang="ts">
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'

/**
 * 确认对话框（teleport 到 body，role="dialog"，焦点圈禁，Esc 关闭）。
 *
 * 用法：
 *   const open = ref(false)
 *   <ConfirmDialog
 *     v-model:open="open"
 *     title="删除该产品？"
 *     description="删除后不可恢复，关联 BOM 将同步移除。"
 *     confirm-text="删除"
 *     danger
 *     @confirm="doDelete"
 *   />
 */
const props = withDefaults(defineProps<{
  open: boolean
  title: string
  description?: string
  confirmText?: string
  cancelText?: string
  /** 危险操作变体：确认按钮使用 danger 样式 */
  danger?: boolean
  /** 确认按钮 loading（异步操作进行中，禁止重复提交与关闭） */
  loading?: boolean
}>(), {
  confirmText: '确认',
  cancelText: '取消',
  danger: false,
  loading: false,
})

const emit = defineEmits<{
  (e: 'update:open', v: boolean): void
  (e: 'confirm'): void
  (e: 'cancel'): void
}>()

const panelRef = ref<HTMLElement | null>(null)
let previousActive: Element | null = null

const FOCUSABLE =
  'button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])'

function close(kind: 'cancel' | 'confirm') {
  if (props.loading) return
  emit('update:open', false)
  if (kind === 'confirm') emit('confirm')
  else emit('cancel')
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    e.stopPropagation()
    close('cancel')
    return
  }
  if (e.key !== 'Tab' || !panelRef.value) return
  // 焦点圈禁：Tab 在面板内循环
  const nodes = Array.from(panelRef.value.querySelectorAll<HTMLElement>(FOCUSABLE))
  if (!nodes.length) return
  const first = nodes[0]
  const last = nodes[nodes.length - 1]
  const active = document.activeElement
  if (e.shiftKey && active === first) {
    e.preventDefault()
    last.focus()
  } else if (!e.shiftKey && active === last) {
    e.preventDefault()
    first.focus()
  }
}

watch(
  () => props.open,
  async (v) => {
    if (v) {
      previousActive = document.activeElement
      document.addEventListener('keydown', onKeydown, true)
      document.body.style.overflow = 'hidden'
      await nextTick()
      // 初始焦点落在第一个可聚焦元素（danger 时为取消按钮，防误确认）
      const nodes = panelRef.value?.querySelectorAll<HTMLElement>(FOCUSABLE)
      const target = props.danger ? nodes?.[0] : nodes?.[nodes.length - 1]
      ;(target ?? panelRef.value)?.focus()
    } else {
      document.removeEventListener('keydown', onKeydown, true)
      document.body.style.overflow = ''
      if (previousActive instanceof HTMLElement) previousActive.focus()
      previousActive = null
    }
  },
)

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown, true)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="mf-dialog">
      <div v-if="open" class="dialog-mask" @click.self="close('cancel')">
        <div
          ref="panelRef"
          class="dialog"
          role="dialog"
          aria-modal="true"
          :aria-label="title"
          tabindex="-1"
        >
          <h2 class="dialog__title">{{ title }}</h2>
          <p v-if="description" class="dialog__desc">{{ description }}</p>
          <div class="dialog__actions">
            <AppButton variant="secondary" size="md" :disabled="loading" @click="close('cancel')">
              {{ cancelText }}
            </AppButton>
            <AppButton
              :variant="danger ? 'danger' : 'primary'"
              size="md"
              :loading="loading"
              @click="close('confirm')"
            >
              {{ confirmText }}
            </AppButton>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.dialog-mask {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-4);
  background: rgba(23, 23, 28, 0.4);
}
[data-theme='dark'] .dialog-mask {
  background: rgba(0, 0, 0, 0.55);
}
.dialog {
  width: 100%;
  max-width: 400px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  padding: var(--space-5);
}
.dialog__title {
  font-size: var(--font-size-md);
  line-height: var(--leading-md);
  font-weight: 600;
  color: var(--text-primary);
}
.dialog__desc {
  margin-top: var(--space-2);
  font-size: var(--font-size-sm);
  line-height: var(--leading-sm);
  color: var(--text-secondary);
}
.dialog__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-5);
}

.mf-dialog-enter-active,
.mf-dialog-leave-active {
  transition: opacity var(--transition-base);
}
.mf-dialog-enter-active .dialog,
.mf-dialog-leave-active .dialog {
  transition: transform var(--transition-base), opacity var(--transition-base);
}
.mf-dialog-enter-from,
.mf-dialog-leave-to {
  opacity: 0;
}
.mf-dialog-enter-from .dialog,
.mf-dialog-leave-to .dialog {
  transform: translateY(8px);
}
</style>
